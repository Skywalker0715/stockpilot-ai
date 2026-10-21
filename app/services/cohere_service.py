# Cohere vision integration for stock metadata generation.
#
# Uses the Chat API v2 with inline base64 image data (data URLs) and
# structured JSON output (response_format json_object + JSON schema).
# Verified against official docs (docs.cohere.com, Oct 2026):
#   POST {base}/v2/chat        header: Authorization: Bearer <COHERE_API_KEY>
#   image: content items {type: "image_url", image_url: {url: "data:<mime>;base64,..."}}
#   structured output: response_format {"type": "json_object", "schema": {...}}
# Default model: config.AI_MODEL (command-a-vision-07-2025), overridable via
# STOCKPILOT_AI_MODEL. If this account cannot access that model or it does not
# support image input, analysis fails with an actionable error instead of
# silently falling back to a text-only model.
#
# Failure policy: every non-success outcome raises CohereServiceError with an
# actionable message. Analysis is never reported as successful unless Cohere
# returned a parseable, schema-valid response.

import base64
import io
import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app import config

# Test seam: tests swap this for httpx.MockTransport to run offline.
# Production default (None) uses the real network transport.
_transport_factory: Callable[[], httpx.BaseTransport | None] = lambda: None

# Per-role API limit for the vision call. Cohere's image inputs are large;
# bounding the image to a max side keeps the request small, fast, and
# predictable over the HTTP transport. 1280 px max side is a good tradeoff:
# enough detail for stock photos, small enough to stay under latency/timeout.
MAX_IMAGE_SIDE_PX = 1280

# Model-level budget for the vision response (Cohere image inputs consume
# vision tokens on top of the text). Kept bounded so a stall cannot balloon
# past the transport timeout.
#
# Measured (Oct 2026): a COMPLIANT response with 50 keywords peaked at 1205
# output tokens, so the original 1024 budget truncated perfectly valid output
# and surfaced as "not valid JSON". 2048 gives ~2x headroom over that peak;
# the worst observed run (a runaway keyword list) reaches the cap in ~44s,
# still inside the 60s default transport timeout.
MAX_RESPONSE_TOKENS = 2048

# Pin sampling to greedy decoding. Measured on the same image 5x: default
# temperature produced a runaway keyword list that hit the token cap in 3 of
# 5 runs (finish_reason=MAX_TOKENS -> truncated JSON -> 502), while
# temperature=0 completed every run in ~6s. The prompt asks for 30-50
# keywords but nothing in Cohere's schema can enforce it (minItems/maxItems
# are unsupported), so unconstrained sampling occasionally emits an
# unbounded list. Deterministic decoding removes that failure mode for
# ordinary photos.
TEMPERATURE = 0.0

# Structured JSON output is documented to require an explicit instruction in
# the message to produce JSON. This phrase is the Cohere-recommended form.
_JSON_INSTRUCTION = "Generate a JSON object"


