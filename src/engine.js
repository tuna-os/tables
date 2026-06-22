/* engine.js — Tables spreadsheet engine: Jspreadsheet CE grid + HyperFormula.
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * Multi-worksheet (tabs) mode. Talks to Python over the `bridge` channel:
 * posts {type:...} up, receives via window.bridgeReceive.
 * Protocol: load/getData carry a list of {name, data} sheets.
 */
(function () {
  'use strict';

  function post(msg) {
    try { window.webkit.messageHandlers.bridge.postMessage(msg); }
    catch (e) { console.log('bridge post failed: ' + e); }
  }

  var sheet = null;       // single active worksheet; the workbook lives in Python
  var selection = null;   // [x1, y1, x2, y2] of the current selection

  function cellName(x, y) {
    var s = '', n = x;
    do { s = String.fromCharCode(65 + (n % 26)) + s; n = Math.floor(n / 26) - 1; } while (n >= 0);
    return s + (y + 1);
  }

  function applyFormat(css) {
    if (!sheet || !selection || !css) { return; }
    var x1 = Math.min(selection[0], selection[2]), x2 = Math.max(selection[0], selection[2]);
    var y1 = Math.min(selection[1], selection[3]), y2 = Math.max(selection[1], selection[3]);
    var styles = {};
    for (var x = x1; x <= x2; x++) {
      for (var y = y1; y <= y2; y++) { styles[cellName(x, y)] = css; }
    }
    try { sheet.setStyle(styles); post({ type: 'changed' }); }
    catch (e) { console.log('applyFormat failed: ' + e); }
  }

  function build(rows) {
    var el = document.getElementById('grid');
    el.innerHTML = '';
    if (!rows || !rows.length) { rows = [['', '', ''], ['', '', ''], ['', '', '']]; }
    sheet = jspreadsheet(el, {
      data: rows,
      minDimensions: [12, 30],
      parseFormulas: true,
      // ── Sort, filter, edit ────────────────────────────────────
      columnSorting: true,
      columnFilters: true,
      columnDrag: true,
      allowInsertRow: true,
      allowDeleteRow: true,
      allowInsertColumn: true,
      allowDeleteColumn: true,
      allowRenameColumn: true,
      allowManualInsertColumn: true,
      // ── Events ───────────────────────────────────────────────
      onchange: function () { post({ type: 'changed' }); },
      onselection: function (el2, x1, y1, x2, y2) { selection = [x1, y1, x2, y2]; }
    });
    // Ensure A1 is selected so format actions (Bold, Italic, etc.)
    // have a target.  Without this, applyFormat returns early.
    selection = [0, 0, 0, 0];
  }

  function init() {
    build([['', '', ''], ['', '', ''], ['', '', '']]);

    try {
      var hf = HyperFormula.buildFromArray(
        [[1], [2], ['=SUM(A1:A2)']], { licenseKey: 'gpl-v3' });
      window.__hf = hf;
      console.log('HyperFormula ready: =SUM(A1:A2) = ' + hf.getCellValue({ sheet: 0, row: 2, col: 0 }));
    } catch (e) {
      console.log('HyperFormula init error: ' + e);
    }

    console.log('Jspreadsheet ready');
    post({ type: 'ready', engine: 'jspreadsheet-ce' });
  }

  function currentStyles() {
    try { return sheet ? sheet.getStyle() : {}; }
    catch (e) { return {}; }
  }

  // Python -> JS
  window.bridgeReceive = function (name, data) {
    if (name === 'load') {
      build(data);
      post({ type: 'changed' });
    } else if (name === 'applyStyles') {
      if (sheet && data && Object.keys(data).length) {
        try { sheet.setStyle(data); } catch (e) { console.log('setStyle failed: ' + e); }
      }
    } else if (name === 'format') {
      applyFormat(data && data.css);
    } else if (name === 'getData') {
      post({ type: 'data', data: sheet ? sheet.getData() : [], styles: currentStyles() });
    } else if (name === 'selectColumn') {
      if (sheet && selection) {
        sheet.updateSelection([selection[0], 0, selection[0], sheet.rows.length - 1]);
      }
    } else if (name === 'selectRow') {
      if (sheet && selection) {
        sheet.updateSelection([0, selection[1], sheet.headers.length - 1, selection[1]]);
      }
    } else if (name === 'mergeCells') {
      if (sheet && selection) {
        sheet.mergeCells(selection[0], selection[1], selection[2], selection[3]);
        post({ type: 'changed' });
      }
    } else if (name === 'freezeColumns') {
      if (sheet) {
        var n = data || 0;
        sheet.freezeColumns(n);
      }
    } else if (name === 'freezeRows') {
      if (sheet) {
        var n = data || 0;
        sheet.freezeRows(n);
      }
    } else if (name === 'setNumberFormat') {
      if (sheet && selection && data) {
        for (var c = selection[0]; c <= selection[2]; c++) {
          sheet.setColumnFormat(c, data);
        }
      }
    } else if (name === 'fillDown') {
      if (sheet) {
        var data = sheet.getData();
        for (var c = selection[0]; c <= selection[2]; c++) {
          var val = data[selection[1]][c];
          for (var r = selection[1] + 1; r <= selection[3]; r++) {
            data[r][c] = val;
            sheet.setValue(c, r, val);
          }
        }
        post({ type: 'changed' });
      }
    } else if (name === 'fillRight') {
      if (sheet) {
        var data = sheet.getData();
        for (var r = selection[1]; r <= selection[3]; r++) {
          var val = data[r][selection[0]];
          for (var c = selection[0] + 1; c <= selection[2]; c++) {
            data[r][c] = val;
            sheet.setValue(c, r, val);
          }
        }
        post({ type: 'changed' });
      }
    } else if (name === 'formulaTest') {
      // TABLES_FORMULATEST: compute formula with given input row via HyperFormula.
      try {
        var inputs = data.row || [];
        var formula = data.formula || '';
        var hfData = [inputs];
        // Add the formula in row 2, col 0
        var formulaRow = new Array(inputs.length || 1).fill('');
        formulaRow[0] = formula;
        hfData.push(formulaRow);
        var hf = HyperFormula.buildFromArray(hfData, { licenseKey: 'gpl-v3' });
        var result = hf.getCellValue({ sheet: 0, row: 1, col: 0 });
        post({ type: 'formulaResult', result: result });
      } catch (e) {
        post({ type: 'formulaResult', result: '#ERROR: ' + e.message });
      }
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
