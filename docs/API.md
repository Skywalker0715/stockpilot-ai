# API Reference

Base URL: `http://127.0.0.1:8000` · All endpoints are under `/api/v1`.
Interactive OpenAPI docs: http://127.0.0.1:8000/docs

The API is **unauthenticated** and intended for `localhost` only
(ADR-005). CORS is restricted to the Vite dev server origin.

## Conventions

- Request and response bodies are JSON (`application/json`), except
  `POST /api/v1/uploads`, which uses `multipart/form-data`.
- Errors use FastAPI's standard shape: `{"detail": "<message>"}` for handled
  errors, and a `detail` array of field errors for `422` validation failures.
- Timestamps are the raw SQLite `datetime('now')` strings, e.g.
  `"2026-10-20 08:31:53"` (UTC, space-separated, **no** `T` separator and no
  `Z` suffix). They are returned as plain strings, not parsed into datetimes.
- List endpoints are paginated with `page` (1-based) and `page_size`
  (max 200) and return `{items, total, page, page_size}`.

---

## Assets

### `GET /api/v1/assets`

List asset records.

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `q` | string (max 200) | — | Case-insensitive contains over display_name, title, keywords, category |
| `category` | string (max 100) | — | Exact match |
| `archived` | boolean | `false` | `true` returns only archived rows, `false` only active rows |
| `has_image` | boolean | — | `true` = has an uploaded image, `false` = record-only asset |
| `page` | integer ≥ 1 | `1` | |
| `page_size` | integer 1–200 | `50` | |

**200** → `{items: AssetOut[], total: int, page: int, page_size: int}`

### `POST /api/v1/assets`

Create an asset record without an image.

**Body** (`AssetCreate`): `display_name` (required, 1–200 chars), `file_reference`
(≤1024), `media_type` (≤100), `title` (≤300), `description` (≤4000),
`keywords` (array, ≤50 entries), `category` (≤100).

Keywords are normalized on write: trimmed, empty entries dropped, entries
longer than 100 chars dropped, and duplicates removed case-insensitively while
preserving first spelling and order.

**201** → `AssetOut` · **422** → validation error

### `GET /api/v1/assets/{asset_id}`

**200** → `AssetOut` · **404** → `Asset not found`

### `PATCH /api/v1/assets/{asset_id}`

Partial update. Only the fields present in the body are changed.

**Body** (`AssetUpdate`): `display_name`, `file_reference`, `media_type`,
`title`, `description`, `keywords`, `category`, `archived`,
`metadata_origin` (`manual` | `imported` | `ai_suggested`).

- `display_name`, `archived`, and `metadata_origin` are **not nullable**;
  sending `null` returns `422` instead of a database error.
- `keywords` and `title` are nullable; send `[]` to clear keywords.
- `archived: true` is how archiving works — there is no separate archive
  endpoint. Archiving hides the row from the default list but keeps the record
  and all metadata intact; set `archived: false` to restore it.

**200** → `AssetOut` · **404** → `Asset not found`

### `DELETE /api/v1/assets/{asset_id}`

Permanently delete an asset. This is destructive and irreversible.

Order of operations: the asset row is deleted (linked submissions **and vision
insights** cascade via the foreign key) and the transaction commits **first**;
then the app-managed image copy inside `uploads/` is removed best-effort. If
the file unlink fails, the request still succeeds and reports
`image_removed: false` — the record deletion already happened.

Files referenced by `file_reference` (your own originals outside the managed
directory) are **never** touched. Vision insights for the asset are deleted
with it.

**200** → `{id, display_name, deleted_submissions, image_removed}`
(`image_removed` is `null` when the asset had no stored image)
**404** → `Asset not found`

---

## Uploads and images

### `POST /api/v1/uploads`

Upload an image and create its asset record in one step.

**Body**: `multipart/form-data` with a single `file` part.

Validation, in order:
1. Size limit while streaming — **413** `File is too large (limit 10.0 MB).`
2. Extension allow-list (`.jpg`, `.jpeg`, `.png`, `.webp`) — **400**
3. Magic-byte check — **400**
4. Full Pillow decode — **400** (this also proves the file is a real image)

The file is stored under a server-generated name inside `uploads/`. Your
original filename is kept only as `display_name`. If the database insert
fails, the stored file is removed so no orphan bytes are left behind
(covered by `tests/test_uploads.py::test_failed_upload_insert_removes_the_orphaned_file`).

**201** → `{asset: AssetOut, image_url: "/api/v1/images/{id}"}`

### `GET /api/v1/images/{asset_id}`

Serve an uploaded image for browser previews. The path is read from the
database row, never from the client.

**200** → the image bytes with the stored `media_type`
**404** → `Image not found`

---

## Submissions

### `GET /api/v1/submissions`

List submission records. Filterable by `asset_id` and `status`; paginated with
`page` and `page_size`.

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `asset_id` | integer > 0 | — | Exact match |
| `status` | string (max 20) | — | One of `draft`, `submitted`, `accepted`, `rejected`, `withdrawn`, `unknown`; anything else returns **422** |
| `page` | integer ≥ 1 | `1` | |
| `page_size` | integer 1–200 | `50` | |

