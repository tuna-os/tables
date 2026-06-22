// export.rs — Typst export for Tables.
// SPDX-License-Identifier: GPL-3.0-or-later

use crate::engine::Spreadsheet;

/// Export spreadsheet to Typst source (table format).
pub fn to_typst(ss: &Spreadsheet) -> String {
    let grid = ss.to_grid();
    let mut out = String::from("#table(\n  columns: 1,\n");
    for row in &grid {
        out.push_str("  [");
        let cells: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
        out.push_str(&cells.join("], ["));
        out.push_str("],\n");
    }
    out.push_str(")\n");
    out
}

/// Export spreadsheet to PDF via Typst compiler.
pub fn to_pdf(ss: &Spreadsheet, output_path: &str) -> Result<(), String> {
    let src = to_typst(ss);
    let world = typst::World::new(typst::CompilerFeat::default());
    let document = typst::compile(&src, &world)
        .map_err(|e| format!("Typst compile: {:?}", e))?;
    std::fs::write(output_path, &document)
        .map_err(|e| format!("Write PDF: {}", e))?;
    Ok(())
}