def _resize_image_to_max_side(data: bytes, max_side: int = MAX_IMAGE_SIDE_PX) -> bytes:
    """Return a JPEG-encoded copy of the bytes with the longest side capped.

    Down-scaling before base64/Cohere keeps the request small and fast.
    If the image cannot be decoded, the caller gets a real error rather than a
    silently dropped or malformed image.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError):
        raise CohereServiceError(
            502,
            "The uploaded image could not be decoded. Upload a valid JPG, PNG, or WebP.",
        ) from None

    if width <= max_side and height <= max_side:
        return data

    ratio = min(max_side / width, max_side / height)
    new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
    resized = img.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    # Re-encode as JPEG for a compact, consistent payload regardless of the
    # original file format. Quality 85 is a good latency/detail balance.
    resized.convert("RGB").save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


PROMPT = (
    "You generate metadata for stock photo and stock illustration listings. "
    "Analyze the image carefully and "
    + _JSON_INSTRUCTION
    + " with exactly these keys:\n"
    '"title": a specific, objective, searchable stock title of at most 15 '
    "words (max 280 characters); no quotes, hype, or claims about model releases\n"
    '"description": one or two factual sentences (max 3500 characters) '
    "describing what is visible and its potential use\n"
    '"category": the single best stock category (max 90 characters), e.g. '
    "Business, Nature, Food, Travel, Technology, People, Abstract\n"
    '"keywords": an array of 30 to 50 relevant search keywords in order of '
    "relevance, most important first; lowercase where natural, single words "
    "or short phrases, no duplicates, no special characters\n"
    "Base every field only on what you can actually see in the image."
)


# JSON Schema for Cohere Structured Outputs (Chat API v2 response_format.schema).
# Only features supported by Cohere's schema subset are used (no minItems/
# maxItems, no string length limits): cardinality and length rules are enforced
# server-side in parse_metadata instead.
_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "category": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "description", "category", "keywords"],
    "additionalProperties": False,
}

_MARKDOWN_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n|\n```\s*$")


class CohereServiceError(Exception):
    """An actionable error safe to return from the AI API route."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def parse_metadata(text: str, model: str | None = None) -> dict[str, Any]:
    """Parse and normalize the model's JSON output into a metadata draft.

    Raises CohereServiceError(502) on malformed or incomplete output.
    """
    cleaned = _strip_fences(text)
    try:
        data = json.loads(cleaned)
    except ValueError:
        raise CohereServiceError(
            502, "Cohere returned a response that is not valid JSON. Try again."
        ) from None
    if not isinstance(data, dict):
        raise CohereServiceError(
            502, "Cohere returned JSON that is not an object. Try again."
        )
    title = data.get("title")
    description = data.get("description")
    category = data.get("category")
    keywords = data.get("keywords")

    if not isinstance(title, str) or not title.strip():
        raise CohereServiceError(
            502, "Cohere's response is missing a usable title. Try again."
        )
    if description is not None and not isinstance(description, str):
        raise CohereServiceError(
            502, "Cohere's response contains an invalid description. Try again."
        )
    if category is not None and not isinstance(category, str):
        raise CohereServiceError(
            502, "Cohere's response contains an invalid category. Try again."
        )
    if not isinstance(keywords, list) or not all(
        isinstance(k, str) for k in keywords
    ):
        raise CohereServiceError(
            502, "Cohere's response contains no usable keywords. Try again."
        )

    normalized_keywords = _normalize_keywords(keywords)[:50]
    if not normalized_keywords:
        raise CohereServiceError(
            502, "Cohere's response contains no usable keywords. Try again."
        )

    return {
        "title": title.strip()[:300],
        "description": (description.strip()[:3500] if description.strip() else None),
        "category": (category.strip()[:100] if category.strip() else None),
        "keywords": normalized_keywords,
    }


def _close_truncated_json(text: str) -> str | None:
    """Close a JSON document that the provider cut off mid-stream.

    Cohere occasionally emits an unbounded `keywords` array (the prompt asks
    for 30-50 entries but its structured-output schema cannot enforce
    minItems/maxItems) and generation is then stopped by `max_tokens`. The
    result is real, valid output that is simply missing its closing
    brackets -- `keywords` is the LAST key in the schema, so title,
    description, category and the leading keywords are all complete.

    This never invents data: it only appends the closers for brackets the
    model already opened. The repaired string is re-validated in full by
    parse_metadata, so a repair that yields anything other than a complete,
    usable draft still raises an honest error.

    Returns the repaired text, or None when the prefix cannot be closed
    safely (caller must then surface the original error).
    """
    stack: list[str] = []
    in_string = False
    escaped = False
    string_start = -1
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            string_start = i
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                return None
            stack.pop()

    # Everything already closed: this was not a truncation, nothing to repair.
    if not stack:
        return None

    if in_string:
        # The cap landed inside a string literal: drop that partial string.
        text = text[:string_start]

    trimmed = text.rstrip()
    while trimmed.endswith(","):
        trimmed = trimmed[:-1].rstrip()
    # A trailing colon means we stopped between a key and its value; there is
    # nothing safe to keep from that tail.
    if trimmed.endswith(":"):
        return None

    candidate = trimmed + "".join(
        "}" if opener == "{" else "]" for opener in reversed(stack)
    )
    try:
        json.loads(candidate)
    except ValueError:
        return None
    return candidate


