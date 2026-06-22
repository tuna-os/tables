# window.py — Tables main window.
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw, GLib  # noqa: E402
from suite_common.window import SuiteWindow  # noqa: E402
from suite_common.webview import SuiteWebView, build_document  # noqa: E402
from . import fileio  # noqa: E402

VENDOR_ASSETS = [
    ('css', 'jsuites.css'),
    ('css', 'jspreadsheet.css'),
    ('js', 'jsuites.js'),
    ('js', 'jspreadsheet.js'),
    ('js', 'hyperformula.full.min.js'),
]


class TablesWindow(SuiteWindow):
    def __init__(self, **kwargs):
        super().__init__(app_name='Tables', **kwargs)
        self._moduledir = os.path.dirname(__file__)
        self._save_path = None
        self._dirty = False
        # The workbook: list of [name, rows, styles]. The grid edits one at a time.
        self.sheets = [['Sheet 1', [], {}]]
        self.active = 0
        self._pending_active = None   # sheet to switch to after saving current
        self._after_save = None       # callable to run once active sheet is captured

        self._selftest = os.environ.get('TABLES_SELFTEST')
        self._multitest = os.environ.get('TABLES_MULTITEST')
        self._styletest = os.environ.get('TABLES_STYLETEST')
        print('[tables] selftest =', self._selftest, flush=True)

        self.webview = SuiteWebView(on_message=self._on_message)
        page = self.tab_view.append(self.webview)
        page.set_title('Sheet 1')

        self._add_header_buttons()
        self._add_format_toolbar()
        self.webview.load_app(self._build_html())

    # ----- UI ---------------------------------------------------------------

    def _add_header_buttons(self):
        open_btn = Gtk.Button(label='Open')
        open_btn.connect('clicked', lambda *_: self.open_file())
        self.header_bar.pack_start(open_btn)

        save_btn = Gtk.Button(icon_name='document-save-symbolic')
        save_btn.set_tooltip_text('Save')
        save_btn.connect('clicked', lambda *_: self.save_file())
        self.header_bar.pack_start(save_btn)

        # Sheet switcher (workbook tabs live in Python; the grid shows one sheet).
        self.sheet_dropdown = Gtk.DropDown.new_from_strings(['Sheet 1'])
        self.sheet_dropdown.connect('notify::selected', self._on_sheet_selected)
        self.header_bar.pack_start(self.sheet_dropdown)

    def _refresh_sheet_dropdown(self):
        names = Gtk.StringList.new([sheet[0] for sheet in self.sheets])
        self.sheet_dropdown.handler_block_by_func(self._on_sheet_selected)
        self.sheet_dropdown.set_model(names)
        self.sheet_dropdown.set_selected(self.active)
        self.sheet_dropdown.handler_unblock_by_func(self._on_sheet_selected)

    def _on_sheet_selected(self, dropdown, _param):
        idx = dropdown.get_selected()
        if idx == self.active or idx >= len(self.sheets):
            return
        # Capture the current sheet, then switch.
        self._pending_active = idx
        self.webview.send('getData', None)

    def _add_format_toolbar(self):
        # Letters idiom: a centered formatting toolbar that applies cell styles,
        # with a responsive extended/more split (suite-common add_action_bar).
        def toggle(icon, label, css_on, css_off):
            btn = Gtk.ToggleButton(icon_name=icon)
            btn.set_tooltip_text(label)
            btn.update_property([Gtk.AccessibleProperty.LABEL], [label])
            btn.connect('toggled', lambda b: self.webview.send(
                'format', {'css': css_on if b.get_active() else css_off}))
            return btn

        bold = toggle('format-text-bold-symbolic', 'Bold',
                      'font-weight:bold', 'font-weight:normal')
        italic = toggle('format-text-italic-symbolic', 'Italic',
                        'font-style:italic', 'font-style:normal')
        underline = toggle('format-text-underline-symbolic', 'Underline',
                           'text-decoration:underline', 'text-decoration:none')

        # Alignment via a window action group (also drives the collapsed 'more' menu).
        group = Gio.SimpleActionGroup()
        for name, align in (('left', 'left'), ('center', 'center'), ('right', 'right')):
            act = Gio.SimpleAction.new(f'align-{name}', None)
            act.connect('activate',
                        lambda a, p, al=align: self.webview.send('format', {'css': f'text-align:{al}'}))
            group.add_action(act)
        self.insert_action_group('fmt', group)

        def align_btn(icon, label, action):
            btn = Gtk.Button(icon_name=icon, action_name=action)
            btn.set_tooltip_text(label)
            btn.update_property([Gtk.AccessibleProperty.LABEL], [label])
            return btn

        left = align_btn('format-justify-left-symbolic', 'Align Left', 'fmt.align-left')
        center = align_btn('format-justify-center-symbolic', 'Align Center', 'fmt.align-center')
        right = align_btn('format-justify-right-symbolic', 'Align Right', 'fmt.align-right')

        more = Gio.Menu()
        more.append('Align Left', 'fmt.align-left')
        more.append('Align Center', 'fmt.align-center')
        more.append('Align Right', 'fmt.align-right')

        self.add_action_bar(primary=[bold, italic, underline],
                            extended=[left, center, right], more_menu=more)

    def _build_html(self):
        vendor_dir = os.path.join(self._moduledir, 'vendor')
        with open(os.path.join(self._moduledir, 'engine.js'), encoding='utf-8') as fh:
            engine = fh.read()
        body = '<div id="grid" style="height:100vh;width:100%"></div>'
        head_extra = f'<script>{engine}</script>'
        return build_document(vendor_dir, VENDOR_ASSETS, body, head_extra)

    # ----- bridge -----------------------------------------------------------

    def _on_message(self, payload):
        kind = payload.get('type')
        if kind == 'ready':
            print('[tables] engine ready:', payload.get('engine'), flush=True)
            if self._selftest:
                self._run_selftest()
            if self._multitest:
                self._run_multitest()
            if self._styletest:
                self._run_styletest()
        elif kind == 'changed':
            self._dirty = True
        elif kind == 'data':
            # Capture the active sheet (values + styles) into the workbook.
            self.sheets[self.active][1] = self._trim(payload.get('data') or [])
            self.sheets[self.active][2] = payload.get('styles') or {}
            if self._pending_active is not None:
                self.active = self._pending_active
                self._pending_active = None
                self._refresh_sheet_dropdown()
                self.webview.send('load', self.sheets[self.active][1])
                self.webview.send('applyStyles', self.sheets[self.active][2])
            elif self._after_save is not None:
                callback = self._after_save
                self._after_save = None
                callback()

    # ----- file I/O ---------------------------------------------------------

    def open_file(self):
        dialog = Gtk.FileDialog(title='Open Spreadsheet')
        flt = Gtk.FileFilter()
        flt.set_name('Spreadsheets')
        for pat in ('*.csv', '*.xlsx', '*.ods'):
            flt.add_pattern(pat)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_done)

    def _on_open_done(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        self._load_path(gfile.get_path())

    def _load_path(self, path):
        try:
            sheets = fileio.read_spreadsheet(path)
        except Exception as exc:  # noqa: BLE001
            self._toast(f'Could not open: {exc}')
            return
        self.sheets = []
        for name, rows, styles in sheets:
            width = max((len(r) for r in rows), default=1)
            rect = [list(r) + [''] * (width - len(r)) for r in rows]
            self.sheets.append([name or 'Sheet', rect, styles or {}])
        if not self.sheets:
            self.sheets = [['Sheet 1', [], {}]]
        self.active = 0
        self._save_path = path
        self._refresh_sheet_dropdown()
        self.webview.send('load', self.sheets[0][1])
        self.webview.send('applyStyles', self.sheets[0][2])
        self._toast(f'Opened {os.path.basename(path)}')

    def save_file(self):
        if self._save_path:
            self._after_save = self._write_all
            self.webview.send('getData', None)
            return
        dialog = Gtk.FileDialog(title='Save Spreadsheet')
        dialog.set_initial_name('Untitled.csv')
        dialog.save(self, None, self._on_save_done)

    def _on_save_done(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        self._save_path = gfile.get_path()
        self._after_save = self._write_all
        self.webview.send('getData', None)

    def _write_all(self):
        if not self._save_path:
            return
        try:
            fileio.write_spreadsheet(
                self._save_path,
                [(name, rows, styles) for name, rows, styles in self.sheets])
        except Exception as exc:  # noqa: BLE001
            self._toast(f'Could not save: {exc}')
            return
        self._dirty = False
        self._toast(f'Saved {os.path.basename(self._save_path)}')

    @staticmethod
    def _trim(data):
        grid = [['' if c is None else str(c) for c in row] for row in data]
        max_col = 0
        for row in grid:
            for i in range(len(row) - 1, -1, -1):
                if row[i] != '':
                    max_col = max(max_col, i + 1)
                    break
        grid = [row[:max_col] for row in grid]
        while grid and all(cell == '' for cell in grid[-1]):
            grid.pop()
        return grid

    # ----- self-test --------------------------------------------------------

    def _run_selftest(self):
        try:
            in_path, _, out_path = self._selftest.partition(':')
            self._load_path(in_path)
            self._save_path = out_path
            self._after_save = self._write_all
            GLib.timeout_add(600, self._selftest_pull)
        except Exception as exc:  # noqa: BLE001
            print('[tables] selftest error:', exc, flush=True)

    def _selftest_pull(self):
        print('[tables] selftest requesting data', flush=True)
        self.webview.send('getData', None)
        return False

    def _run_multitest(self):
        try:
            base = self._multitest
            inp = os.path.join(base, 'in.xlsx')
            self._mt_out = os.path.join(base, 'out.xlsx')
            sheets = [('Alpha', [['1', '2'], ['3', '4']]), ('Beta', [['5', '6']])]
            fileio.write_spreadsheet(inp, sheets)   # multi-sheet write
            self._load_path(inp)                    # loads sheet 0, stores both
            self._save_path = self._mt_out
            self._after_save = self._multitest_save_and_verify
            GLib.timeout_add(700, lambda: (self.webview.send('getData', None), False)[1])
        except Exception as exc:  # noqa: BLE001
            print('[tables] multitest error:', exc, flush=True)

    def _run_styletest(self):
        base = self._styletest
        path = os.path.join(base, 's.xlsx')
        rows = [['x', 'y'], ['1', '2']]
        styles = {'A1': 'font-weight:bold', 'B1': 'text-align:center'}
        try:
            fileio.write_spreadsheet(path, [('Sheet1', rows, styles)])
            back = fileio.read_spreadsheet(path)
            bstyles = back[0][2]
            ok = 'bold' in bstyles.get('A1', '') and 'center' in bstyles.get('B1', '')
            print(f'[tables] styletest A1={bstyles.get("A1")!r} '
                  f'B1={bstyles.get("B1")!r} -> {"PASS" if ok else "FAIL"}', flush=True)
        except Exception as exc:  # noqa: BLE001
            print('[tables] styletest error:', exc, flush=True)

    def _multitest_save_and_verify(self):
        self._write_all()   # writes all sheets (active updated, others preserved)
        try:
            back = fileio.read_spreadsheet(self._mt_out)
            names = [sheet[0] for sheet in back]
            ok = names == ['Alpha', 'Beta']
            print(f'[tables] multitest sheets={names} -> '
                  f'{"PASS" if ok else "FAIL"}', flush=True)
        except Exception as exc:  # noqa: BLE001
            print('[tables] multitest verify error:', exc, flush=True)

    # ----- helpers ----------------------------------------------------------

    def _toast(self, text):
        print('[tables]', text, flush=True)
