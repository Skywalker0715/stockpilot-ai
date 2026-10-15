# Asset CRUD, search, filter, archive, validation, and pagination (FR-01/FR-02).

from app import db


def _create(client, **overrides):
    payload = {"display_name": "Sunset over city", **overrides}
    resp = client.post("/api/v1/assets", json=payload)
    return resp


def test_create_asset_returns_201_and_defaults(client):
    resp = _create(client, keywords=["  City ", "city", "TEA ", ""])
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "Sunset over city"
    # Keyword normalization: trimmed, de-duplicated case-insensitively,
    # empties dropped, first spelling preserved.
    assert data["keywords"] == ["City", "TEA"]
    assert data["metadata_origin"] == "manual"
    assert data["archived"] is False
    assert data["id"] > 0


def test_create_asset_validation_errors(client):
    # Empty display_name violates min_length.
    assert _create(client, display_name="").status_code == 422
    # Missing display_name entirely.
    assert client.post("/api/v1/assets", json={}).status_code == 422
    # Too-long display_name.
    assert _create(client, display_name="x" * 201).status_code == 422
    # Non-list keywords.
    assert _create(client, keywords="coffee").status_code == 422


def test_get_asset_and_404(client):
    created = _create(client).json()
    resp = client.get(f"/api/v1/assets/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert client.get("/api/v1/assets/999999").status_code == 404


def test_update_asset_partial(client):
    created = _create(client).json()
    resp = client.patch(
        f"/api/v1/assets/{created['id']}",
        json={"title": "Sunset", "keywords": [" skyline"], "archived": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Sunset"
    assert data["keywords"] == ["skyline"]
    assert data["archived"] is True
    assert data["display_name"] == "Sunset over city"  # untouched


def test_update_asset_rejects_explicit_null(client):
    created = _create(client).json()
    resp = client.patch(
        f"/api/v1/assets/{created['id']}", json={"display_name": None}
    )
    assert resp.status_code == 422
    resp = client.patch(f"/api/v1/assets/{created['id']}", json={"archived": None})
    assert resp.status_code == 422
    resp = client.patch(f"/api/v1/assets/{created['id']}", json={"keywords": None})
    assert resp.status_code == 422
    # Null clears a genuinely nullable field.
    resp = client.patch(
        f"/api/v1/assets/{created['id']}", json={"title": None}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] is None
    assert client.patch("/api/v1/assets/999999", json={"title": "x"}).status_code == 404


def test_search_filter_and_archive_visibility(client):
    _create(client, display_name="Coffee shop", keywords=["coffee"], category="photo")
    _create(client, display_name="Forest path", keywords=["nature"], category="art")

    # Default list hides archived records.
    resp = client.get("/api/v1/assets")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2

    # Text search matches display_name and keywords.
    resp = client.get("/api/v1/assets", params={"q": "coffee"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["display_name"] == "Coffee shop"

    # Category filter.
    resp = client.get("/api/v1/assets", params={"category": "art"})
    assert resp.json()["total"] == 1

    # Archiving removes from default view, visible with archived=true.
    coffee_id = client.get(
        "/api/v1/assets", params={"q": "coffee"}
    ).json()["items"][0]["id"]
    client.patch(f"/api/v1/assets/{coffee_id}", json={"archived": True})
    assert client.get("/api/v1/assets").json()["total"] == 1
    archived = client.get("/api/v1/assets", params={"archived": True})
    assert archived.json()["total"] == 1
    assert archived.json()["items"][0]["id"] == coffee_id


def test_pagination(client):
    for i in range(3):
        _create(client, display_name=f"Asset {i}")
    resp = client.get("/api/v1/assets", params={"page": 1, "page_size": 2})
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    resp = client.get("/api/v1/assets", params={"page": 2, "page_size": 2})
    assert len(resp.json()["items"]) == 1
    # Invalid page parameters are rejected.
    assert client.get("/api/v1/assets", params={"page": 0}).status_code == 422
    assert client.get(
        "/api/v1/assets", params={"page_size": 1000}
    ).status_code == 422


def test_records_persist_across_restart(db_path):
    # Phase: create data with one app instance...
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/assets", json={"display_name": "Persistent asset"}
        ).json()
        asset_id = created["id"]

    # ...simulate a restart: a new app instance on the same database file.
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/assets/{asset_id}")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Persistent asset"


def test_database_has_foreign_keys_enabled(db_path):
    conn = db.connect()
    try:
        # This test talks to the database directly, so apply migrations first.
        db.run_migrations(conn)
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1
        # Attempting to violate FK enforcement directly must fail.
        import sqlite3

        try:
            conn.execute(
                "INSERT INTO submissions (asset_id, platform) VALUES (999999, 'x')"
            )
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        assert raised, "foreign key violation should raise IntegrityError"
    finally:
        conn.close()
