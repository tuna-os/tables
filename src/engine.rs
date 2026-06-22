// engine.rs — Spreadsheet engine using IronCalc.
// SPDX-License-Identifier: GPL-3.0-or-later

use ironcalc_base::Model;

pub struct Spreadsheet {
    model: Model<'static>,
}

impl Spreadsheet {
    pub fn new(rows: usize, cols: usize) -> Result<Self, String> {
        let mut model = Model::new_empty("untitled", "en", "UTC", "en")
            .map_err(|e| format!("Create: {}", e))?;
        for r in 0..rows {
            for c in 0..cols {
                model.set_user_input(0, r as i32 + 1, c as i32 + 1, "")
                    .map_err(|e| format!("Set: {}", e))?;
            }
        }
        Ok(Self { model })
    }

    pub fn load(path: &str) -> Result<Self, String> {
        let tmp = ironcalc::import::load_from_xlsx(path, "en_US", "UTC", "en")
            .map_err(|e| format!("Load: {}", e))?;
        // Rebuild as Model<'static> via native serialization
        let buf = tmp.to_bytes().map_err(|e| format!("Serialize: {}", e))?;
        let model = Model::from_bytes(&buf, "en".to_string(), "UTC".to_string(), "en".to_string())
            .unwrap_or_else(|_| {
                // Fallback: empty model
                Model::new_empty("loaded", "en", "UTC", "en").unwrap()
            });
        Ok(Self { model })
    }

    pub fn save(&self, path: &str) -> Result<(), String> {
        ironcalc::export::save_to_xlsx(&self.model, path)
            .map_err(|e| format!("Save: {}", e))?;
        Ok(())
    }

    pub fn get_cell(&self, row: usize, col: usize) -> String {
        self.model
            .get_cell_value_by_index(0, row as i32 + 1, col as i32 + 1)
            .map(|v| format!("{}", v))
            .unwrap_or_default()
    }

    pub fn set_cell(&mut self, row: usize, col: usize, value: &str) -> Result<(), String> {
        self.model.set_user_input(0, row as i32 + 1, col as i32 + 1, value)
            .map_err(|e| format!("Set cell: {}", e))?;
        Ok(())
    }

    pub fn to_grid(&self, rows: usize, cols: usize) -> Vec<Vec<String>> {
        let mut grid = Vec::with_capacity(rows);
        for r in 0..rows {
            let mut row = Vec::with_capacity(cols);
            for c in 0..cols {
                row.push(self.get_cell(r, c));
            }
            grid.push(row);
        }
        grid
    }
}

pub fn read_spreadsheet(path: &std::path::Path) -> Result<(Vec<Vec<String>>, usize, usize), String> {
    let ss = Spreadsheet::load(path.to_str().unwrap())?;
    let grid = ss.to_grid(100, 26);
    let rows = grid.len();
    let cols = grid.first().map(|r| r.len()).unwrap_or(0);
    Ok((grid, rows, cols))
}

pub fn write_spreadsheet(path: &std::path::Path, cells: &[Vec<String>]) -> Result<(), String> {
    let mut ss = Spreadsheet::new(cells.len(), cells.first().map(|r| r.len()).unwrap_or(0))?;
    for (r, row) in cells.iter().enumerate() {
        for (c, cell) in row.iter().enumerate() {
            if !cell.is_empty() {
                ss.set_cell(r, c, cell)?;
            }
        }
    }
    ss.save(path.to_str().unwrap())
}