def analyze_image(
    data: bytes,
    media_type: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> dict:
    """Send an image to Cohere and return a validated metadata draft dict.

    Raises CohereServiceError for missing config, network failures, timeouts,
    provider errors, unsupported models, and malformed model output.
    """
    key = (api_key if api_key is not None else config.COHERE_API_KEY).strip()
    if not key:
        raise CohereServiceError(
            503,
            "AI generation is not configured: set COHERE_API_KEY in .env "
            "(get a key at https://dashboard.cohere.com/api-keys) and restart "
            "the backend. Manual metadata editing always works.",
        )
    active_model = (model or config.AI_MODEL).strip()

    # Resize before encoding so a large original does not bloat the payload
    # and make the request slow to send and slow for Cohere to read.
    image_bytes = _resize_image_to_max_side(data)
    if image_bytes is not data:
        # The resizer re-encodes as JPEG; the data URL must declare the
        # actually encoded format rather than the original upload type.
        media_type = "image/jpeg"

    image_url = (
        f"data:{media_type or 'image/jpeg'};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )

    request_json = {
        "model": active_model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                            # Low detail materially cuts latency and price
                            # for the same scene; suitable for stock metadata.
                            "detail": "low",
                        },
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object", "schema": _RESPONSE_SCHEMA},
        "temperature": TEMPERATURE,
        "max_tokens": MAX_RESPONSE_TOKENS,
    }

    url = f"{config.COHERE_BASE_URL}/v2/chat"
    # Decompose the timeout so a slow response body cannot be cut off by a
    # single fixed whole-request ceiling: allow up to the config limit for
    # the entire request, but carve out a hard send/read/write budget so a
    # stalled body is still bounded in practice.
    timeout = httpx.Timeout(
        config.AI_TIMEOUT_SECONDS,
        connect=config.AI_TIMEOUT_SECONDS,
        read=config.AI_TIMEOUT_SECONDS,
        write=config.AI_TIMEOUT_SECONDS,
    )
    diagnostics: dict[str, Any] = {
        "url": url,
        "timeout_seconds": config.AI_TIMEOUT_SECONDS,
        "status_code": None,
        "request_duration_ms": None,
        "error_message": None,
    }
    started = time.monotonic()
    try:
        with httpx.Client(
            timeout=timeout, transport=_transport_factory()
        ) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=request_json,
            )
        diagnostics["status_code"] = resp.status_code
        diagnostics["request_duration_ms"] = (time.monotonic() - started) * 1000
    except httpx.TimeoutException:
        diagnostics["error_message"] = (
            f"Timed out after {config.AI_TIMEOUT_SECONDS:.0f}s"
        )
        raise CohereServiceError(
            504,
            f"Cohere did not answer within {config.AI_TIMEOUT_SECONDS:g} "
            "seconds. Try again.",
        ) from None
    except httpx.TransportError:
        diagnostics["error_message"] = "Network error"
        raise CohereServiceError(
            502,
            "Could not reach the Cohere API. Check your internet "
            "connection and try again.",
        ) from None
    finally:
        # Retain sanitized diagnostics for local inspection without exposing
        # the API key, image bytes, or encoded image payload.
        if not hasattr(config, "_diag_logged"):
            config._diag_logged = []
        config._diag_logged.append(diagnostics)

    _raise_for_status(resp, active_model)
    try:
        body = resp.json()
    except ValueError:
        raise CohereServiceError(
            502, "Cohere returned an unreadable response. Try again."
        ) from None

    try:
        content = body["message"]["content"]
        text = next(
            item["text"]
            for item in content
            if item.get("type") == "text" and isinstance(item.get("text"), str)
        )
    except (KeyError, TypeError, StopIteration):
        raise CohereServiceError(
            502, "Cohere returned no metadata text. Try again."
        ) from None
    try:
        return parse_metadata(text, active_model)
    except CohereServiceError:
        # The provider stopped generation at max_tokens: the JSON is a valid
        # prefix missing its closing brackets. Recover the complete fields
        # rather than reporting "not valid JSON" for output we can use.
        if body.get("finish_reason") != "MAX_TOKENS":
            raise
        repaired = _close_truncated_json(_strip_fences(text))
        if repaired is None:
            raise
        return parse_metadata(repaired, active_model)


