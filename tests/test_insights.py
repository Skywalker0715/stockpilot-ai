# Insights honesty (sample size, recorded data only) and AI status disclosure (Q6).


def test_insights_empty_state(client):
    resp = client.get("/api/v1/insights/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assets"] == 0
    assert data["total_submissions"] == 0
    assert data["sample_size"] == 0
    assert data["period_start"] is None
    assert data["period_end"] is None
    assert data["submissions_by_status"] == {}


def test_insights_counts_from_recorded_data_only(client):
    # Two assets, one archived.
    a1 = client.post("/api/v1/assets", json={"display_name": "A1"}).json()
    a2 = client.post("/api/v1/assets", json={"display_name": "A2"}).json()
    client.patch(f"/api/v1/assets/{a2['id']}", json={"archived": True})

    # Three submissions with different outcomes.
    client.post(
        "/api/v1/submissions",
        json={
            "asset_id": a1["id"],
            "platform": "Adobe Stock",
            "status": "accepted",
            "submitted_at": "2026-10-01",
        },
    )
    client.post(
        "/api/v1/submissions",
        json={
            "asset_id": a1["id"],
            "platform": "Adobe Stock",
            "status": "rejected",
            "submitted_at": "2026-10-02",
            "rejection_category": "duplicate",
        },
    )
    client.post(
        "/api/v1/submissions",
        json={
            "asset_id": a2["id"],
            "platform": "ShutterStock",
            "status": "rejected",
            "submitted_at": "2026-10-03",
        },
    )

    resp = client.get("/api/v1/insights/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assets"] == 2
    assert data["archived_assets"] == 1
    assert data["total_submissions"] == 3
    assert data["submissions_by_status"] == {"accepted": 1, "rejected": 2}
    assert data["submissions_by_platform"] == {"Adobe Stock": 2, "ShutterStock": 1}
    # Uncategorized rejection is reported as uncategorized, not invented.
    assert data["rejections_by_category"] == {
        "duplicate": 1,
        "uncategorized": 1,
    }
    # Sample size counts only submissions with an explicit date (PRD: show n).
    assert data["sample_size"] == 3
    assert data["period_start"] is not None
    assert data["period_end"] is not None


def test_ai_status_reports_not_configured(client):
    # Q6: the app must clearly indicate AI is unavailable and that
    # manual entry works.
    resp = client.get("/api/v1/ai/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_configured"] is False
    assert "manual" in data["message"].lower()


def test_health_and_openapi(client):
    # Basic app liveness + contract generation.
    assert client.get("/openapi.json").status_code == 200
