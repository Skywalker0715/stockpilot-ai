# Cohere analysis: status disclosure, consent, mocked provider responses,
# output validation/normalization, and error mapping. Fully offline: Cohere
# is mocked via httpx.MockTransport through cohere_service._transport_factory.

import base64
import io
import json
import os

import httpx
import pytest
from PIL import Image

from app import config
from app.services import cohere_service

# ---- helpers ---------------------------------------------------------------


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client) -> dict:
    resp = client.post(
        "/api/v1/uploads",
        files={"file": ("img.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201
    return resp.json()


def _cohere_ok_body(text: str) -> dict:
    return {
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        }
    }


_GOOD_DRAFT = {
    "title": "Wooden cabin beside an alpine lake at sunrise",
    "description": "A rustic cabin reflects in still mountain water.",
    "category": "Travel",
    "keywords": ["cabin", "lake", "mountains", "sunrise"],
}


def _mock_provider(
    monkeypatch,
    *,
    status_code: int = 200,
    body: dict | None = None,
    text: str | None = None,
    raw: bytes | None = None,
    handler=None,
):
    """Route all Cohere calls to a canned MockTransport response."""
    if handler is None:
        if raw is not None:
            payload = raw
        elif body is not None:
            payload = json.dumps(body).encode()
        else:
            payload = json.dumps(
                _cohere_ok_body(text or json.dumps(_GOOD_DRAFT))
            ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, content=payload)

    def factory() -> httpx.BaseTransport:
        return httpx.MockTransport(handler)

    monkeypatch.setattr(cohere_service, "_transport_factory", factory)


def _analyze(client, asset_id: int, consent: bool = True) -> httpx.Response:
    return client.post(
        "/api/v1/ai/analyze",
        json={"asset_id": asset_id, "consent": consent},
    )


# ---- status disclosure -----------------------------------------------------


def test_status_reports_configured_state(client, ai_key):
    resp = client.get("/api/v1/ai/status")
    assert resp.status_code == 200
    assert resp.json()["ai_configured"] is False  # client fixture: no key
    assert "manually" in resp.json()["message"].lower()

    ai_key()
    resp = client.get("/api/v1/ai/status")
    data = resp.json()
    assert data["ai_configured"] is True
    assert config.AI_MODEL in data["message"]
    assert data["model"] == config.AI_MODEL


def test_status_never_exposes_api_key(client, ai_key):
    ai_key("super-secret-key-123")
    resp = client.get("/api/v1/ai/status")
    assert b"super-secret-key-123" not in resp.content


# ---- consent and preconditions --------------------------------------------


def test_analyze_requires_consent(client, ai_key):
    ai_key()
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id, consent=False)
    assert resp.status_code == 422  # rejected by request validation


# ---- mocked success path ---------------------------------------------------


def test_analyze_success_returns_draft_and_saves_nothing(
    client, ai_key, monkeypatch
):
    ai_key()
    _mock_provider(monkeypatch)
    asset_id = _upload(client)["asset"]["id"]

    resp = _analyze(client, asset_id)
    assert resp.status_code == 200
    draft = resp.json()
    assert draft["asset_id"] == asset_id
    assert draft["title"] == _GOOD_DRAFT["title"]
    assert draft["keywords"] == _GOOD_DRAFT["keywords"]
    assert draft["model"] == config.AI_MODEL

    # DRAFT ONLY: the stored asset was not modified by analysis.
    asset = client.get(f"/api/v1/assets/{asset_id}").json()
    assert asset["title"] is None
    assert asset["keywords"] == []
    assert asset["metadata_origin"] == "manual"


def test_mocked_request_contains_image_and_schema(
    client, ai_key, monkeypatch
):
    """The outgoing request must carry the real image bytes; the API key
    travels in a header, never in the URL."""
    ai_key()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_cohere_ok_body(json.dumps(_GOOD_DRAFT)))

    _mock_provider(monkeypatch, handler=handler)
    asset_id = _upload(client)["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 200

    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers.get("authorization") == "Bearer test-api-key"
    assert "api_key" not in captured["url"].lower()  # key never in the URL
    assert "/v2/chat" in captured["url"]
    assert config.AI_MODEL == captured["body"]["model"]
    assert captured["body"]["stream"] is False
    content = captured["body"]["messages"][0]["content"]
    text_part, image_part = content[0], content[1]
    assert text_part["type"] == "text"
    inline = image_part["image_url"]
    assert inline["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(inline["url"].split(",", 1)[1]) == _png_bytes()
    # Structured JSON output requested.
    rf = captured["body"]["response_format"]
    assert rf["type"] == "json_object"
    assert rf["schema"]["type"] == "object"
    assert "title" in rf["schema"]["required"]
    # Key never in URL and bearer header used (header names are case-insensitive).
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers.get("authorization") == "Bearer test-api-key"


# ---- output validation / normalization ------------------------------------


def test_keywords_normalized_deduped_and_capped(client, ai_key, monkeypatch):
    ai_key()
    many = [f"kw{i}" for i in range(60)] + ["KW0", "  ", "kw1", "x" * 200]
    _mock_provider(monkeypatch, text=json.dumps(dict(_GOOD_DRAFT, keywords=many)))
    asset_id = _upload(client)["asset"]["id"]
    draft = _analyze(client, asset_id).json()
    # capped at 50; duplicates (case-insensitive), empties, and over-long
    # entries removed; order preserved.
    assert len(draft["keywords"]) == 50
    assert draft["keywords"][0] == "kw0"
    assert len({k.lower() for k in draft["keywords"]}) == 50


def test_long_fields_truncated_and_blanks_dropped(
    client, ai_key, monkeypatch
):
    ai_key()
    payload = {
        "title": "T" * 500,
        "description": " " * 10,
        "category": "C" * 300,
        "keywords": ["ok"],
    }
    _mock_provider(monkeypatch, text=json.dumps(payload))
    asset_id = _upload(client)["asset"]["id"]
    draft = _analyze(client, asset_id).json()
    assert len(draft["title"]) == 300
    assert draft["description"] is None  # blank -> null
    assert len(draft["category"]) == 100


@pytest.mark.parametrize(
    "text,expected_fragment",
    [
        ("this is not json", "valid JSON"),
        (json.dumps({"description": "x", "keywords": ["a"]}), "title"),
        (json.dumps({"title": "ok", "keywords": []}), "keywords"),
        (json.dumps(["a", "b"]), "object"),
    ],
)
def test_malformed_model_output_rejected(
    client, ai_key, monkeypatch, text, expected_fragment
):
    ai_key()
    _mock_provider(monkeypatch, text=text)
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id)
    assert resp.status_code == 502
    assert expected_fragment.lower() in resp.json()["detail"].lower()


def test_markdown_fenced_json_still_parsed(client, ai_key, monkeypatch):
    ai_key()
    fenced = "```json\n" + json.dumps(_GOOD_DRAFT) + "\n```"
    _mock_provider(monkeypatch, text=fenced)
    asset_id = _upload(client)["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 200


# ---- max_tokens truncation (observed against the real Cohere API) ----------


# Cut off mid-keyword-array, exactly what Cohere returns when generation hits
# max_tokens. title/description/category and the leading keywords are
# complete; only the closing brackets are missing. Note the partial string at
# the end, which is where the token cap actually landed.
_TRUNCATED_KEYWORDS_TEXT = (
    '{\n  "title": "Solid green abstract background",\n'
    '  "description": "A flat, uniform green field.",\n'
    '  "category": "Abstract",\n'
    '  "keywords": [\n    "green",\n    "background",\n    "abstract",\n'
    '    "color gree'
)


def _truncated_body(finish_reason: str = "MAX_TOKENS") -> dict:
    return {
        "finish_reason": finish_reason,
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": _TRUNCATED_KEYWORDS_TEXT}],
        },
    }


def test_truncated_json_repaired_when_provider_reports_max_tokens(
    client, ai_key, monkeypatch
):
    """A max_tokens-truncated response is valid output minus its closing
    brackets. keywords is the last key in the schema, so the complete fields
    must be returned as a draft instead of a blanket 502."""
    ai_key()
    _mock_provider(monkeypatch, body=_truncated_body())
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id)
    assert resp.status_code == 200
    draft = resp.json()
    assert draft["title"] == "Solid green abstract background"
    assert draft["description"] == "A flat, uniform green field."
    assert draft["category"] == "Abstract"
    # The dangling partial string ("color gree") is dropped, never guessed.
    assert draft["keywords"] == ["green", "background", "abstract"]