def _provider_message(resp: httpx.Response) -> str:
    """Return a short provider error message without leaking request data."""
    try:
        body = resp.json()
        message = body.get("message", "")
        if isinstance(message, str) and message:
            return message[:500]
    except (ValueError, AttributeError):
        pass
    return resp.text[:300] if resp.text else "no error body"


def _raise_for_status(resp: httpx.Response, model: str) -> None:
    if resp.status_code < 400:
        return
    if resp.status_code == 429:
        raise CohereServiceError(
            429, "Cohere rate limit reached. Wait a moment and try again."
        )
    if resp.status_code in (401, 403):
        raise CohereServiceError(
            502,
            "Cohere rejected the API key. Check COHERE_API_KEY in .env "
            "(get a key at https://dashboard.cohere.com/api-keys) and "
            "restart the backend. Manual metadata editing always works.",
        )
    if resp.status_code == 404:
        raise CohereServiceError(
            502,
            f"Cohere model '{model}' was not found or does not support this "
            "request. Check STOCKPILOT_AI_MODEL "
            "(https://docs.cohere.com/docs/image-inputs).",
        )
    if resp.status_code == 400:
        raise CohereServiceError(
            502,
            f"Cohere rejected the request: {_provider_message(resp)}. "
            "Check the image and try again.",
        )
    raise CohereServiceError(
        502, f"Cohere service error (HTTP {resp.status_code}). Try again later."
    )


def _strip_fences(text: str) -> str:
    """Remove an optional markdown code fence surrounding the JSON."""
    stripped = text.strip()
    stripped = _MARKDOWN_FENCE.sub("", stripped)
    return stripped


def _normalize_keywords(value) -> list[str]:
    """Trim, drop empties/over-long entries, dedupe case-insensitively,
    preserve first spelling and order."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in value:
        if not isinstance(raw, str):
            continue
        word = raw.strip()
        if not word or len(word) > 100:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(word)
    return result


# ---------------------------------------------------------------------------
# Vision Insights: image analysis beyond Generate's metadata draft
# ---------------------------------------------------------------------------

# Structured output schema for the vision-insights analysis. Every field is an
# AI-generated observation or inference and is labeled as such in the UI;
# none of it is measured market demand, search volume, sales volume, or
# ranking data.
VISION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "visual_attributes": {
            "type": "object",
            "properties": {
                "objects": {"type": "array", "items": {"type": "string"}},
                "scene": {"type": "array", "items": {"type": "string"}},
                "dominant_colors": {"type": "array", "items": {"type": "string"}},
                "lighting": {"type": ["string", "null"]},
                "mood": {"type": ["string", "null"]},
                "composition": {"type": ["string", "null"]},
                "orientation": {"type": ["string", "null"]},
                "copy_space": {"type": ["string", "null"]},
            },
            "required": [
                "objects",
                "scene",
                "dominant_colors",
                "lighting",
                "mood",
                "composition",
                "orientation",
                "copy_space",
            ],
            "additionalProperties": False,
        },
        "commercial_use_ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "use_case": {"type": "string"},
                    "fit": {"type": ["string", "null"]},
                },
                "required": ["use_case"],
                "additionalProperties": False,
            },
        },
        "keyword_gap_analysis": {
            "type": "object",
            "properties": {
                "existing_keywords": {"type": "array", "items": {"type": "string"}},
                "suggested_missing": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": ["string", "null"]},
            },
            "required": [
                "existing_keywords",
                "suggested_missing",
                "reasoning",
            ],
            "additionalProperties": False,
        },
        "metadata_quality_review": {
            "type": "object",
            "properties": {
                "title_assessment": {"type": ["string", "null"]},
                "keyword_issues": {"type": "array", "items": {"type": "string"}},
                "description_assessment": {"type": ["string", "null"]},
                "unsupported_terms": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "title_assessment",
                "keyword_issues",
                "description_assessment",
                "unsupported_terms",
            ],
            "additionalProperties": False,
        },
        "actionable_recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "visual_attributes",
        "commercial_use_ideas",
        "keyword_gap_analysis",
        "metadata_quality_review",
        "actionable_recommendations",
    ],
    "additionalProperties": False,
}

VISION_PROMPT = """You are a careful stock-photo analyst. Analyze the supplied image and return
ONLY a JSON object matching the requested schema. Do not add markdown fences or
extra prose.

