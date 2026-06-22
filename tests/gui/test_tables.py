#!/usr/bin/env python3
# Dogtail GUI test for Tables — drives the running Flatpak via AT-SPI.
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Uses AT-SPI actions (doActionNamed) rather than mouse synthesis, so it works
# headlessly on Wayland (no X display). Run on the HOST against a launched app:
#   python3 tests/gui/test_tables.py        (`just guitest` handles launch/teardown)

import os
import sys
import time

# Resolve suite-common: sibling clone (dev layout) or subproject (Flatpak build).
for _candidate in (
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'suite-common'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'subprojects', 'suite-common'),
):
    if os.path.isdir(_candidate):
        sys.path.insert(0, _candidate)
        break

from dogtail import tree  # noqa: E402
from suite_common.test_helpers import click, count_nodes, find_app, pressed, toggle_and_assert


def main():
    app = find_app('tables')
    print('found application: tables')

    bold = app.child(name='Bold', roleName='toggle button')
    italic = app.child(name='Italic', roleName='toggle button')
    app.child(name='Underline', roleName='toggle button')
    print('found formatting toggles: Bold, Italic, Underline')

    toggle_and_assert(bold)
    print('Bold toggles via AT-SPI: OK')

    click(italic)
    time.sleep(0.4)
    assert pressed(italic), 'Italic should be pressed after AT-SPI click'
    print('Italic toggles via AT-SPI: OK')

    # The primary menu button (Letters idiom) is findable + activatable.
    menu = app.child(name='Main Menu', roleName='toggle button', showingOnly=False)
    click(menu)
    time.sleep(0.4)
    print('primary menu found + activated: OK')

    # The sheet switcher (workbook tabs) is exposed as a combo box.
    app.child(roleName='combo box', showingOnly=False)
    print('sheet switcher (combo box) found: OK')

    # The WebKit grid is bridged to AT-SPI — many descendant cells are present.
    descendants = count_nodes(app)
    assert descendants > 50, f'expected the grid bridged to AT-SPI, got {descendants} nodes'
    print(f'WebKit grid bridged to AT-SPI: {descendants} accessible nodes')

    print('GUITEST: PASS')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f'GUITEST: FAIL — {exc}')
        sys.exit(1)
