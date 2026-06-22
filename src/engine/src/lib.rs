// tables-engine — Rust spreadsheet engine for Tables.
// SPDX-License-Identifier: GPL-3.0-or-later

use std::ffi::{CStr, CString};
use std::os::raw::c_char;

/// Read an XLSX file and return a CSV string.
/// Called from Python via ctypes.
#[no_mangle]
pub extern "C" fn engine_read_xlsx(path: *const c_char) -> *mut c_char {
    let path = unsafe { CStr::from_ptr(path) }.to_str().unwrap_or("");
    
    let result = match calamine::open_workbook_auto(path) {
        Ok(mut wb) => {
            let mut csv = String::new();
            if let Ok(range) = wb.worksheet_range_at(0) {
                for row in range.rows() {
                    let cells: Vec<String> = row.iter()
                        .map(|c| c.to_string())
                        .collect();
                    csv.push_str(&cells.join(","));
                    csv.push('\n');
                }
            }
            csv
        }
        Err(e) => format!("ERROR: {}", e),
    };

    CString::new(result).unwrap().into_raw()
}

/// Free a string allocated by Rust.
#[no_mangle]
pub extern "C" fn engine_free_string(s: *mut c_char) {
    if !s.is_null() {
        unsafe { let _ = CString::from_raw(s); }
    }
}

/// Evaluate a formula and return the result.
/// Stub — will integrate IronCalc or Formulizer.
#[no_mangle]
pub extern "C" fn engine_eval_formula(formula: *const c_char, inputs_json: *const c_char) -> *mut c_char {
    let formula = unsafe { CStr::from_ptr(formula) }.to_str().unwrap_or("");
    let _inputs = unsafe { CStr::from_ptr(inputs_json) }.to_str().unwrap_or("[]");
    
    // Stub: just echo the formula
    let result = format!("RUST: formula='{}' [stub — IronCalc pending]", formula);
    CString::new(result).unwrap().into_raw()
}
