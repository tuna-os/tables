# Tables — build & run as a Flatpak using the org.flatpak.Builder flatpak.
# Designed to run on the `himachal` build host (no system flatpak-builder needed).

app_id := "io.github.hanthor.tables"
manifest := app_id + ".json"

default:
    @just --list

# Fetch vendored JS engines into src/vendor/ (commit the result; flatpak builds offline).
vendor:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p src/vendor
    base="https://cdn.jsdelivr.net/npm"
    curl -fsSL "$base/jspreadsheet-ce@4/dist/index.js"            -o src/vendor/jspreadsheet.js
    curl -fsSL "$base/jspreadsheet-ce@4/dist/jspreadsheet.css"    -o src/vendor/jspreadsheet.css
    curl -fsSL "$base/jsuites@4/dist/jsuites.js"                  -o src/vendor/jsuites.js
    curl -fsSL "$base/jsuites@4/dist/jsuites.css"                 -o src/vendor/jsuites.css
    curl -fsSL "$base/hyperformula@3/dist/hyperformula.full.min.js" -o src/vendor/hyperformula.full.min.js
    curl -fsSL "$base/jspreadsheet-ce@4/LICENSE" -o src/vendor/LICENSE.jspreadsheet-ce
    curl -fsSL "$base/jsuites@4/LICENSE"         -o src/vendor/LICENSE.jsuites
    echo "vendored:"; ls -la src/vendor

# Fetch the suite-common subproject (offline-safe; flatpak build sandbox has no net).
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p subprojects
    if [ -d subprojects/suite-common/.git ]; then
        git -C subprojects/suite-common fetch --depth 1 origin main
        git -C subprojects/suite-common reset --hard origin/main
    else
        rm -rf subprojects/suite-common
        git clone --depth 1 https://github.com/hanthor/suite-common.git subprojects/suite-common
    fi

# Build the Flatpak and install it to the user installation.
# Build artifacts live outside the source tree so `type: dir` only copies sources.
build: setup lint
    #!/usr/bin/env bash
    set -euo pipefail
    # org.flatpak.Builder is sandboxed: pin its cwd to this project and give it
    # host fs access. Run from a path under $HOME (flatpaks get a private /tmp).
    state="$HOME/.cache/tables-flatpak"
    mkdir -p "$state"
    flatpak run --cwd="$PWD" --filesystem=host org.flatpak.Builder \
        --force-clean --user --install --install-deps-from=flathub \
        --state-dir="$state/state" \
        --repo="$state/repo" \
        "$state/build" "{{manifest}}"

# Run the installed Flatpak. Inherits the caller's Wayland/X session.
run:
    flatpak run {{app_id}}

# Build, then launch headlessly for a few seconds to confirm it doesn't crash.
smoke: build
    #!/usr/bin/env bash
    set -euo pipefail
    timeout 8 flatpak run {{app_id}} >/tmp/tables-run.log 2>&1 &
    pid=$!
    sleep 6
    if kill -0 "$pid" 2>/dev/null; then echo "OK: still running"; kill "$pid" 2>/dev/null || true; else wait "$pid"; fi
    echo "--- log ---"; cat /tmp/tables-run.log || true

# Build, launch on the session, and assert the JS engine loaded (via console logs).
verify: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    log=$(mktemp)
    timeout 8 flatpak run --env=PYTHONUNBUFFERED=1 {{app_id}} >"$log" 2>&1 &
    pid=$!; sleep 6
    kill "$pid" 2>/dev/null || true
    echo "--- console ---"; cat "$log"
    # PASS requires: engine JS loaded (console) AND the JS->Python bridge delivered
    # the 'ready' message (the Python print) — proving suite-common #2 works.
    if grep -q "\[tables\] engine ready" "$log" \
       && grep -q "HyperFormula ready" "$log" \
       && grep -q "Jspreadsheet ready" "$log"; then
        echo "VERIFY: PASS (grid + HyperFormula loaded; JS<->Python bridge live)"
    else
        echo "VERIFY: FAIL"; exit 1
    fi

# Headless CSV round-trip test (tables #4): load a CSV through the engine and
# assert the written-back CSV matches.
csvtest: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    d="$HOME/.cache/tables-csvtest"; rm -rf "$d"; mkdir -p "$d"
    printf 'name,qty,price\nApples,3,1.50\nPears,12,0.80\n' > "$d/in.csv"
    flatpak run --env=PYTHONUNBUFFERED=1 --filesystem="$d" \
        --env=TABLES_SELFTEST="$d/in.csv:$d/out.csv" {{app_id}} >"$d/log" 2>&1 &
    pid=$!; sleep 6; kill "$pid" 2>/dev/null || true
    echo "--- log ---"; cat "$d/log"
    echo "--- out.csv ---"; cat "$d/out.csv" 2>/dev/null || echo "(no output)"
    if [ -f "$d/out.csv" ] && diff -q "$d/in.csv" "$d/out.csv" >/dev/null; then
        echo "CSVTEST: PASS (round-trip exact)"; rm -rf "$d"
    else
        echo "CSVTEST: FAIL"; rm -rf "$d"; exit 1
    fi