def test_truncated_json_without_max_tokens_still_rejected(
    client, ai_key, monkeypatch
):
    """The repair must not generalise: identical malformed output that the
    provider did NOT attribute to max_tokens stays an honest 502."""
    ai_key()
    _mock_provider(monkeypatch, body=_truncated_body(finish_reason="COMPLETE"))
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id)
    assert resp.status_code == 502
    assert "valid json" in resp.json()["detail"].lower()


def test_repair_declines_when_truncation_splits_a_key_and_value(
    client, ai_key, monkeypatch
):
    """Stopping between a key and its value leaves nothing safe to keep, so
    the honest error is preserved rather than a lossy guess."""
    ai_key()
    body = {
        "finish_reason": "MAX_TOKENS",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": '{"title": "ok", "keywords": ["a"], "category":',
                }
            ],
        },
    }
    _mock_provider(monkeypatch, body=body)
    asset_id = _upload(client)["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 502


def test_analyze_404_unknown_asset_and_400_without_image(client, ai_key):
    ai_key()
    assert _analyze(client, 999999).status_code == 404
    record_only = client.post(
        "/api/v1/assets", json={"display_name": "no image"}
    ).json()
    resp = _analyze(client, record_only["id"])
    assert resp.status_code == 400
    assert "no uploaded image" in resp.json()["detail"]


def test_analyze_without_api_key_returns_503_actionable(client):
    # client fixture forces no_ai_key.
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id)
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "COHERE_API_KEY" in detail
    assert ".env" in detail


