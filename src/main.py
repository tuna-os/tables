# main.py — Tables application entry point.
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gio, Adw  # noqa: E402
from suite_common.application import SuiteApplication  # noqa: E402
from .window import TablesWindow  # noqa: E402


class TablesApplication(SuiteApplication):
    def __init__(self, version):
        super().__init__(application_id='io.github.hanthor.tables',
                         window_class=TablesWindow,
                         app_name='Tables',
                         version=version)

        # ── Format shortcuts ───────────────────────────────────────
        self._add_format_action('bold', 'font-weight:bold',
                                'font-weight:normal', ['<primary>b'])
        self._add_format_action('italic', 'font-style:italic',
                                'font-style:normal', ['<primary>i'])
        self._add_format_action('underline', 'text-decoration:underline',
                                'text-decoration:none', ['<primary>u'])

        # Add to shortcuts overlay
        self.shortcuts['Format'] = [
            ('<primary>b', _('Bold')),
            ('<primary>i', _('Italic')),
            ('<primary>u', _('Underline')),
        ]

    def _add_format_action(self, name, css_on, css_off, accels):
        """Create a toggle action that sends format CSS to the webview."""
        action = Gio.SimpleAction.new_stateful(
            name, None, Gio.Variant.new_boolean(False))
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


def main(version):
    Adw.init()
    app = TablesApplication(version)
    return app.run(sys.argv)