# Headless xlsx + ods round-trip test (tables #5, #6): csv -> xlsx -> csv and
# csv -> ods -> csv must reproduce the original (integer data for exactness).
fmttest: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    d="$HOME/.cache/tables-fmttest"; rm -rf "$d"; mkdir -p "$d"; : >"$d/log"
    printf 'name,qty\nApples,3\nPears,12\n' > "$d/in.csv"
    runsel() {
        flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
        timeout 9 flatpak run --env=PYTHONUNBUFFERED=1 --filesystem="$d" \
            --env=TABLES_SELFTEST="$1" {{app_id}} >>"$d/log" 2>&1 &
        local p=$!; sleep 7; flatpak kill {{app_id}} 2>/dev/null || true; kill "$p" 2>/dev/null || true; sleep 1
    }
    runsel "$d/in.csv:$d/out.xlsx"
    runsel "$d/out.xlsx:$d/rt_xlsx.csv"
    runsel "$d/in.csv:$d/out.ods"
    runsel "$d/out.ods:$d/rt_ods.csv"
    echo "--- log ---"; cat "$d/log"
    echo "--- rt_xlsx.csv ---"; cat "$d/rt_xlsx.csv" 2>/dev/null || echo "(none)"
    echo "--- rt_ods.csv ---"; cat "$d/rt_ods.csv" 2>/dev/null || echo "(none)"
    ok=1
    diff -q "$d/in.csv" "$d/rt_xlsx.csv" >/dev/null 2>&1 || { echo "xlsx round-trip MISMATCH"; ok=0; }
    diff -q "$d/in.csv" "$d/rt_ods.csv" >/dev/null 2>&1 || { echo "ods round-trip MISMATCH"; ok=0; }
    if [ "$ok" = 1 ]; then echo "FMTTEST: PASS (xlsx + ods round-trip exact)"; rm -rf "$d"; else echo "FMTTEST: FAIL"; exit 1; fi

# Multi-sheet round-trip (tables #8): 2-sheet workbook -> grid (tabs) -> xlsx -> 2 sheets.
multitest: build
    #!/usr/bin/env bash
    set -uo pipefail
    flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    d="$HOME/.cache/tables-multitest"; rm -rf "$d"; mkdir -p "$d"
    timeout 9 flatpak run --env=PYTHONUNBUFFERED=1 --filesystem="$d" \
        --env=TABLES_MULTITEST="$d" {{app_id}} >"$d/log" 2>&1 &
    pid=$!; sleep 7; flatpak kill {{app_id}} 2>/dev/null; kill "$pid" 2>/dev/null || true
    echo "--- log ---"; grep -E "multitest|sheets" "$d/log" || cat "$d/log"
    if grep -q "multitest sheets=\['Alpha', 'Beta'\] -> PASS" "$d/log"; then
        echo "MULTITEST: PASS (2 sheets survive grid round-trip)"; rm -rf "$d"
    else echo "MULTITEST: FAIL"; exit 1; fi

# Cell formatting round-trip (tables #7): bold + alignment survive xlsx save/reopen.
styletest: build
    #!/usr/bin/env bash
    set -uo pipefail
    flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    d="$HOME/.cache/tables-styletest"; rm -rf "$d"; mkdir -p "$d"
    timeout 9 flatpak run --env=PYTHONUNBUFFERED=1 --filesystem="$d" \
        --env=TABLES_STYLETEST="$d" {{app_id}} >"$d/log" 2>&1 &
    pid=$!; sleep 7; flatpak kill {{app_id}} 2>/dev/null; kill "$pid" 2>/dev/null || true
    echo "--- log ---"; grep styletest "$d/log" || tail -3 "$d/log"
    if grep -q "styletest .* -> PASS" "$d/log"; then
        echo "STYLETEST: PASS (bold + alignment round-trip xlsx)"; rm -rf "$d"
    else echo "STYLETEST: FAIL"; exit 1; fi

# Dogtail GUI test (AT-SPI): launch the Flatpak and drive it from the host.
# Requires dogtail + AT-SPI on the host session (Bluefin/GNOME has them).
guitest: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
    flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
    setsid flatpak run {{app_id}} >/tmp/tables-gui.log 2>&1 &
    sleep 8
    python3 tests/gui/test_tables.py; rc=$?
    flatpak kill {{app_id}} 2>/dev/null || true
    exit $rc

clean:
    rm -rf subprojects/suite-common "$HOME/.cache/tables-flatpak"

# Run L1 adapter round-trip tests (pytest, no display).
l1test:
    pip install pytest openpyxl odfpy 2>/dev/null
    pytest tests/unit/ -v

# Formula conformance test (ODF OpenFormula vectors via HyperFormula).
formulatest: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    d="$HOME/.cache/tables-formulatest"; rm -rf "$d"; mkdir -p "$d"
    flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
    timeout 15 flatpak run --env=PYTHONUNBUFFERED=1 --env=TABLES_FORMULATEST="$d" \
        {{app_id}} >"$d/log" 2>&1 &
    pid=$!; sleep 12; flatpak kill {{app_id}} 2>/dev/null || true; kill "$pid" 2>/dev/null || true
    echo "--- log ---"; grep formulatest "$d/log" || cat "$d/log"
    if grep -q 'formulatest: DONE' "$d/log" && ! grep -q 'formulatest.*FAIL' "$d/log"; then
        echo "FORMULATEST: PASS"; rm -rf "$d"
    else
        echo "FORMULATEST: FAIL"; exit 1
    fi

# L3 golden-file E2E (dogtail GUI + oracle verification).
e2etest: build
    #!/usr/bin/env bash
    set -uo pipefail
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    export WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep -m1 -E '^wayland-[0-9]+$' || echo wayland-0)"
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
    d="$HOME/.cache/tables-e2e"; rm -rf "$d"; mkdir -p "$d"
    flatpak kill {{app_id}} 2>/dev/null || true; sleep 1
    setsid flatpak run --filesystem="$d" --env=TABLES_GUITEST="$d" {{app_id}} >/tmp/tables-e2e.log 2>&1 &
    sleep 8
    python3 tests/gui/test_tables_e2e.py "$d"; rc=$?
    flatpak kill {{app_id}} 2>/dev/null || true
    exit $rc

# Lint Python source files (syntax check only).
lint:
    python3 -m py_compile src/main.py
    python3 -m py_compile src/window.py
