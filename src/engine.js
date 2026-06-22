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
      onchange: function () { post({ type: 'changed' }); },
      onselection: function (el2, x1, y1, x2, y2) { selection = [x1, y1, x2, y2]; }
    });
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
