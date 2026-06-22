# main.py — Tables application entry point.
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gio, GLib, Adw  # noqa: E402
from suite_common.application import SuiteApplication  # noqa: E402
from .window import TablesWindow  # noqa: E402


class TablesApplication(SuiteApplication):
    def __init__(self, version):
        super().__init__(application_id='io.github.hanthor.tables',
                         window_class=TablesWindow,
                         app_name='Tables',
                         version=version)

        # ── Format shortcuts (MS Excel / Google Sheets convention) ──
        self._add_format_toggle('bold', 'font-weight:bold',
                                'font-weight:normal', ['<primary>b'])
        self._add_format_toggle('italic', 'font-style:italic',
                                'font-style:normal', ['<primary>i'])
        self._add_format_toggle('underline', 'text-decoration:underline',
                                'text-decoration:none', ['<primary>u'])

        # ── Sheet navigation (Excel convention) ──
        self._add_action('next-sheet', self._on_next_sheet,
                         ['<primary>Page_Down'])
        self._add_action('prev-sheet', self._on_prev_sheet,
                         ['<primary>Page_Up'])

        # ── Selection (Excel convention) ──
        self._add_action('select-column', self._on_select,
                         ['<primary>space'])
        self._add_action('select-row', self._on_select,
                         ['<shift>space'])

        # ── Fill (Excel convention) ──
        self._add_action('fill-down', self._on_fill,
                         ['<primary>d'])
        self._add_action('fill-right', self._on_fill,
                         ['<primary>r'])

        # Add to shortcuts overlay
        self.shortcuts[_('Format')] = [
            ('<primary>b', _('Bold')),
            ('<primary>i', _('Italic')),
            ('<primary>u', _('Underline')),
        ]
        self.shortcuts[_('Sheet')] = [
            ('<primary>Page Down', _('Next Sheet')),
            ('<primary>Page Up', _('Previous Sheet')),
        ]
        self.shortcuts[_('Selection')] = [
            ('<primary>Space', _('Select Column')),
            ('<shift>Space', _('Select Row')),
        ]
        self.shortcuts[_('Fill')] = [
            ('<primary>d', _('Fill Down')),
            ('<primary>r', _('Fill Right')),
        ]

    def _add_format_toggle(self, name, css_on, css_off, accels):
        action = Gio.SimpleAction.new_stateful(
            name, None, GLib.Variant.new_boolean(False))
        action.connect('change-state', self._on_format_toggle, css_on, css_off)
        self.add_action(action)
        if accels:
            self.set_accels_for_action(f'app.{name}', accels)

    def _on_format_toggle(self, action, state, css_on, css_off):
        action.set_state(state)
        win = self.props.active_window
        if win and hasattr(win, 'webview'):
            active = state.get_boolean()
            win.webview.send('format', {'css': css_on if active else css_off})

    def _on_next_sheet(self, *a):
        self._call_win('next_sheet')

    def _on_prev_sheet(self, *a):
        self._call_win('prev_sheet')

    def _on_fill(self, action, *a):
        """Ctrl+D: fill down. Ctrl+R: fill right."""
        name = action.get_name()
        msg = 'fillDown' if name == 'fill-down' else 'fillRight'
        self._call_win('webview_send', msg, None)

    # ── Toolbar handlers ──────────────────────────────────────────

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
        name = action.get_name()
        if name == 'select-column':
            self._call_win('webview_send', 'selectColumn', None)
        elif name == 'select-row':
            self._call_win('webview_send', 'selectRow', None)


def main(version):
    Adw.init()
    app = TablesApplication(version)
    return app.run(sys.argv)
