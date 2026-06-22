# L1 adapter round-trip tests for Tables — pure pytest, no display.
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Verifies csv/xlsx/ods values, cell styles, and multi-sheet survival
# via independent read-back.  See TESTING-SPEC.md §1.
#
# Run: pytest tests/unit/

import os
import sys
import tempfile

import pytest

# Add src/ to path so we can import fileio directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
import fileio  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────

def _roundtrip(sheets, ext):
    """Write sheets to a temp file and read them back. Returns the
    read-back triples."""
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, f'roundtrip.{ext}')
        fileio.write_spreadsheet(path, sheets)
        return fileio.read_spreadsheet(path)


def _openpyxl_read(path):
    """Read an xlsx with openpyxl as an independent verifier.
    Returns (sheet_names, cells_by_sheet)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    result = {}
    for ws in wb.worksheets:
        cells = {}
        styles = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells[cell.coordinate] = str(cell.value)
                css_parts = []
                if cell.font and cell.font.bold:
                    css_parts.append('font-weight:bold')
                if cell.font and cell.font.italic:
                    css_parts.append('font-style:italic')
                if cell.alignment and cell.alignment.horizontal:
                    css_parts.append('text-align:' + cell.alignment.horizontal)
                if css_parts:
                    styles[cell.coordinate] = ';'.join(css_parts)
        result[ws.title] = (cells, styles)
    return result


# ── CSV ────────────────────────────────────────────────────────────────

class TestCsvRoundtrip:
    def test_simple_values(self):
        sheets = [('Data', [['a', 'b'], ['1', '2']], {})]
        result = _roundtrip(sheets, 'csv')
        assert len(result) == 1
        # CSV always reads back as 'Sheet 1' (hardcoded in read_spreadsheet)
        assert result[0][1] == [['a', 'b'], ['1', '2']]

    def test_empty_cells(self):
        sheets = [('S', [['a', '', 'c'], ['', 'b', '']], {})]
        result = _roundtrip(sheets, 'csv')
        assert result[0][1] == [['a', '', 'c'], ['', 'b', '']]

    def test_numbers_preserved_as_strings(self):
        sheets = [('N', [[1, 2.5], [3, 4]], {})]
        result = _roundtrip(sheets, 'csv')
        # CSV is text; int/float become strings
        assert result[0][1][0] == ['1', '2.5']


# ── XLSX values ────────────────────────────────────────────────────────

class TestXlsxValues:
    """Write via fileio (openpyxl), read back via fileio AND via
    independent openpyxl for cross-verification."""
    @classmethod
    def setup_class(cls):
        pytest.importorskip('openpyxl')

    def test_roundtrip_values(self):
        sheets = [('Vals', [['alpha', 'beta'], ['1', '2']], {})]
        result = _roundtrip(sheets, 'xlsx')
        assert len(result) == 1
        assert result[0][0] == 'Vals'
        assert result[0][1][0] == ['alpha', 'beta']
        # _coerce() preserves numeric types: '1' -> 1, '2' -> 2
        assert result[0][1][1] == [1, 2]

    def test_independent_openpyxl_values(self):
        pytest.importorskip('openpyxl')
        sheets = [('Vals', [['hello', 'world'], ['42', '0']], {})]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'test.xlsx')
            fileio.write_spreadsheet(path, sheets)
            result = _openpyxl_read(path)
        assert 'Vals' in result
        cells, _styles = result['Vals']
        assert cells.get('A1') == 'hello'
        assert cells.get('B1') == 'world'
        assert cells.get('A2') == '42'


# ── XLSX styles ────────────────────────────────────────────────────────

STYLE_SHEETS = [('Styled', [['x', 'y'], ['1', '2']])]


class TestXlsxStyles:
    @classmethod
    def setup_class(cls):
        pytest.importorskip('openpyxl')

    def test_bold_roundtrip(self):
        styles = {'A1': 'font-weight:bold'}
        sheets = [('Styled', [['x', 'y'], ['1', '2']], styles)]
        result = _roundtrip(sheets, 'xlsx')
        assert 'bold' in result[0][2].get('A1', '')

    def test_italic_roundtrip(self):
        styles = {'B1': 'font-style:italic'}
        sheets = [('Styled', [['x', 'y'], ['1', '2']], styles)]
        result = _roundtrip(sheets, 'xlsx')
        assert 'italic' in result[0][2].get('B1', '')

    def test_alignment_roundtrip(self):
        styles = {'A1': 'text-align:center'}
        sheets = [('Styled', [['x', 'y'], ['1', '2']], styles)]
        result = _roundtrip(sheets, 'xlsx')
        assert 'text-align:center' in result[0][2].get('A1', '')

    def test_bold_independent_openpyxl(self):
        pytest.importorskip('openpyxl')
        styles = {'A1': 'font-weight:bold'}
        sheets = [('Styled', [['x', 'y'], ['1', '2']], styles)]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'test.xlsx')
            fileio.write_spreadsheet(path, sheets)
            result = _openpyxl_read(path)
        _, read_styles = result['Styled']
        assert 'bold' in read_styles.get('A1', '')

    def test_align_independent_openpyxl(self):
        pytest.importorskip('openpyxl')
        styles = {'B2': 'text-align:center'}
        sheets = [('Styled', [['x', 'y'], ['1', '2']], styles)]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'test.xlsx')
            fileio.write_spreadsheet(path, sheets)
            result = _openpyxl_read(path)
        _, read_styles = result['Styled']
        assert 'center' in read_styles.get('B2', '')


# ── ODS values ─────────────────────────────────────────────────────────

class TestOdsValues:
    @classmethod
    def setup_class(cls):
        pytest.importorskip('odf.opendocument')

    def test_roundtrip_values(self):
        sheets = [('Sheet1', [['a', 'b', 'c'], ['1', '2', '3']], {})]
        result = _roundtrip(sheets, 'ods')
        assert len(result) >= 1
        assert result[0][1][0] == ['a', 'b', 'c']

    def test_ods_empty_sheet(self):
        pytest.importorskip('odf.opendocument')
        sheets = [('Empty', [], {})]
        result = _roundtrip(sheets, 'ods')
        assert len(result) >= 1


# ── Multi-sheet ────────────────────────────────────────────────────────

class TestMultiSheet:
    def test_xlsx_multi_sheet(self):
        pytest.importorskip('openpyxl')
        sheets = [
            ('Alpha', [[1, 2], [3, 4]], {'A1': 'font-weight:bold'}),
            ('Beta', [['x', 'y']], {}),
        ]
        result = _roundtrip(sheets, 'xlsx')
        assert len(result) == 2
        names = [s[0] for s in result]
        assert 'Alpha' in names
        assert 'Beta' in names
        alpha = next(s for s in result if s[0] == 'Alpha')
        # _coerce() preserves numeric types: 1, 2 -> int
        assert alpha[1][0] == [1, 2]
        assert 'bold' in alpha[2].get('A1', '')

    def test_csv_only_first_sheet(self):
        sheets = [
            ('First', [['a']], {}),
            ('Second', [['b']], {}),
        ]
        result = _roundtrip(sheets, 'csv')
        # CSV only stores first sheet
        assert len(result) == 1
        assert result[0][1] == [['a']]


# ── Cross-format ───────────────────────────────────────────────────────

class TestCrossFormat:
    def test_csv_to_xlsx_values_survive(self):
        pytest.importorskip('openpyxl')
        sheets = [('X', [['name', 'qty'], ['Apples', '3'], ['Pears', '12']], {})]
        with tempfile.TemporaryDirectory() as td:
            csv_path = os.path.join(td, 'in.csv')
            fileio.write_spreadsheet(csv_path, sheets)
            csv_data = fileio.read_spreadsheet(csv_path)
            xlsx_path = os.path.join(td, 'out.xlsx')
            fileio.write_spreadsheet(xlsx_path, csv_data)
            xlsx_data = fileio.read_spreadsheet(xlsx_path)
        assert xlsx_data[0][1][0] == ['name', 'qty']
        # _coerce() preserves numeric: '3' -> 3
        assert xlsx_data[0][1][1] == ['Apples', 3]

    def test_xlsx_to_csv_values_survive(self):
        pytest.importorskip('openpyxl')
        sheets = [('X', [['name', 'qty'], ['Apples', '3']], {})]
        with tempfile.TemporaryDirectory() as td:
            xlsx_path = os.path.join(td, 'in.xlsx')
            fileio.write_spreadsheet(xlsx_path, sheets)
            xlsx_data = fileio.read_spreadsheet(xlsx_path)
            csv_path = os.path.join(td, 'out.csv')
            fileio.write_spreadsheet(csv_path, xlsx_data)
            csv_data = fileio.read_spreadsheet(csv_path)
        assert csv_data[0][1][0] == ['name', 'qty']
        assert csv_data[0][1][1] == ['Apples', '3']
