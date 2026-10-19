"""Shared test fixtures.

Every test gets a brand-new in-memory SQLite database, so tests never
share data and never touch your real replaylab.db file.
"""

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(**overrides: Any) -> Settings:
    values = {
        "database_url": "sqlite://",
        "cors_origins": ["http://localhost:5173"],
        "max_request_bytes": 5 * 1024 * 1024,
        "enable_scenario_runner": True,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(make_settings())
    with TestClient(app) as test_client:  # "with" runs startup (creates tables)
        yield test_client


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url():
    port = free_port()
    app = create_app(make_settings())
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
