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


def test_unknown_api_route_returns_404(client):
    # No catch-all route: unknown paths are plain 404s, not 500s.
    assert client.get("/api/v1/does-not-exist").status_code == 404
    assert client.get("/api/v1/assets/1/extra").status_code == 404


def test_cors_only_allows_the_configured_frontend_origin(client):
    # docs/SECURITY.md: no wildcard CORS; only the Vite dev origin.
    allowed = {"Origin": "http://localhost:5173"}
    resp = client.get("/api/v1/ai/status", headers=allowed)
    assert resp.status_code == 200
    assert (
        resp.headers.get("access-control-allow-origin")
        == "http://localhost:5173"
    )

    # An unknown origin gets no allow header on a simple request...
    evil = {"Origin": "https://evil.example"}
    resp = client.get("/api/v1/ai/status", headers=evil)
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers

    # ...and no grant on a preflight either.
    resp = client.options(
        "/api/v1/ai/status",
        headers={**evil, "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in resp.headers

    # The configured origin is granted a preflight.
    resp = client.options(
        "/api/v1/ai/status",
        headers={**allowed, "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert (
        resp.headers.get("access-control-allow-origin")
        == "http://localhost:5173"
    )


def test_date_range_uses_submitted_at_and_skips_nulls(client):
    # P4: earliest/latest must describe RECORDED SUBMISSION DATES, not the
    # record-creation timestamp, and rows without submitted_at are excluded
    # from BOTH the range and the "with a recorded date" count.
    asset = client.post("/api/v1/assets", json={"display_name": "A"}).json()
    # Out-of-order dates: all created within the same second, so a
    # created_at-based range could never produce these bounds.
    client.post(
        "/api/v1/submissions",
        json={
            "asset_id": asset["id"],
            "platform": "Adobe Stock",
            "status": "submitted",
            "submitted_at": "2026-10-05",
        },
    )
    client.post(
        "/api/v1/submissions",
        json={
            "asset_id": asset["id"],
            "platform": "Adobe Stock",
            "status": "submitted",
            "submitted_at": "2026-10-01",
        },
    )
    # No recorded date: must not enter the range or the count.
    client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "ShutterStock", "status": "draft"},
    )

    data = client.get("/api/v1/insights/summary").json()
    assert data["total_submissions"] == 3
    assert data["sample_size"] == 2  # consistent with the range below
    assert data["period_start"] == "2026-10-01"
    assert data["period_end"] == "2026-10-05"


def test_date_range_empty_when_no_recorded_dates(client):
    # One submission exists but has no submitted_at: the range must report
    # NULL honestly (the Dashboard shows "—"), not a fabricated date.
    asset = client.post("/api/v1/assets", json={"display_name": "A"}).json()
    client.post(
        "/api/v1/submissions",
        json={"asset_id": asset["id"], "platform": "Adobe Stock", "status": "draft"},
    )

    data = client.get("/api/v1/insights/summary").json()
    assert data["total_submissions"] == 1
    assert data["sample_size"] == 0
    assert data["period_start"] is None
    assert data["period_end"] is None
