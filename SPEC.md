# Tables — Specification

**Tables** is a spreadsheet for the GNOME desktop (Excel-equivalent), part of a FOSS
office suite alongside [Letters](https://github.com/codelogistics/letters) (word
processor) and [Decks](https://github.com/hanthor/decks) (presentation). It follows the
Letters pattern: **pure libadwaita chrome wrapping a `WebKit.WebView` engine**, with
**in-process Python libraries** doing file I/O. See
[suite-common](https://github.com/hanthor/suite-common) for the shared architecture.

- **App ID:** `io.github.hanthor.tables`
- **Runtime:** `org.gnome.Platform` 50, Flatpak
- **Stack:** Python + PyGObject + GTK4 + libadwaita + WebKitGTK 6.0 + Blueprint
- **License:** GPLv3-or-later (matches Letters; required by HyperFormula's GPL option)

## Engine (best-of-breed)

| Concern | Library | License | Notes |
|---------|---------|---------|-------|
| Grid UI | **Jspreadsheet CE** | MIT | cells, selection, resize, context menus, formatting |
| Formula engine | **HyperFormula** | GPLv3-or-commercial | dependency graph + 450+ Excel-compatible functions; runs in a Web Worker |

Wire HyperFormula as Jspreadsheet's calculation backend. *Fallback:* **FortuneSheet**
(MIT) — single dependency with grid + formulas + formatting, React runtime in the webview.

Engines are vendored as minified UMD bundles in `src/vendor/`, gresource'd, and
`<script>`-loaded into the HTML passed to `webview.load_html(...)` — the same way Letters
loads `editor.js`. No Node runtime ships in the Flatpak. The webview stays offline/sandboxed.

## File I/O (in-process Python, vendored as `python3-*` pip modules)

| Format | Read | Write |
|--------|------|-------|
| `.xlsx` | `python-calamine` (fast) or `openpyxl` | `openpyxl` |
| `.ods` | `odfpy` (or `pyexcel-ods3`) | `odfpy` |
| `.csv` | stdlib `csv` | stdlib `csv` |

The bridge converts a workbook ↔ the engine's JSON model (sheets, cells, formulas, number
formats). Formulas round-trip as strings; values recalc in HyperFormula. Mirrors Letters'
`pypandoc.convert_file(...)` flow over the `UserContentManager` script-message channel.

## Chrome (from suite-common)

`Adw.ApplicationWindow` + `Adw.TabView` (one workbook per tab; sheets as in-document tabs),
header bar, preferences, shortcuts dialog, about dialog, recent files, error toasts.
Target gnome-gui-spec parity with Letters (85/92 baseline).

## Repo layout

See [suite-common](https://github.com/hanthor/suite-common). `engine.js` initializes
Jspreadsheet + HyperFormula; `subprojects/suite-common/` provides the shell + bridge.

## Verification (end-to-end)

1. Build the Flatpak (vendored JS + pip libs).
2. Launch; confirm libadwaita chrome renders.
3. Open a sample `.xlsx` → cells + formulas load; edit a formula → live recalc via
   HyperFormula; Save → reopen in LibreOffice/Excel to confirm round-trip.
4. Repeat for `.ods` and `.csv`.
5. Run gnome-gui-spec audit; target Letters parity.

See repo **Issues** for the tracer-bullet vertical-slice build order.
