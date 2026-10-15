"""Static conformance: the OpenAPI document FastAPI generates must contain every path, method, success status code
and query/path parameter (with the same required flag) that openapi.yaml defines. Needs fastapi + pyyaml; no MongoDB."""
import pathlib

import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("fastapi")

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))


def _params(op):
    out = {}
    for p in op.get("parameters", []):
        if "$ref" in p:
            p = SPEC["components"]["parameters"][p["$ref"].split("/")[-1]]
        out[p["name"]] = bool(p.get("required"))
    return out


def test_paths_methods_status_codes_and_parameters():
    from app.main import app
    generated = app.openapi()["paths"]
    for path, ops in SPEC["paths"].items():
        assert path in generated, f"missing path {path}"
        for method, op in ops.items():
            assert method in generated[path], f"missing {method.upper()} {path}"
            gen_op = generated[path][method]
            for code in (c for c in op["responses"] if c.startswith("2")):
                assert code in gen_op["responses"], f"{method.upper()} {path}: success status {code} missing"
            gen_params = {p["name"]: bool(p.get("required")) for p in gen_op.get("parameters", [])}
            for name, required in _params(op).items():
                assert name in gen_params, f"{method.upper()} {path}: parameter {name} missing"
                assert gen_params[name] == required, f"{method.upper()} {path}: required flag of {name} differs"


def test_no_undocumented_routes():
    from app.main import app
    spec_paths = set(SPEC["paths"])
    extra = {p for p in app.openapi()["paths"] if p not in spec_paths}
    assert not extra, f"routes not in the contract: {extra}"
