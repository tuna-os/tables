// engine.rs — Spreadsheet engine: read/write XLSX/CSV/ODS.
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Uses calamine for reading and rust_xlsxwriter for writing.
// Formula engine (IronCalc/Formulizer) will be integrated later.

use std::path::Path;

/// Read an XLSX/ODS/CSV file and return tab-separated text for display.
pub fn read_spreadsheet(path: &Path) -> Result<String, String> {
    let mut workbook = calamine::open_workbook_auto(path)
        .map_err(|e| format!("Failed to open: {}", e))?;

    let mut result = String::new();
    let sheet_names = workbook.sheet_names().to_vec();
    let name = sheet_names.first().cloned().unwrap_or_default();

    if let Ok(range) = workbook.worksheet_range(&name) {
        for row in range.rows() {
            let cells: Vec<String> = row.iter()
                .map(|c| c.to_string())
                .collect();
            result.push_str(&cells.join("\t"));
            result.push('\n');
        }
    }
    Ok(result)
}

/// Write tab-separated text to an XLSX file.
pub fn write_spreadsheet(path: &Path, data: &str) -> Result<(), String> {
    use rust_xlsxwriter::*;
    let mut workbook = Workbook::new();
    let worksheet = workbook.add_worksheet();

    for (row_idx, line) in data.lines().enumerate() {
        for (col_idx, cell) in line.split('\t').enumerate() {
            worksheet
                .write_string(row_idx as u32, col_idx as u16, cell)
                .map_err(|e| format!("Write error: {}", e))?;
        }
    }

    workbook.save(path).map_err(|e| format!("Save error: {}", e))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.xlsx");
        let data = "Name\tAge\nAlice\t30\nBob\t25\n";
        write_spreadsheet(&path, data).unwrap();
        let back = read_spreadsheet(&path).unwrap();
        // Normalize newlines
        assert_eq!(back.trim(), data.trim());
    }
}
