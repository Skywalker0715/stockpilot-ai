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


def test_submission_for_archived_asset_is_allowed(client):
    # Implemented behavior: archiving does not block recording review
    # history; the service checks asset existence only.
    asset = _asset(client, "Archived one")
    assert (
        client.patch(
            f"/api/v1/assets/{asset['id']}", json={"archived": True}
        ).status_code
        == 200
    )
    resp = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock"},
    )
    assert resp.status_code == 201


def test_submission_pagination_and_parameter_validation(client):
    asset = _asset(client)
    for i in range(3):
        client.post(
            "/api/v1/submissions",
            json={"asset_id": asset["id"], "platform": f"P{i}"},
        )

    page1 = client.get(
        "/api/v1/submissions", params={"page": 1, "page_size": 2}
    ).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    page2 = client.get(
        "/api/v1/submissions", params={"page": 2, "page_size": 2}
    ).json()
    assert len(page2["items"]) == 1

    # Invalid parameters are rejected with 422, not silently coerced.
    assert client.get("/api/v1/submissions", params={"page": 0}).status_code == 422
    assert (
        client.get("/api/v1/submissions", params={"page_size": 201}).status_code
        == 422
    )
    # asset_id filter must be a positive integer (Query(gt=0)).
    assert (
        client.get("/api/v1/submissions", params={"asset_id": 0}).status_code
        == 422
    )


def test_submission_create_and_fetch_return_identical_data(client):
    # Schema consistency between POST and GET for submissions.
    asset = _asset(client)
    resp = client.post(
        "/api/v1/submissions",
        json={
            "asset_id": asset["id"],
            "platform": "Adobe Stock",
            "status": "submitted",
            "submitted_at": "2026-10-17",
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    fetched = client.get(f"/api/v1/submissions/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_empty_submission_patch_is_a_noop(client):
    asset = _asset(client)
    created = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock"},
    ).json()
    resp = client.patch(f"/api/v1/submissions/{created['id']}", json={})
    assert resp.status_code == 200
    assert resp.json() == created
    # Empty PATCH on a missing id is still a 404.
    assert client.patch("/api/v1/submissions/999999", json={}).status_code == 404


# ---- permanent delete (DELETE /submissions/{id}) ----------------------------


def test_delete_submission_removes_only_that_record(client):
    asset = _asset(client, "Keeper")
    keep = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock", "status": "submitted"},
    ).json()
    doomed = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "ShutterStock", "status": "rejected"},
    ).json()

    resp = client.delete(f"/api/v1/submissions/{doomed['id']}")
    assert resp.status_code == 200
    # The response echoes the deleted record so the UI can name it.
    assert resp.json()["id"] == doomed["id"]
    assert resp.json()["platform"] == "ShutterStock"

    # Gone from the store...
    assert client.get(f"/api/v1/submissions/{doomed['id']}").status_code == 404
    remaining = client.get("/api/v1/submissions").json()
    assert remaining["total"] == 1
    assert remaining["items"][0]["id"] == keep["id"]
    # ...while the asset and its sibling submission are untouched.
    assert client.get(f"/api/v1/assets/{asset['id']}").status_code == 200
    assert (
        client.get("/api/v1/submissions", params={"asset_id": asset["id"]}).json()["total"]
        == 1
    )


def test_delete_submission_404_and_422(client):
    assert client.delete("/api/v1/submissions/999999").status_code == 404
    assert client.delete("/api/v1/submissions/not-a-number").status_code == 422
    # Deleting twice -> clean 404, no crash.
    asset = _asset(client)
    created = client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock"},
    ).json()
    assert client.delete(f"/api/v1/submissions/{created['id']}").status_code == 200
    assert client.delete(f"/api/v1/submissions/{created['id']}").status_code == 404
