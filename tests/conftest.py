# Shared test fixtures: each test gets an isolated temporary SQLite database.

import pytest
from fastapi.testclient import TestClient

from app import config


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test_stockpilot.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


@pytest.fixture()
def client(db_path):
    # The context manager runs the lifespan handler, which applies migrations.
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