You are given the image plus the asset's existing metadata keywords (if any).

1. visual_attributes: OBSERVABLE image content only.
   - objects: concrete objects/people/substances visible (max 20).
   - scene: the setting/place (max 10).
   - dominant_colors: the most noticeable colors (max 8).
   - lighting: e.g. "bright daylight", "soft indoor", "low light", "golden hour".
   - mood: e.g. "calm", "energetic", "nostalgic", "neutral".
   - composition: e.g. "centered subject", "rule of thirds", "close-up", "wide shot".
   - orientation: "portrait", "landscape", or "square".
   - copy_space: e.g. "plenty of clean negative space for text", "little copy space".
   Describe what is actually visible. Do not infer unshown content.

2. commercial_use_ideas: PLAUSIBLE use cases (website hero, blog illustration,
   advertising, presentation, social media). Label implicitly as suggestions by
   keeping them general and conditional ("could work as", "suited for"). NEVER
   claim guaranteed commercial demand, sales volume, search volume, or ranking.
   Max 10 ideas, each with a use_case and an optional short fit note.

3. keyword_gap_analysis: compare the existing keywords against the visual
   attributes and suggest missing RELEVANT keywords (no duplicates of existing
   ones, no unsupported claims). Include existing_keywords, suggested_missing,
   and a brief reasoning string.

4. metadata_quality_review: honest, concise review of the existing metadata.
   - title_assessment: vague? specific? accurate?
   - keyword_issues: repetitive, over-broad, or off-topic keywords.
   - description_assessment: does it match the image?
   - unsupported_terms: terms not visibly supported by the image.
   Be direct but neutral; do not invent faults.

5. actionable_recommendations: concise, image-specific improvements to metadata
   wording or discoverability (max 15 short items).

