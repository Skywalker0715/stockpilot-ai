# Submission/review tracking: create, filter, update, rejection notes (FR-04/FR-05).


def _asset(client, name="Test asset"):
    return client.post("/api/v1/assets", json={"display_name": name}).json()


def test_create_submission_and_404_on_missing_asset(client):
    asset = _asset(client)
    resp = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "Adobe Stock"
    assert data["status"] == "draft"

    # Foreign asset id is rejected with 404 (service-level check).
    resp = client.post(
        "/api/v1/submissions",
        json={"asset_id": 999999, "platform": "Adobe Stock"},
    )
    assert resp.status_code == 404


def test_submission_validation(client):
    asset = _asset(client)
    # Invalid status enum.
    resp = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock", "status": "nope"},
    )
    assert resp.status_code == 422
    # Missing platform.
    resp = client.post(
        "/api/v1/submissions", json={"asset_id": asset["id"]}
    )
    assert resp.status_code == 422
    # Invalid status on list filter.
    resp = client.get("/api/v1/submissions", params={"status": "bogus"})
    assert resp.status_code == 422


def test_update_submission_status_and_rejection_note(client):
    asset = _asset(client)
    created = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "ShutterStock"},
    ).json()

    resp = client.patch(
        f"/api/v1/submissions/{created['id']}",
        json={
            "status": "rejected",
            "rejection_note": "Too similar to existing image",
            "rejection_category": "duplicate",
            "reviewed_at": "2026-10-16",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_note"] == "Too similar to existing image"
    assert data["rejection_category"] == "duplicate"

    # The category can be corrected later (PRD: user-correctable).
    resp = client.patch(
        f"/api/v1/submissions/{created['id']}",
        json={"rejection_category": "quality"},
    )
    assert resp.json()["rejection_category"] == "quality"
    # Rejection note can be cleared with explicit null (nullable column).
    resp = client.patch(
        f"/api/v1/submissions/{created['id']}", json={"rejection_note": None}
    )
    assert resp.status_code == 200
    assert resp.json()["rejection_note"] is None

    # Explicit null on NOT NULL fields -> 422, not a DB crash.
    resp = client.patch(
        f"/api/v1/submissions/{created['id']}", json={"platform": None}
    )
    assert resp.status_code == 422
    resp = client.patch(
        f"/api/v1/submissions/{created['id']}", json={"status": None}
    )
    assert resp.status_code == 422

    assert client.patch(
        "/api/v1/submissions/999999", json={"status": "accepted"}
    ).status_code == 404


def test_list_submissions_filters(client):
    a1 = _asset(client, "A1")
    a2 = _asset(client, "A2")
    client.post(
        "/api/v1/submissions",
        json={"asset_id": a1["id"], "platform": "Adobe Stock", "status": "submitted"},
    )
    client.post(
        "/api/v1/submissions",
        json={"asset_id": a2["id"], "platform": "ShutterStock", "status": "accepted"},
    )

    resp = client.get("/api/v1/submissions")
    assert resp.json()["total"] == 2

    resp = client.get("/api/v1/submissions", params={"asset_id": a1["id"]})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["platform"] == "Adobe Stock"

    resp = client.get("/api/v1/submissions", params={"status": "accepted"})
    assert resp.json()["total"] == 1

    resp = client.get(
        "/api/v1/submissions", params={"asset_id": 999999}
    )
    assert resp.json()["total"] == 0  # empty state, not an error


def test_submission_get_by_id(client):
    asset = _asset(client)
    created = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock"},
    ).json()
    resp = client.get(f"/api/v1/submissions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert client.get("/api/v1/submissions/999999").status_code == 404
