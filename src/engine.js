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

  var sheet = null;  // single active worksheet; the workbook lives in Python

  function build(rows) {
    var el = document.getElementById('grid');
    el.innerHTML = '';
    if (!rows || !rows.length) { rows = [['', '', ''], ['', '', ''], ['', '', '']]; }
    sheet = jspreadsheet(el, {
      data: rows,
      minDimensions: [12, 30],
      parseFormulas: true,
      onchange: function () { post({ type: 'changed' }); }
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
    } else if (name === 'getData') {
      post({ type: 'data', data: sheet ? sheet.getData() : [], styles: currentStyles() });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
