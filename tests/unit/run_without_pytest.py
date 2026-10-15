"""Fallback runner: executes every test_* function in tests/unit without pytest (stdlib only)."""
import importlib.util
import pathlib
import sys
import traceback

failed = passed = 0
for path in sorted(pathlib.Path(__file__).parent.glob("test_*.py")):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)()
            passed += 1
            print(f"PASS {path.name}::{name}")
        except Exception:
            failed += 1
            print(f"FAIL {path.name}::{name}")
            traceback.print_exc()
print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