Existing keywords (may be empty): {existing_keywords}
"""

# Explicit output skeleton appended to VISION_PROMPT.
#
# Cohere's structured-output mode does not guarantee that the model returns an
# *instance* of the supplied schema. With the deeply nested vision schema the
# model can reply with the schema itself (echoing "type"/"properties"/
# "required" and filling the properties with placeholder strings). The parser
# correctly rejects that as unusable output, but the request still fails for
# the user. Restating the expected shape as a concrete JSON example makes the
# model fill the structure instead of repeating it.
#
# This constant is concatenated rather than appended to VISION_PROMPT because
# it contains literal braces, which would break str.format().
_VISION_OUTPUT_SKELETON = """
Return a single JSON object with EXACTLY these five top-level keys, in this
exact shape:
{
  "visual_attributes": {"objects": ["..."], "scene": ["..."], "dominant_colors": ["..."], "lighting": "...", "mood": "...", "composition": "...", "orientation": "portrait|landscape|square", "copy_space": "..."},
  "commercial_use_ideas": [{"use_case": "...", "fit": "..."}],
  "keyword_gap_analysis": {"existing_keywords": ["..."], "suggested_missing": ["..."], "reasoning": "..."},
  "metadata_quality_review": {"title_assessment": "...", "keyword_issues": ["..."], "description_assessment": "...", "unsupported_terms": ["..."]},
  "actionable_recommendations": ["..."]
}
Replace every "..." with a value you actually observe in the image. Return the
filled object only. Never output the schema, and never output the keys "type",
"properties", "required", or "additionalProperties".
"""

def parse_vision_insights(text: str, model: str | None = None) -> dict[str, Any]:
    """Parse and normalize the model's vision-insights JSON output.

    Raises CohereServiceError(502) on malformed or incomplete output. Keyword
    lists are normalized (trimmed, de-duplicated, capped) but never invented.
    """
    cleaned = _strip_fences(text)
    try:
        data = json.loads(cleaned)
    except ValueError:
        raise CohereServiceError(
            502, "Cohere returned a response that is not valid JSON. Try again."
        ) from None
    if not isinstance(data, dict):
        raise CohereServiceError(
            502, "Cohere returned JSON that is not an object. Try again."
        ) from None

    # Detect the "schema echo" failure mode: the model repeats the JSON Schema
    # instead of returning an instance of it. The echoed document has
    # "type"/"properties"/"required" at the top level and none of the expected
    # analysis keys, so it is rejected here with an explicit message instead
    # of the misleading "missing usable visual attributes".
    if "visual_attributes" not in data and (
        "properties" in data or "required" in data
    ):
        raise CohereServiceError(
            502,
            "Cohere returned the response schema instead of an analysis. "
            "Try again.",
        ) from None

    def _str_list(value, cap: int) -> list[str]:
        if not isinstance(value, list):
            return []
        return _normalize_keywords([v for v in value if isinstance(v, str)])[:cap]

    visual = data.get("visual_attributes")
    if not isinstance(visual, dict):
        raise CohereServiceError(
            502, "Cohere's response is missing usable visual attributes. Try again."
        ) from None

    gap = data.get("keyword_gap_analysis")
    if not isinstance(gap, dict):
        raise CohereServiceError(
            502, "Cohere's response is missing keyword gap analysis. Try again."
        ) from None

    review = data.get("metadata_quality_review")
    if not isinstance(review, dict):
        raise CohereServiceError(
            502, "Cohere's response is missing metadata quality review. Try again."
        ) from None

    ideas = data.get("commercial_use_ideas")
    if not isinstance(ideas, list):
        ideas = []
    clean_ideas = []
    for idea in ideas:
        if isinstance(idea, dict) and isinstance(idea.get("use_case"), str):
            clean_ideas.append(
                {
                    "use_case": idea["use_case"].strip()[:120],
                    "fit": (
                        idea["fit"].strip()[:200]
                        if isinstance(idea.get("fit"), str) and idea["fit"].strip()
                        else None
                    ),
                }
            )

    recommendations = data.get("actionable_recommendations")
    if not isinstance(recommendations, list):
        recommendations = []
    clean_recommendations = [
        str(r).strip()[:200]
        for r in recommendations
        if isinstance(r, str) and r.strip()
    ][:15]

    def _opt_str(value, cap: int) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()[:cap]
        return None

    return {
        "visual_attributes": {
            "objects": _str_list(visual.get("objects"), 20),
            "scene": _str_list(visual.get("scene"), 10),
            "dominant_colors": _str_list(visual.get("dominant_colors"), 8),
            "lighting": _opt_str(visual.get("lighting"), 200),
            "mood": _opt_str(visual.get("mood"), 200),
            "composition": _opt_str(visual.get("composition"), 200),
            "orientation": _opt_str(visual.get("orientation"), 40),
            "copy_space": _opt_str(visual.get("copy_space"), 200),
        },
        "commercial_use_ideas": clean_ideas[:10],
        "keyword_gap_analysis": {
            "existing_keywords": _str_list(gap.get("existing_keywords"), 50),
            "suggested_missing": _str_list(gap.get("suggested_missing"), 30),
            "reasoning": _opt_str(gap.get("reasoning"), 1000),
        },
        "metadata_quality_review": {
            "title_assessment": _opt_str(review.get("title_assessment"), 500),
            "keyword_issues": _str_list(review.get("keyword_issues"), 20),
            "description_assessment": _opt_str(review.get("description_assessment"), 1000),
            "unsupported_terms": _str_list(review.get("unsupported_terms"), 20),
        },
        "actionable_recommendations": clean_recommendations,
    }

def analyze_vision_insights(
    data: bytes,
    media_type: str,
    *,
    existing_keywords: list[str] | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> dict:
    """Send an image to Cohere and return a validated vision-insights dict.

    Reuses the same image resizing, base64 data-URL, transport, and error
    handling as analyze_image. Raises CohereServiceError for missing config,
    network failures, timeouts, provider errors, unsupported models, and
    malformed model output.
    """
    key = (api_key if api_key is not None else config.COHERE_API_KEY).strip()
    if not key:
        raise CohereServiceError(
            503,
            "AI generation is not configured: set COHERE_API_KEY in .env "
            "(get a key at https://dashboard.cohere.com/api-keys) and restart "
            "the backend. Manual metadata editing always works.",
        )
    active_model = (model or config.AI_MODEL).strip()

    image_bytes = _resize_image_to_max_side(data)
    if image_bytes is not data:
        media_type = "image/jpeg"

    image_url = (
        f"data:{media_type or 'image/jpeg'};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )

    existing = _normalize_keywords(existing_keywords or [])[:50]
    prompt = VISION_PROMPT.format(existing_keywords=", ".join(existing) or "none")
    # The skeleton is appended after formatting so its literal braces survive.
    prompt = f"{prompt}{_VISION_OUTPUT_SKELETON}"

    request_json = {
        "model": active_model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                            "detail": "low",
                        },
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object", "schema": VISION_RESPONSE_SCHEMA},
        "temperature": TEMPERATURE,
        "max_tokens": MAX_RESPONSE_TOKENS,
    }

    url = f"{config.COHERE_BASE_URL}/v2/chat"
    timeout = httpx.Timeout(
        config.AI_TIMEOUT_SECONDS,
        connect=config.AI_TIMEOUT_SECONDS,
        read=config.AI_TIMEOUT_SECONDS,
        write=config.AI_TIMEOUT_SECONDS,
    )
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout, transport=_transport_factory()) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=request_json,
            )
    except httpx.TimeoutException as exc:
        raise CohereServiceError(
            504,
            f"Cohere timed out after {config.AI_TIMEOUT_SECONDS:g} seconds. "
            "Try again with a smaller image or later.",
        ) from exc
    except httpx.RequestError as exc:
        raise CohereServiceError(
            502, f"Cannot reach Cohere: {exc}. Check your connection."
        ) from exc

    _raise_for_status(resp, active_model)

    try:
        body = resp.json()
    except ValueError:
        raise CohereServiceError(
            502, "Cohere returned an unreadable response. Try again."
        ) from None

    try:
        content = body["message"]["content"]
        text = next(
            item["text"]
            for item in content
            if item.get("type") == "text" and isinstance(item.get("text"), str)
        )
    except (KeyError, TypeError, StopIteration):
        raise CohereServiceError(
            502, "Cohere returned no analysis text. Try again."
        ) from None

    return parse_vision_insights(text, active_model)

