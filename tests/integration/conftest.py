"""Integration fixtures: a real MongoDB, and the real app served by uvicorn on a free local port.

A live server (not Starlette's TestClient) is used on purpose: the concurrency tests fire genuinely parallel HTTP
requests from several threads. Each session uses its own throw-away database that is dropped at the end.
If MongoDB is not reachable every integration test is SKIPPED (reported as not run), never passed.
"""
import os
import socket
import threading
import time
import uuid

import pytest

MONGO_URI = os.getenv("TEST_MONGO_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server():
    from pymongo import MongoClient
    probe = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    try:
        probe.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"MongoDB not reachable at the configured URI ({exc.__class__.__name__}); integration tests NOT RUN")
    db_name = f"attendance_test_{uuid.uuid4().hex[:8]}"
    os.environ["MONGO_URI"] = MONGO_URI
    os.environ["MONGO_DB"] = db_name
    import uvicorn
    from app.main import app

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not srv.started:
        if time.time() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    yield {"url": f"http://127.0.0.1:{port}", "db_name": db_name}
    srv.should_exit = True
    thread.join(timeout=10)
    probe.drop_database(db_name)
    probe.close()


@pytest.fixture(scope="session")
def mongo(server):
    from pymongo import MongoClient
    client = MongoClient(MONGO_URI, tz_aware=True)
    yield client
    client.close()


@pytest.fixture()
def db(server, mongo):
    database = mongo[server["db_name"]]
    database.employees.delete_many({})
    database.attendance_logs.delete_many({})
    return database


@pytest.fixture()
def api(server, db):
    import httpx
    with httpx.Client(base_url=server["url"], timeout=60) as client:
        yield client
