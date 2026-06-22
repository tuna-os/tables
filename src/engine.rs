// engine.rs — Spreadsheet engine using IronCalc exclusively.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Decision: IronCalc only. No calamine, no rust_xlsxwriter.
// Strategy: store Model as serialized bytes in memory to avoid
// lifetime issues.  Serialize/deserialize on load/save.

use std::path::Path;

pub struct Spreadsheet {
    /// IronCalc Model serialized to bytes (icalc format)
    data: Vec<u8>,
    rows: usize,
    cols: usize,
}

impl Spreadsheet {
    pub fn new(rows: usize, cols: usize) -> Result<Self, String> {
        let model = ironcalc_base::Model::new_empty("untitled", "en", "UTC", "en")
            .map_err(|e| format!("Create: {}", e))?;
        let data = model.to_bytes()
            .map_err(|e| format!("Serialize: {}", e))?;
        Ok(Self { data, rows, cols })
    }

    /// Rehydrate the model from bytes.
    fn model(&self) -> Result<ironcalc_base::Model<'static>, String> {
        ironcalc_base::Model::from_bytes(&self.data, "en", "UTC", "en")
            .map_err(|e| format!("Deserialize: {}", e))
    }

    /// Save and reload to persist changes.
    fn commit(&mut self) -> Result<(), String> {
        let m = self.model()?;
        self.data = m.to_bytes().map_err(|e| format!("Serialize: {}", e))?;
        Ok(())
    }

    pub fn set_cell(&mut self, row: usize, col: usize, value: &str) -> Result<(), String> {
        let mut m = self.model()?;
        m.set_user_input(0, row as i32 + 1, col as i32 + 1, value)
            .map_err(|e| format!("Set: {}", e))?;
        self.data = m.to_bytes().map_err(|e| format!("Serialize: {}", e))?;
        Ok(())
    }

    pub fn get_cell(&self, row: usize, col: usize) -> String {
        if let Ok(m) = self.model() {
            m.get_cell_value_by_index(0, row as i32 + 1, col as i32 + 1)
                .map(|v| format!("{}", v))
                .unwrap_or_default()
        } else {
            String::new()
        }
    }

    pub fn to_grid(&self) -> Vec<Vec<String>> {
        let mut grid = Vec::with_capacity(self.rows);
        for r in 0..self.rows {
            let mut row = Vec::with_capacity(self.cols);
            for c in 0..self.cols {
                row.push(self.get_cell(r, c));
            }
            grid.push(row);
        }
        grid
    }
}

pub fn read_spreadsheet(path: &Path) -> Result<Spreadsheet, String> {
    let s = path.to_str().ok_or("Invalid path")?;
    let model = ironcalc::import::load_from_xlsx(s, "en_US", "UTC", "en")
        .map_err(|e| format!("Load: {}", e))?;
    let data = model.to_bytes().map_err(|e| format!("Serialize: {}", e))?;
    // Approximate dimensions from metadata
    let sheet = model.get_sheet(0).ok().flatten()
        .map(|s| (s.rows() as usize, s.columns() as usize))
        .unwrap_or((100, 26));
    Ok(Spreadsheet { data, rows: sheet.0, cols: sheet.1 })
}

pub fn write_spreadsheet(path: &Path, ss: &Spreadsheet) -> Result<(), String> {
    let m = ss.model()?;
    ironcalc::export::save_to_xlsx(&m, path.to_str().unwrap())
        .map_err(|e| format!("Save: {}", e))?;
    Ok(())
}
