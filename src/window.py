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
        self._formulatest = os.environ.get('TABLES_FORMULATEST')
        self._guitest = os.environ.get('TABLES_GUITEST')
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
        open_btn.set_tooltip_text('Open')
        open_btn.update_property([Gtk.AccessibleProperty.LABEL], ['Open'])
        open_btn.connect('clicked', lambda *_: self.open_file())
        self.header_bar.pack_start(open_btn)

        save_btn = Gtk.Button(icon_name='document-save-symbolic')
        save_btn.set_tooltip_text('Save')
        save_btn.update_property([Gtk.AccessibleProperty.LABEL], ['Save'])
        save_btn.connect('clicked', lambda *_: self.save_file())
        self.header_bar.pack_start(save_btn)

        # Sheet switcher (workbook tabs live in Python; the grid shows one sheet).
        self.sheet_dropdown = Gtk.DropDown.new_from_strings(['Sheet 1'])
        self.sheet_dropdown.set_tooltip_text('Sheet')
        self.sheet_dropdown.update_property([Gtk.AccessibleProperty.LABEL], ['Sheet'])
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
        self._switch_to_sheet(idx)

    def _switch_to_sheet(self, idx):
        self._pending_active = idx
        self.webview.send('getData', None)

    def next_sheet(self):
        """Ctrl+PgDn: switch to the next sheet."""
        target = (self.active + 1) % len(self.sheets)
        self._switch_to_sheet(target)

    def prev_sheet(self):
        """Ctrl+PgUp: switch to the previous sheet."""
        target = (self.active - 1) % len(self.sheets)
        self._switch_to_sheet(target)

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

        # ── Data toolbar: merge, freeze, number format ──────────
        merge_btn = Gtk.Button(label='Merge')
        merge_btn.set_tooltip_text('Merge selected cells')
        merge_btn.update_property([Gtk.AccessibleProperty.LABEL], ['Merge cells'])
        merge_btn.connect('clicked', lambda b: self.webview.send('mergeCells', None))

        self.chart_combo = Gtk.DropDown.new_from_strings(
            ['Chart', 'Bar Chart', 'Line Chart', 'Pie Chart'])
        self.chart_combo.set_tooltip_text('Add chart on save')
        self.chart_combo.set_selected(0)
        self.chart_combo.connect('notify::selected', self._on_chart_type)

        self.border_btn = Gtk.Button(label='Border')
        self.border_btn.set_tooltip_text('Add borders to selected cells')
        self.border_btn.update_property([Gtk.AccessibleProperty.LABEL], ['Borders'])
        self.border_btn.connect('clicked',
            lambda b: self.webview.send('setBorders', '1px solid #888'))

        self.freeze_combo = Gtk.DropDown.new_from_strings(
            ['Freeze', 'Freeze 1 col', 'Freeze 1 row', 'Freeze 2 cols'])
        self.freeze_combo.set_tooltip_text('Freeze panes')
        self.freeze_combo.set_selected(0)
        self.freeze_combo.connect('notify::selected', self._on_freeze)

        self.number_combo = Gtk.DropDown.new_from_strings(
            ['Number', 'Currency', 'Percent', 'Date', 'Plain text'])
        self.number_combo.set_tooltip_text('Number format')
        self.number_combo.set_selected(0)
        self.number_combo.connect('notify::selected', self._on_number_format)

        data_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                          halign=Gtk.Align.CENTER, margin_top=4)
        data_bar.add_css_class('toolbar')
        data_bar.append(merge_btn)
        data_bar.append(self.border_btn)
        data_bar.append(self.chart_combo)
        data_bar.append(self.freeze_combo)
        data_bar.append(self.number_combo)
        self.toolbar_view.add_top_bar(data_bar)

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
            if self._formulatest:
                self._run_formulatest()
            if self._guitest:
                self._run_guitest_setup()
        elif kind == 'changed':
            self._dirty = True
        elif kind == 'formulaResult':
            self._on_formula_result(payload)
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
        # TABLES_GUITEST: save to predetermined path without dialog
        if self._guitest:
            path = os.path.join(self._guitest, 'out.xlsx')
            self._save_path = path
            self._after_save = lambda: (self._write_all(), print('[tables] guitest: saved', path, flush=True))
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
        # Post-process: add chart if selected in toolbar
        chart_type = getattr(self, '_chart_type', None)
        if chart_type and self._save_path.endswith('.xlsx'):
            try:
                from . import charts
                ws = self.sheets[0][0] if self.sheets else 'Sheet 1'
                rows = self.sheets[0][1] if self.sheets else []
                if len(rows) > 1 and len(rows[0]) >= 1:
                    charts.add_chart_to_file(
                        self._save_path, ws,
                        (1, 1, min(len(rows), 20), min(len(rows[0]), 5)),
                        chart_type,
                        f'{chart_type.title()} Chart', 'E10')
                    print(f'[tables] chart: added {chart_type} chart', flush=True)
            except Exception as exc:
                print(f'[tables] chart error: {exc}', flush=True)
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

    def _run_formulatest(self):
        """TABLES_FORMULATEST: validate formula vectors through HyperFormula.

        Loads a 1-row sheet with input values, sets the formula in B1,
        sends it to the engine, and prints the computed result.
        The pytest harness reads stdout for verification.
        """
        base = os.environ['TABLES_FORMULATEST']
        vectors = [
            # (label, formula, inputs, expected)
            ('sum', '=SUM(A1:C1)', [1, 2, 3], 6),
            ('avg', '=AVERAGE(A1:B1)', [10, 20], 15),
            ('min', '=MIN(A1:C1)', ['5', '2', '8'], 2),
            ('max', '=MAX(A1:C1)', ['5', '2', '8'], 8),
            ('add', '=A1+B1', [3, 7], 10),
            ('if_true', '=IF(A1>0,"pos","neg")', [5], 'pos'),
            ('if_false', '=IF(A1>0,"pos","neg")', [-3], 'neg'),
            ('round', '=ROUND(A1,0)', [3.7], 4),
            ('sqrt', '=SQRT(9)', [], 3),
            ('abs', '=ABS(A1)', [-7], 7),
        ]
        self._formula_vectors = vectors
        self._formula_idx = 0
        self._formula_base = base
        print('[tables] formulatest: running', len(vectors), 'vectors', flush=True)
        GLib.timeout_add(400, self._run_next_formula)

    def _run_next_formula(self):
        if self._formula_idx >= len(self._formula_vectors):
            print('[tables] formulatest: DONE', flush=True)
            return False
        label, formula, inputs, expected = self._formula_vectors[self._formula_idx]
        self._formula_idx += 1
        # Load inputs as row 1
        rows = [list(map(str, inputs))]
        self.sheets[0][1] = rows
        # Send formula to engine for computation
        payload = {'type': 'formulaTest', 'formula': formula, 'row': rows[0]}
        self._formula_expected = expected
        self._formula_label = label
        self.webview.send('formulaTest', payload)
        return False  # one-shot

    def _on_formula_result(self, payload):
        result = payload.get('result')
        expected = self._formula_expected
        label = self._formula_label
        ok = str(result) == str(expected)
        print(f'[tables] formulatest {label}: {result!r} == {expected!r} -> '
              f'{"PASS" if ok else "FAIL"}', flush=True)
        GLib.timeout_add(100, self._run_next_formula)

    # ----- guitest (TABLES_GUITEST) ----------------------------------------

    def _run_guitest_setup(self):
        """TABLES_GUITEST=<dir>: load fixture, enable save-without-dialog.

        The dogtail test drives GUI actions. The app auto-saves to
        <dir>/out.xlsx after 15s (enough time for AT-SPI interactions).
        Header bar icon-only Gtk.Buttons are not AT-SPI-accessible in GTK4,
        so we can't drive Save via dogtail.
        """
        base = self._guitest
        fixture = os.path.join(base, 'fixture.xlsx')
        if os.path.exists(fixture):
            self._load_path(fixture)
            print('[tables] guitest: loaded fixture', fixture, flush=True)
        else:
            # Create a minimal fixture so the grid has data to format.
            self.sheets[0][1] = [['Hello', 'World'], [42, 7]]
            self.sheets[0][2] = {}
            self.webview.send('load', self.sheets[0][1])
            print('[tables] guitest: using built-in test data', flush=True)
        # Auto-save after 15s so the oracle can verify the formatted output.
        GLib.timeout_add(15000, self._guitest_autosave)

    def _guitest_autosave(self):
        path = os.path.join(self._guitest, 'out.xlsx')
        self._save_path = path
        self._after_save = self._write_all
        self.webview.send('getData', None)  # capture grid state
        print('[tables] guitest: autosave requested', flush=True)
        return False

    # ----- helpers ----------------------------------------------------------

    def _on_chart_type(self, dropdown, _pspec):
        """Store chart type selection.  Chart is added at save time."""
        idx = dropdown.get_selected()
        self._chart_type = [None, 'bar', 'line', 'pie'][idx] if idx < 4 else None

    def _on_freeze(self, dropdown, _pspec):
        idx = dropdown.get_selected()
        if idx == 0:  # Freeze (none)
            self.webview.send('freezeColumns', 0)
            self.webview.send('freezeRows', 0)
        elif idx == 1:  # Freeze 1 col
            self.webview.send('freezeColumns', 1)
        elif idx == 2:  # Freeze 1 row
            self.webview.send('freezeRows', 1)
        elif idx == 3:  # Freeze 2 cols
            self.webview.send('freezeColumns', 2)

    def _on_number_format(self, dropdown, _pspec):
        formats = [None, '$ #,##0.00', '0.00%', 'DD/MM/YYYY', None]
        idx = dropdown.get_selected()
        fmt = formats[idx] if idx < len(formats) else None
        self.webview.send('setNumberFormat', fmt)

    def _toast(self, text):
        print('[tables]', text, flush=True)
