// engine.rs — Spreadsheet engine using IronCalc exclusively.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Decision 2026-06-22: IronCalc is the spreadsheet engine.
// - load_from_xlsx / save_to_xlsx for file I/O
// - icalc format for working state (native IronCalc format)
// - No calamine, no rust_xlsxwriter — IronCalc handles everything.

use std::path::{Path, PathBuf};

/// Read an XLSX file via IronCalc, returning cell data as 2D grid.
/// Uses a temp icalc file as intermediate format for cell access.
pub fn read_spreadsheet(path: &Path) -> Result<(Vec<Vec<String>>, usize, usize), String> {
    // IronCalc Model isn't publicly importable, so we convert:
    // XLSX → icalc → parse icalc → grid
    let tmp = std::env::temp_dir().join("ironcalc-tmp.icalc");
    let model = ironcalc::import::load_from_xlsx(
        path.to_str().unwrap(), "en_US", "UTC", "en"
    ).map_err(|e| format!("Read: {}", e))?;
    ironcalc::export::save_to_icalc(&model, tmp.to_str().unwrap())
        .map_err(|e| format!("Export: {}", e))?;

    // Parse icalc (JSON-based format)
    let content = std::fs::read_to_string(&tmp)
        .map_err(|e| format!("Read icalc: {}", e))?;
    let json: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Parse: {}", e))?;

    let sheets = json["sheets"].as_array()
        .ok_or("No sheets in icalc")?;
    let sheet = &sheets[0];
    let cells_arr = sheet["cells"].as_array()
        .ok_or("No cells")?;

    let rows = cells_arr.len();
    let cols = cells_arr.first()
        .and_then(|r| r.as_array())
        .map(|r| r.len())
        .unwrap_or(0);

    let mut cells: Vec<Vec<String>> = Vec::with_capacity(rows);
    for row in cells_arr {
        if let Some(row_arr) = row.as_array() {
            let r: Vec<String> = row_arr.iter()
                .map(|v| v.as_str().unwrap_or("").to_string())
                .collect();
            cells.push(r);
        }
    }
    Ok((cells, rows, cols))
}

/// Write a 2D grid to XLSX via IronCalc.
/// Uses icalc as intermediate: grid → icalc → XLSX.
pub fn write_spreadsheet(path: &Path, cells: &[Vec<String>]) -> Result<(), String> {
    let tmp = std::env::temp_dir().join("ironcalc-out.icalc");
    // Build minimal icalc JSON
    let mut json = serde_json::json!({
        "sheets": [{
            "name": "Sheet1",
            "cells": cells,
            "columns": [],
            "rows": []
        }]
    });
    std::fs::write(&tmp, serde_json::to_string_pretty(&json)
        .map_err(|e| format!("JSON: {}", e))?)
        .map_err(|e| format!("Write icalc: {}", e))?;

    let model = ironcalc::import::load_from_icalc(tmp.to_str().unwrap())
        .map_err(|e| format!("Load icalc: {}", e))?;
    ironcalc::export::save_to_xlsx(&model, path.to_str().unwrap())
        .map_err(|e| format!("Save XLSX: {}", e))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ironcalc_roundtrip() {
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
}