> **Note:** there is **no `platform` query filter** on this endpoint. Platform is
> stored and displayed per record and is aggregated by
> `GET /api/v1/insights/summary` (`submissions_by_platform`), but it cannot be
> used to filter the list.

**200** → `{items: SubmissionOut[], total, page, page_size}`

### `POST /api/v1/submissions`

**Body**: `asset_id` (required, must exist), `platform` (required),
`status`, `submitted_at`, `rejection_note`, `rejection_category`, `reviewed_at`.

`status` is one of `draft`, `submitted`, `accepted`, `rejected`, `withdrawn`,
`unknown`.

**201** → `SubmissionOut` · **404** → linked asset not found

### `GET /api/v1/submissions/{submission_id}`

**200** → `SubmissionOut` · **404** → `Submission not found`

### `PATCH /api/v1/submissions/{submission_id}`

Partial update of status, notes, categories, and dates. A `rejected` status
without a note is allowed; the note is simply shown as empty.

**200** → `SubmissionOut` · **404** → `Submission not found`

---

## Insights

### `GET /api/v1/insights/summary`

Aggregates computed **only** from recorded data. No predictions, no fabricated
analytics.

**200** → includes `total_assets`, `archived_assets`, `total_submissions`,
`submissions_by_platform`, `submissions_by_status`, plus the time range and
sample size the numbers cover.

---

## AI metadata generation

### `GET /api/v1/ai/status`

Honest configuration disclosure. It reflects whether `COHERE_API_KEY` is set
**right now** — it never hardcodes a claim either way.

**200** → `{ai_configured: bool, message: str, model: str | null}`

- Configured: `ai_configured: true`, `model` is the active model name.
- Not configured: `ai_configured: false`, `model: null`, and a message that
  points at `.env` and reminds you that manual entry still works.

### `POST /api/v1/ai/analyze`

Analyze an uploaded image and return an **unsaved draft**.

**Body**: `{"asset_id": int, "consent": bool}`

- `consent` must be `true`; otherwise **422**. The server rejects the request
  before any image is read or sent.
- The asset must have an uploaded image, otherwise **400**
  `This asset has no uploaded image to analyze.`
- If the stored file is missing, **404** `The stored image file is missing.`

**Nothing is persisted.** The draft stays client-side until you save it with
`PATCH /api/v1/assets/{id}`.

**200** → `{asset_id, title, description, category, keywords, model}`

**Error codes**

| Status | Meaning |
| --- | --- |
| 400 | The asset has no uploaded image to analyze |
| 404 | Asset not found, or the stored image file is missing |
| 422 | Consent not given, or body failed validation |
| 429 | Cohere rate limit reached — wait and retry |
| 502 | Cohere returned an unusable response (invalid JSON, wrong shape, HTTP error) |
| 503 | No `COHERE_API_KEY` configured, or the model does not support image input |
| 504 | The Cohere request timed out |

---

## Vision Insights

### `POST /api/v1/vision/analyze/{asset_id}`

Run a structured vision analysis and **persist** the result.

**Body**: `{"asset_id": int, "consent": bool}`

- `asset_id` in the body must match the path, otherwise **422**.
- `consent` must be `true`, otherwise **422**. The server rejects the request
  before any image is read or sent.
- The asset must have an uploaded image, otherwise **404**.

The asset's editable metadata is **not** changed. Keyword suggestions from
the gap analysis must be applied separately via
`PATCH /api/v1/assets/{id}`.

**201** → `VisionInsightsRecordOut`:

```json
{
  "id": 1,
  "asset_id": 25,
  "visual_attributes": {
    "objects": ["..."], "scene": ["..."], "dominant_colors": ["..."],
    "lighting": "...", "mood": "...", "composition": "...",
    "orientation": "portrait|landscape|square", "copy_space": "..."
  },
  "commercial_use_ideas": [{"use_case": "...", "fit": "..."}],
  "keyword_gap_analysis": {
    "existing_keywords": ["..."], "suggested_missing": ["..."], "reasoning": "..."
  },
  "metadata_quality_review": {
    "title_assessment": "...", "keyword_issues": ["..."],
    "description_assessment": "...", "unsupported_terms": ["..."]
  },
  "actionable_recommendations": ["..."],
  "model": "command-a-vision-07-2025",
  "created_at": "2026-10-21 15:50:55"
}
```

**Error codes**

| Status | Meaning |
| --- | --- |
| 404 | Asset not found, or the asset has no uploaded image |
| 422 | Consent not given, or body/path `asset_id` mismatch |
| 429 | Cohere rate limit reached — wait and retry |
| 502 | Cohere returned an unusable response — including the "schema echo" case, where the model replies with the JSON Schema instead of an instance of it |
| 503 | No `COHERE_API_KEY` configured, or the model does not support image input |
| 504 | The Cohere request timed out |

### `GET /api/v1/vision/insights/{asset_id}`

Return the most recent persisted vision-insights record for an asset.

**200** → `VisionInsightsRecordOut`
**404** → `No vision insights found for this asset`

> **Note:** vision insights are tied to their asset by
> `asset_id REFERENCES assets(id) ON DELETE CASCADE`. Deleting the asset
> deletes its insight row, so a `GET` for a deleted asset returns **404**.
> Insights never modify the asset's editable metadata.

