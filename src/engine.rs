// engine.rs — Spreadsheet engine: read/write XLSX/CSV + IronCalc formulas.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Uses calamine for reading, rust_xlsxwriter for writing,
// and IronCalc for formula evaluation.

use std::collections::HashMap;
use std::path::Path;

/// A 2D grid of cells with optional formulas.
pub struct Spreadsheet {
    pub rows: usize,
    pub cols: usize,
    pub cells: Vec<Vec<String>>,
    formulas: HashMap<(usize, usize), String>,  // (row, col) → formula
    engine: ironcalc::IronCalc,
}

impl Spreadsheet {
    pub fn new(rows: usize, cols: usize) -> Self {
        let cells = vec![vec![String::new(); cols]; rows];
        Self {
            rows, cols, cells,
            formulas: HashMap::new(),
            engine: ironcalc::IronCalc::new(),
        }
    }

    pub fn set(&mut self, row: usize, col: usize, value: &str) {
        if row < self.rows && col < self.cols {
            self.cells[row][col] = value.to_string();
            // Remove any formula at this cell
            self.formulas.remove(&(row, col));
        }
    }

    pub fn set_formula(&mut self, row: usize, col: usize, formula: &str) {
        if row < self.rows && col < self.cols {
            self.formulas.insert((row, col), formula.to_string());
        }
    }

    pub fn get(&self, row: usize, col: usize) -> &str {
        if row < self.rows && col < self.cols {
            &self.cells[row][col]
        } else {
            ""
        }
    }

    /// Evaluate all formulas and update cell values.
    pub fn recalc(&mut self) {
        // Build IronCalc sheet from data
        let mut sheet_data: Vec<Vec<String>> = Vec::new();
        for r in 0..self.rows {
            let mut row = Vec::new();
            for c in 0..self.cols {
                if let Some(formula) = self.formulas.get(&(r, c)) {
                    row.push(formula.clone());
                } else {
                    row.push(self.cells[r][c].clone());
                }
            }
            sheet_data.push(row);
        }

        // Let IronCalc evaluate
        if let Ok(results) = self.engine.evaluate(&sheet_data) {
            for r in 0..self.rows {
                for c in 0..self.cols {
                    if self.formulas.contains_key(&(r, c)) {
                        if let Some(val) = results.get(r).and_then(|row| row.get(c)) {
                            self.cells[r][c] = val.clone();
                        }
                    }
                }
            }
        }
    }

    /// Load data from a CSV/TSV string.
    pub fn load_csv(&mut self, data: &str) {
        for (r, line) in data.lines().enumerate() {
            for (c, cell) in line.split('\t').enumerate() {
                if r < self.rows && c < self.cols {
                    self.cells[r][c] = cell.to_string();
                }
            }
        }
        self.formulas.clear();
    }

    /// Return tab-separated text for display.
    pub fn to_tsv(&self) -> String {
        let mut result = String::new();
        for r in 0..self.rows {
            for c in 0..self.cols {
                if c > 0 { result.push('\t'); }
                result.push_str(&self.cells[r][c]);
            }
            result.push('\n');
        }
        result
    }
}

/// Read an XLSX/ODS/CSV file and return a Spreadsheet.
pub fn read_spreadsheet(path: &Path) -> Result<Spreadsheet, String> {
    let mut workbook = calamine::open_workbook_auto(path)
        .map_err(|e| format!("Failed to open: {}", e))?;

    let sheet_names = workbook.sheet_names().to_vec();
    let name = sheet_names.first().cloned().unwrap_or_default();
    let range = workbook.worksheet_range(&name)
        .map_err(|e| format!("Read error: {}", e))?;

    let rows = range.rows().count().max(50);
    let cols = range.rows().next().map(|r| r.len()).unwrap_or(10).max(10);
    let mut sheet = Spreadsheet::new(rows, cols);

    for (r, row) in range.rows().enumerate() {
        for (c, cell) in row.iter().enumerate() {
            if r < rows && c < cols {
                sheet.set(r, c, &cell.to_string());
            }
        }
    }
    Ok(sheet)
}

/// Write a Spreadsheet to an XLSX file.
pub fn write_spreadsheet(path: &Path, sheet: &Spreadsheet) -> Result<(), String> {
    use rust_xlsxwriter::*;
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();

    for r in 0..sheet.rows {
        for c in 0..sheet.cols {
            worksheet
                .write_string(r as u32, c as u16, &sheet.cells[r][c])
                .map_err(|e| format!("Write error: {}", e))?;
        }
    }
    workbook.save(path).map_err(|e| format!("Save error: {}", e))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_io() {
        let mut s = Spreadsheet::new(3, 2);
        s.set(0, 0, "Hello");
        s.set(1, 1, "World");
        assert_eq!(s.get(0, 0), "Hello");
        assert_eq!(s.get(1, 1), "World");
        assert_eq!(s.get(2, 1), "");
    }

    #[test]
    fn test_formula_sum() {
        let mut s = Spreadsheet::new(4, 2);
        s.set(0, 0, "10");
        s.set(1, 0, "20");
        s.set(2, 0, "30");
        s.set_formula(3, 0, "=SUM(A1:A3)");
        s.recalc();
        assert_eq!(s.get(3, 0), "60");
    }

    #[test]
    fn test_roundtrip_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.xlsx");
        let mut s = Spreadsheet::new(3, 2);
        s.set(0, 0, "Name");
        s.set(0, 1, "Age");
        s.set(1, 0, "Alice");
        s.set(1, 1, "30");
        write_spreadsheet(&path, &s).unwrap();
        let back = read_spreadsheet(&path).unwrap();
        assert_eq!(back.get(0, 0), "Name");
        assert_eq!(back.get(1, 1), "30");
    }
}
