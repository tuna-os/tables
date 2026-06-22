# Tables — GNOME GUI Spec Audit

**Spec:** [hanthor/gnome-gui-spec](https://github.com/hanthor/gnome-gui-spec) v0.2.0
**App:** `io.github.hanthor.tables` — Python + PyGObject + GTK4 + libadwaita + WebKitGTK 6.0
**Audit date:** 2026-06-22

Tables inherits its chrome from [suite-common](https://github.com/hanthor/suite-common),
which now ports Letters' design idioms (raised toolbar, responsive action toolbar,
sizing, accessibility). The document surface is a `WebKit.WebView` running Jspreadsheet CE.

## 1. Widget Inventory

### Adw (libadwaita)
| Widget | Where |
|---|---|
| `AdwApplicationWindow` | suite_common/window.py |
| `AdwToolbarView` (`top-bar-style: raised`) | suite_common/window.py |
| `AdwHeaderBar` | suite_common/window.py |
| `AdwTabView` + `AdwTabBar` | suite_common/window.py |
| `AdwToastOverlay` | suite_common/window.py |
| `AdwBreakpoint` (`max-width: 500sp`) | suite_common/window.py (action bar) |
| `AdwPreferencesDialog` + `Page`/`Group`/`SwitchRow` | suite_common/dialogs.py |
| `AdwAboutDialog` | suite_common/application.py |
| `AdwStyleManager` (dark scheme) | suite_common/dialogs.py |

### Gtk (GTK4)
| Widget | Where |
|---|---|
| `GtkButton` / `GtkToggleButton` (flat, formatting) | tables window.py |
| `GtkMenuButton` (primary menu, `more`) | suite_common/window.py |
| `GtkDropDown` (sheet switcher) | tables window.py |
| `GtkBox` (`.toolbar`, centered) | suite_common/window.py |
| `GtkShortcutsWindow` | suite_common/dialogs.py |
| `GtkFileDialog` | tables window.py |

## 2. Checklist Compliance (§14)

**Architecture** — ✅ `AdwApplication` + `AdwApplicationWindow`; ✅ single window;
✅ adaptive (min 296×360, breakpoint at 500sp; works ≤360px).

**Header Bar** — ✅ centred title (implicit `AdwWindowTitle`); ✅ primary [start] / menu [end];
✅ all buttons have `tooltip-text`; ✅ flat (libadwaita header default); ✅ `<control>comma` → Preferences.

**Navigation** — ✅ one pattern (document tabs via `AdwTabView`).

**Preferences** — ✅ `AdwPreferencesDialog`; ✅ `search-enabled`; ✅ `AdwSwitchRow` (Dark Style,
working via `AdwStyleManager`); 🟡 **not GSettings-backed** (settings are in-memory).

**Feedback** — ✅ toasts via `AdwToastOverlay`/`SuiteWindow.toast()`; 🟡 no undo-toast;
🟡 no empty-state `AdwStatusPage` (the grid is always present).

**Styling** — ✅ follows system light/dark + manual toggle; ✅ symbolic icons; ✅ app CSS via
`.toolbar`; 🟡 typography classes not explicitly applied (content is web-rendered).

**Accessibility** — ✅ `accessibility`/`AccessibleProperty.LABEL` + tooltips on all custom
buttons, menu, window; 🟡 the WebKit grid's internals aren't bridged to AT-SPI.

## 3. Anti-pattern check (§13)
None of the listed anti-patterns are present: uses `AdwApplicationWindow`/`AdwHeaderBar`
(not the Gtk equivalents), preferences live in an `AdwPreferencesDialog` (not inline),
toasts (not confirmation dialogs), one navigation pattern, symbolic icons, header tooltips,
menu access keys (`_`).

## 4. Score

| Area | Score |
|---|---|
| Architecture | 10/10 |
| Header Bar | 10/10 |
| Navigation | 9/9 |
| Toolbar (responsive action bar) | 7/7 |
| Preferences | 6/7 (no GSettings) |
| Dialogs | 7/7 |
| Shortcuts | 7/7 |
| Menus | 7/7 |
| Typography | 6/7 |
| Spacing | 5/5 |
| Accessibility | 5/6 (webview) |
| Adaptive | 4/5 |
| Feedback | 4/5 (no undo/empty-state) |
| **Total** | **87/92 (95%)** |

## 5. Findings / follow-ups
1. Back preferences with **GSettings** (gschema + `glib_compile_schemas` post-install) and
   bind the Dark Style row — closes the only anti-pattern-adjacent gap (Preferences 6→7).
2. Add an **empty-state `AdwStatusPage`** for a freshly opened, blank workbook (Feedback 4→5).
3. Bridge the WebKit grid to AT-SPI for full accessibility (Accessibility 5→6).
