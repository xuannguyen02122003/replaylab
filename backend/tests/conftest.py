"""Shared test fixtures.

Every test gets a brand-new in-memory SQLite database, so tests never
share data and never touch your real replaylab.db file.
"""

from collections.abc import Iterator
from typing import Any

import pytest
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