# ---- latency guards: downsize, prompt instruction, token budget, timeout ----


def _noise_png(width: int, height: int) -> bytes:
    """A large, incompressible PNG so downsizing measurably shrinks payload."""
    raw = os.urandom(width * height * 3)
    buf = io.BytesIO()
    Image.frombytes("RGB", (width, height), raw).save(buf, format="PNG")
    return buf.getvalue()


def test_large_image_is_downscaled_reencoded_and_declared_jpeg(
    client, ai_key, monkeypatch
):
    """An image over the max side must be capped, re-encoded as JPEG, and
    the data URL must declare image/jpeg (not the original upload type)."""
    ai_key()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_cohere_ok_body(json.dumps(_GOOD_DRAFT)))

    _mock_provider(monkeypatch, handler=handler)
    big = _noise_png(1600, 1200)
    resp = client.post(
        "/api/v1/uploads", files={"file": ("big.png", big, "image/png")}
    )
    assert resp.status_code == 201
    asset_id = resp.json()["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 200

    content = captured["body"]["messages"][0]["content"]
    inline = content[1]["image_url"]
    assert inline["url"].startswith("data:image/jpeg;base64,")
    sent = base64.b64decode(inline["url"].split(",", 1)[1])
    with Image.open(io.BytesIO(sent)) as img:
        assert img.format == "JPEG"
        assert max(img.size) <= cohere_service.MAX_IMAGE_SIDE_PX
    # Payload is materially smaller than the original upload.
    assert len(sent) < len(big) // 2


def test_request_carries_json_instruction_detail_and_token_budget(
    client, ai_key, monkeypatch
):
    ai_key()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_cohere_ok_body(json.dumps(_GOOD_DRAFT)))

    _mock_provider(monkeypatch, handler=handler)
    asset_id = _upload(client)["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 200

    body = captured["body"]
    # Cohere-documented JSON instruction must appear in the prompt text.
    prompt = body["messages"][0]["content"][0]["text"]
    assert cohere_service._JSON_INSTRUCTION in prompt
    # Bounded model output so a stall cannot balloon the response.
    assert body["max_tokens"] == cohere_service.MAX_RESPONSE_TOKENS
    # Greedy decoding: unconstrained sampling produced runaway keyword lists
    # that hit the token cap and returned truncated JSON (see truncation
    # tests above).
    assert body["temperature"] == cohere_service.TEMPERATURE
    # Low-detail image input to cut vision latency.
    inline = body["messages"][0]["content"][1]["image_url"]
    assert inline["detail"] == "low"


def test_timeout_is_decomposed_per_transport_leg(client, ai_key, monkeypatch):
    """The Cohere client must get an httpx.Timeout with each leg (connect,
    read, write) bounded by the configured limit, not a bare scalar."""
    ai_key()
    captured = {}
    real_client = httpx.Client

    def spy_client(*args, **kwargs):
        if isinstance(kwargs.get("transport"), httpx.MockTransport):
            captured["timeout"] = kwargs.get("timeout")
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", spy_client)
    _mock_provider(monkeypatch)
    asset_id = _upload(client)["asset"]["id"]
    assert _analyze(client, asset_id).status_code == 200

    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    limit = config.AI_TIMEOUT_SECONDS
    assert timeout.connect == limit
    assert timeout.read == limit
    assert timeout.write == limit


def test_provider_timeout_maps_to_504(client, ai_key, monkeypatch):
    ai_key()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated stall", request=request)

    _mock_provider(monkeypatch, handler=handler)
    asset_id = _upload(client)["asset"]["id"]
    resp = _analyze(client, asset_id)
    assert resp.status_code == 504
    detail = resp.json()["detail"]
    assert f"{config.AI_TIMEOUT_SECONDS:g}" in detail
    assert "seconds" in detail


def test_undecodable_image_bytes_rejected_before_network(ai_key):
    ai_key()
    with pytest.raises(cohere_service.CohereServiceError) as excinfo:
        cohere_service.analyze_image(b"definitely-not-an-image", "image/png")
    assert excinfo.value.status_code == 502
    assert "could not be decoded" in excinfo.value.message
