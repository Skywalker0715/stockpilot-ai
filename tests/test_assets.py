# Asset CRUD + permanent delete, search, filter, archive, validation, and
# pagination (FR-01/FR-02).

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


def test_archived_asset_detail_and_edit_remain_available(client):
    # Implemented behavior: archiving hides the record from the default
    # list only. The record stays fetchable and editable by id (archive is
    # the recoverable soft alternative to DELETE /assets/{id}).
    created = _create(client, title="Original").json()
    assert (
        client.patch(
            f"/api/v1/assets/{created['id']}", json={"archived": True}
        ).status_code
        == 200
    )

    # Hidden from the default list...
    assert client.get("/api/v1/assets").json()["total"] == 0
    # ...but still returned by the detail endpoint.
    resp = client.get(f"/api/v1/assets/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True
    # Editing while archived still works and does not unarchive.
    resp = client.patch(
        f"/api/v1/assets/{created['id']}", json={"title": "Edited"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Edited"
    assert resp.json()["archived"] is True
    # Unarchiving restores it to the default list.
    resp = client.patch(
        f"/api/v1/assets/{created['id']}", json={"archived": False}
    )
    assert resp.json()["archived"] is False
    assert client.get("/api/v1/assets").json()["total"] == 1


def test_unimplemented_routes_and_invalid_path_ids(client):
    # DELETE /assets/{id} is a real endpoint (covered by the delete tests
    # below); POSTing to a detail path is still not a route.
    created = _create(client).json()
    assert client.post(f"/api/v1/assets/{created['id']}").status_code == 405
    # Non-integer path id -> request validation error, not a crash.
    assert client.get("/api/v1/assets/not-a-number").status_code == 422
    assert client.delete("/api/v1/assets/not-a-number").status_code == 422
    # Integer id without a record -> 404.
    assert client.get("/api/v1/assets/0").status_code == 404
    # Unknown deeper path -> 404 (no catch-all route).
    assert client.get("/api/v1/assets/1/extra").status_code == 404


def test_empty_patch_is_a_noop(client):
    created = _create(client, title="Keep me").json()
    resp = client.patch(f"/api/v1/assets/{created['id']}", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Keep me"
    assert data["display_name"] == created["display_name"]
    # Empty PATCH on a missing id is still a 404.
    assert client.patch("/api/v1/assets/999999", json={}).status_code == 404


def test_keyword_count_limit_and_overlong_keyword_dropped(client):
    # Field(max_length=50) on the keywords list rejects oversized input.
    resp = _create(client, keywords=[f"k{i}" for i in range(51)])
    assert resp.status_code == 422
    # Individual keywords longer than 100 chars are dropped by the
    # normalization rule (documented service behavior), not stored.
    resp = _create(client, keywords=["x" * 101, "ok"])
    assert resp.status_code == 201
    assert resp.json()["keywords"] == ["ok"]


def test_search_treats_sql_characters_as_plain_text(client):
    # Search input is parameterized: quotes and LIKE wildcards must not
    # cause errors or match every row.
    _create(client, display_name="Alpha")
    resp = client.get("/api/v1/assets", params={"q": "%' OR '1'='1"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    resp = client.get("/api/v1/assets", params={"q": "' OR 1=1 --"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_asset_create_and_fetch_return_identical_data(client):
    # Schema consistency: what POST returns, GET must reproduce exactly.
    resp = _create(
        client,
        title="T",
        description="D",
        keywords=["one", "Two"],
        category="photo",
        file_reference="C:\\img\\a.jpg",
        media_type="image/jpeg",
    )
    assert resp.status_code == 201
    created = resp.json()
    fetched = client.get(f"/api/v1/assets/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


# ---- permanent delete (DELETE /assets/{id}) ---------------------------------


def test_delete_asset_removes_record_and_returns_counts(client):
    created = _create(client, title="Doomed").json()
    resp = client.delete(f"/api/v1/assets/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["display_name"] == "Sunset over city"
    assert data["deleted_submissions"] == 0
    # No stored image on this record -> null, not a false success/failure.
    assert data["image_removed"] is None
    # Gone from list and detail...
    assert client.get("/api/v1/assets").json()["total"] == 0
    assert client.get(f"/api/v1/assets/{created['id']}").status_code == 404
    # ...and deleting again is a clean 404, not a crash or double count.
    assert client.delete(f"/api/v1/assets/{created['id']}").status_code == 404


def test_delete_asset_cascades_submissions_and_preserves_others(client):
    doomed = _create(client, display_name="Doomed").json()
    keeper = _create(client, display_name="Keeper").json()
    for asset_id, platform in (
        (doomed["id"], "Adobe Stock"),
        (doomed["id"], "Shutterstock"),
        (keeper["id"], "Adobe Stock"),
    ):
        resp = client.post(
            "/api/v1/submissions",
            json={"asset_id": asset_id, "platform": platform, "status": "submitted"},
        )
        assert resp.status_code == 201

    resp = client.delete(f"/api/v1/assets/{doomed['id']}")
    assert resp.status_code == 200
    assert resp.json()["deleted_submissions"] == 2

    # Both linked submissions are gone (FK ON DELETE CASCADE)...
    assert (
        client.get(
            "/api/v1/submissions", params={"asset_id": doomed["id"]}
        ).json()["total"]
        == 0
    )
    assert client.get("/api/v1/submissions").json()["total"] == 1
    # ...while the unrelated asset and its submission are untouched.
    assert client.get(f"/api/v1/assets/{keeper['id']}").status_code == 200
    kept = client.get(
        "/api/v1/submissions", params={"asset_id": keeper["id"]}
    ).json()
    assert kept["total"] == 1
    assert kept["items"][0]["platform"] == "Adobe Stock"


def test_delete_unknown_asset_returns_404(client):
    assert client.delete("/api/v1/assets/999999").status_code == 404
    assert client.delete("/api/v1/assets/0").status_code == 404
