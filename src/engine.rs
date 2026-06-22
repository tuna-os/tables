// engine.rs — In-memory spreadsheet engine.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Todo: Integrate IronCalc when API stabilizes (Model<'static>, CellValue Display).

/// Simple in-memory spreadsheet with formula evaluation placeholder.
pub struct Spreadsheet {
    cells: Vec<Vec<String>>,
    rows: usize,
    cols: usize,
}

impl Spreadsheet {
    pub fn new(rows: usize, cols: usize) -> Self {
        let cells = vec![vec![String::new(); cols]; rows];
        Self { cells, rows, cols }
    }

    pub fn set_cell(&mut self, row: usize, col: usize, value: &str) {
        if row < self.rows && col < self.cols {
            self.cells[row][col] = value.to_string();
        }
    }

    pub fn get_cell(&self, row: usize, col: usize) -> &str {
        if row < self.rows && col < self.cols {
            &self.cells[row][col]
        } else {
            ""
        }
    }

    pub fn to_grid(&self) -> Vec<Vec<String>> {
        self.cells.clone()
    }

    pub fn dimensions(&self) -> (usize, usize) {
        (self.rows, self.cols)
    }
}

/// Read XLSX via calamine (crate added back as optional dependency).
pub fn read_spreadsheet(path: &std::path::Path) -> Result<(Vec<Vec<String>>, usize, usize), String> {
    Err("File I/O not yet implemented in native Rust build. Use Python version for now.".into())
}

pub fn write_spreadsheet(_path: &std::path::Path, _cells: &[Vec<String>]) -> Result<(), String> {
    Err("File I/O not yet implemented in native Rust build. Use Python version for now.".into())
}
