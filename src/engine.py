# engine.py — Python FFI wrapper for the Rust tables-engine.
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Loads the compiled libtables_engine.so via ctypes and exposes
# read_xlsx() and eval_formula() to the Python GUI layer.
#
# Build the Rust engine with:  cd src/engine && cargo build --release

import ctypes
import os
import sys

_ENGINE = None


def _load():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    # Search paths for the compiled .so
    candidates = [
        os.path.join(os.path.dirname(__file__), 'engine',
                     'target', 'release', 'libtables_engine.so'),
        os.path.join(os.path.dirname(__file__), 'engine',
                     'target', 'debug', 'libtables_engine.so'),
    ]
    for path in candidates:
        if os.path.exists(path):
            _ENGINE = ctypes.CDLL(path)
            _ENGINE.engine_read_xlsx.restype = ctypes.c_char_p
            _ENGINE.engine_read_xlsx.argtypes = [ctypes.c_char_p]
            _ENGINE.engine_free_string.argtypes = [ctypes.c_char_p]
            _ENGINE.engine_eval_formula.restype = ctypes.c_char_p
            _ENGINE.engine_eval_formula.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            return _ENGINE
    raise FileNotFoundError(
        'Rust engine not built. Run: cd src/engine && cargo build --release')


def read_xlsx(path):
    """Read an XLSX file and return CSV text."""
    eng = _load()
    result = eng.engine_read_xlsx(path.encode('utf-8'))
    text = ctypes.c_char_p(result).value.decode('utf-8')
    eng.engine_free_string(result)
    return text


def eval_formula(formula, inputs=None):
    """Evaluate a formula with optional inputs (JSON list)."""
    eng = _load()
    inputs_json = json.dumps(inputs or [])
    result = eng.engine_eval_formula(
        formula.encode('utf-8'),
        inputs_json.encode('utf-8'))
    text = ctypes.c_char_p(result).value.decode('utf-8')
    eng.engine_free_string(result)
    return text


if __name__ == '__main__':
    import json
    print('Rust engine test:')
    try:
        csv = read_xlsx('/tmp/test.xlsx')
        print(f'  read_xlsx: {csv[:100]}')
    except Exception as e:
        print(f'  read_xlsx: {e}')
    print(f'  eval: {eval_formula("=SUM(A1:A3)", [1,2,3])}')
