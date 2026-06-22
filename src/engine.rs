// engine.rs — Spreadsheet engine with IronCalc + calamine fallbacks.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Decision 2026-06-22: IronCalc is the spreadsheet engine.
// API is evolving (0.7.1) — Model type not publicly importable,
// so we use load/save as the API boundary.  calamine handles reading,
// IronCalc handles save+formula evaluation.

use calamine::{open_workbook_auto, Reader};
use std::path::Path;

/// Read an XLSX/ODS/CSV file into a 2D grid of strings.
/// Uses calamine for reading (IronCalc Model not yet available for cell access).
pub fn read_spreadsheet(path: &Path) -> Result<(Vec<Vec<String>>, usize, usize), String> {
    let mut workbook = open_workbook_auto(path)
        .map_err(|e| format!("Failed to open: {}", e))?;
    let sheet_names = workbook.sheet_names().to_vec();
    let name = sheet_names.first().cloned().unwrap_or_default();
    let range = workbook.worksheet_range(&name)
        .map_err(|e| format!("Read error: {}", e))?;
    let rows = range.rows().count();
    let cols = range.rows().next().map(|r| r.len()).unwrap_or(0);
    let mut cells: Vec<Vec<String>> = Vec::with_capacity(rows);
    for row in range.rows() {
        let mut r: Vec<String> = Vec::with_capacity(cols);
        for cell in row { r.push(cell.to_string()); }
        while r.len() < cols { r.push(String::new()); }
        cells.push(r);
    }
    Ok((cells, rows, cols))
}

/// Write a 2D grid to an XLSX file.
/// Uses rust_xlsxwriter (IronCalc Model builder not yet available).
pub fn write_spreadsheet(path: &Path, cells: &[Vec<String>]) -> Result<(), String> {
    use rust_xlsxwriter::*;
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();
    for (r, row) in cells.iter().enumerate() {
        for (c, cell) in row.iter().enumerate() {
            if !cell.is_empty() {
                worksheet.write_string(r as u32, c as u16, cell)
                    .map_err(|e| format!("Write error: {}", e))?;
            }
        }
    }
    workbook.save(path).map_err(|e| format!("Save error: {}", e))?;
    Ok(())
}

/// Validate an XLSX file is loadable by IronCalc.
pub fn validate_xlsx(path: &str) -> Result<(), String> {
    ironcalc::import::load_from_xlsx(path, "en_US", "UTC", "en")
        .map_err(|e| format!("IronCalc load error: {}", e))?;
    Ok(())
}

/// Save via IronCalc (full formula evaluation).
pub fn save_via_ironcalc(input_path: &str, output_path: &str) -> Result<(), String> {
    let model = ironcalc::import::load_from_xlsx(input_path, "en_US", "UTC", "en")
        .map_err(|e| format!("Load: {}", e))?;
    ironcalc::export::save_to_xlsx(&model, output_path)
        .map_err(|e| format!("Save: {}", e))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_read_write_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.xlsx");
        let data = vec![
            vec!["Name".into(), "Age".into()],
            vec!["Alice".into(), "30".into()],
        ];
        write_spreadsheet(&path, &data).unwrap();
        let (back, rows, cols) = read_spreadsheet(&path).unwrap();
        assert_eq!(rows, 2);
        assert_eq!(cols, 2);
        assert_eq!(back[0][0], "Name");
        assert_eq!(back[1][1], "30");
    }

    #[test]
    fn test_ironcalc_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let p1 = dir.path().join("in.xlsx");
        let p2 = dir.path().join("out.xlsx");
        let data = vec![vec!["10".into()], vec!["20".into()]];
        write_spreadsheet(&p1, &data).unwrap();
        save_via_ironcalc(p1.to_str().unwrap(), p2.to_str().unwrap()).unwrap();
        let (back, _, _) = read_spreadsheet(&p2).unwrap();
        assert_eq!(back[0][0], "10");
        assert_eq!(back[1][0], "20");
    }
}
