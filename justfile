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
build: setup
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

clean:
    rm -rf subprojects/suite-common "$HOME/.cache/tables-flatpak"
