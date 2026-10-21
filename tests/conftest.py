# Shared test fixtures: each test gets an isolated temporary SQLite database
# and an isolated upload directory (no writes into the repo's uploads/).

import pytest
from fastapi.testclient import TestClient

from app import config


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test_stockpilot.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


@pytest.fixture()
def upload_dir(tmp_path, monkeypatch):
    path = tmp_path / "uploads"
    monkeypatch.setattr(config, "UPLOAD_DIR", path)
    return path


@pytest.fixture()
def ai_key(monkeypatch):
    """Set a fake Cohere API key for a test (and restore on teardown)."""

    def _set(key: str = "test-api-key") -> str:
        monkeypatch.setattr(config, "COHERE_API_KEY", key)
        return key

    return _set


@pytest.fixture()
def no_ai_key(monkeypatch):
    """Force the 'AI not configured' state regardless of the host .env."""
    monkeypatch.setattr(config, "COHERE_API_KEY", "")


@pytest.fixture()
def client(db_path, upload_dir, no_ai_key):
    # The context manager runs the lifespan handler, which applies migrations.
    # no_ai_key keeps status/error tests deterministic; tests that need a key
    # re-set it via the ai_key fixture after this one (monkeypatch is ordered).
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
