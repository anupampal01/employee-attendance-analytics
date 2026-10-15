"""Loads the stdlib-only helper block of app/main.py (between the BEGIN/END PURE HELPERS markers).

Unit tests use this so the business rules (R1-R10 helpers) can be tested on any machine, with or without FastAPI and
MongoDB installed. It executes the *same source text* that the application runs; nothing is copied or re-implemented.
"""
import pathlib
import types

_SRC = pathlib.Path(__file__).resolve().parent.parent / "app" / "main.py"


def load_pure():
    text = _SRC.read_text(encoding="utf-8")
    begin = text.index("# ===== BEGIN PURE HELPERS =====")
    end = text.index("# ===== END PURE HELPERS =====")
    module = types.ModuleType("attendance_pure")
    exec(compile(text[begin:end], str(_SRC), "exec"), module.__dict__)
    return module
