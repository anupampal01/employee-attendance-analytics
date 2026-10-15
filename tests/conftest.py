"""Shared pytest configuration.

  pytest tests/unit          -> pure business-rule tests, no MongoDB needed
  pytest tests/integration   -> needs a reachable MongoDB (MONGO_URI); skipped, not failed, when there is none
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs a running MongoDB")
