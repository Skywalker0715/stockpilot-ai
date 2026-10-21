"""Vision Insights API validation and persistence tests using a mocked Cohere response."""

import io
import json

import httpx
from PIL import Image

from app import db
from app.services import cohere_service


def _image_bytes() -> bytes:
    image = io.BytesIO()
    Image.new("RGB", (8, 8), (20, 30, 40)).save(image, format="PNG")
    return image.getvalue()


def _analysis() -> dict:
    return {
        "visual_attributes": {
            "objects": ["tree"], "scene": ["forest"], "dominant_colors": ["green"],
            "lighting": "daylight", "mood": "calm", "composition": "wide shot",
            "orientation": "landscape", "copy_space": "open sky",
        },
        "commercial_use_ideas": [{"use_case": "Could work as a nature blog header", "fit": "Wide composition"}],
        "keyword_gap_analysis": {
            "existing_keywords": ["forest"],
            "suggested_missing": ["Forest", "trees", "woodland", "forest"],
            "reasoning": "Visible trees and woodland setting.",
        },
        "metadata_quality_review": {
            "title_assessment": "The title is specific.", "keyword_issues": [],
            "description_assessment": None, "unsupported_terms": [],
        },
        "actionable_recommendations": ["Use a specific location only if known."],
    }


def _mock_vision(monkeypatch, text: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": [{"type": "text", "text": text}]}},
        )

    monkeypatch.setattr(cohere_service, "_transport_factory", lambda: httpx.MockTransport(handler))


def _mock_vision_capturing(monkeypatch, text: str) -> dict:
    """Mock Cohere and capture the outgoing request body."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"message": {"content": [{"type": "text", "text": text}]}},
        )

    monkeypatch.setattr(cohere_service, "_transport_factory", lambda: httpx.MockTransport(handler))
    return captured


def _upload(client) -> int:
    response = client.post(
        "/api/v1/uploads", files={"file": ("forest.png", _image_bytes(), "image/png")}
    )
    assert response.status_code == 201
    return response.json()["asset"]["id"]


def test_vision_analysis_persists_result_without_changing_metadata(client, ai_key, monkeypatch):
    ai_key()
    _mock_vision(monkeypatch, json.dumps(_analysis()))
    asset_id = _upload(client)

    response = client.post(
        f"/api/v1/vision/analyze/{asset_id}",
        json={"asset_id": asset_id, "consent": True},
    )
    assert response.status_code == 201
    record = response.json()
    assert record["asset_id"] == asset_id
    assert record["visual_attributes"]["objects"] == ["tree"]
    assert record["keyword_gap_analysis"]["suggested_missing"] == ["Forest", "trees", "woodland"]
    assert client.get(f"/api/v1/vision/insights/{asset_id}").json()["id"] == record["id"]

    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    assert asset["keywords"] == []
    assert asset["title"] is None


def test_vision_malformed_provider_output_is_reported(client, ai_key, monkeypatch):
    ai_key()
    _mock_vision(monkeypatch, "not valid json")
    asset_id = _upload(client)
    response = client.post(
        f"/api/v1/vision/analyze/{asset_id}",
        json={"asset_id": asset_id, "consent": True},
    )
    assert response.status_code == 502
    assert "valid json" in response.json()["detail"].lower()


def test_vision_analysis_requires_consent(client, ai_key):
    ai_key()
    asset_id = _upload(client)
    response = client.post(
        f"/api/v1/vision/analyze/{asset_id}",
        json={"asset_id": asset_id, "consent": False},
    )
    assert response.status_code == 422


def test_vision_prompt_states_the_expected_output_shape(client, ai_key, monkeypatch):
    """The prompt must spell out the JSON shape.

    Cohere's structured-output mode can answer with the schema itself instead
    of an instance of it, which the parser rejects. The prompt therefore has to
    restate the expected shape explicitly.
    """
    ai_key()
    captured = _mock_vision_capturing(monkeypatch, json.dumps(_analysis()))
    asset_id = _upload(client)

    response = client.post(
        f"/api/v1/vision/analyze/{asset_id}",
        json={"asset_id": asset_id, "consent": True},
    )
    assert response.status_code == 201

    prompt = captured["body"]["messages"][0]["content"][0]["text"]
    for key in (
        "visual_attributes",
        "commercial_use_ideas",
        "keyword_gap_analysis",
        "metadata_quality_review",
        "actionable_recommendations",
    ):
        assert key in prompt


def test_vision_schema_echo_is_reported_clearly(client, ai_key, monkeypatch):
    """A schema echo must not surface as a misleading 'missing attributes' error."""
    ai_key()
    echoed = json.dumps(
        {
            "type": "object",
            "properties": {"visual_attributes": {"type": "object"}},
            "required": ["visual_attributes"],
            "additionalProperties": False,
        }
    )
    _mock_vision(monkeypatch, echoed)
    asset_id = _upload(client)

    response = client.post(
        f"/api/v1/vision/analyze/{asset_id}",
        json={"asset_id": asset_id, "consent": True},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "schema" in detail.lower()
    assert "missing usable visual attributes" not in detail.lower()


def test_delete_asset_cascades_its_vision_insights(client, ai_key, monkeypatch):
    """Deleting an asset must remove its persisted vision insights.

    The insights live in their own table (migration 003) with
    `asset_id REFERENCES assets(id) ON DELETE CASCADE`, so the rows go away
    with the asset instead of being orphaned.
    """
    ai_key()
    _mock_vision(monkeypatch, json.dumps(_analysis()))
    doomed = _upload(client)
    keeper = _upload(client)

    for asset_id in (doomed, keeper):
        response = client.post(
            f"/api/v1/vision/analyze/{asset_id}",
            json={"asset_id": asset_id, "consent": True},
        )
        assert response.status_code == 201

    # Both assets have a persisted analysis before the delete.
    assert client.get(f"/api/v1/vision/insights/{doomed}").status_code == 200
    assert client.get(f"/api/v1/vision/insights/{keeper}").status_code == 200

    resp = client.delete(f"/api/v1/assets/{doomed}")
    assert resp.status_code == 200

    # The deleted asset's insights are gone...
    assert client.get(f"/api/v1/vision/insights/{doomed}").status_code == 404
    # ...while the unrelated asset keeps its analysis untouched.
    assert client.get(f"/api/v1/vision/insights/{keeper}").status_code == 200

    # Verify at the database level that no orphaned insight row survives.
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT asset_id FROM vision_insights ORDER BY asset_id"
        ).fetchall()
    finally:
        conn.close()
    assert [row["asset_id"] for row in rows] == [keeper]
