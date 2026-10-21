# Architecture and System Design

**Status:** Implemented and verified against the current repository
(Cohere MVP, branch `mvp/asset-workspace`).

This document describes the system that exists in the repository today. Where
an earlier "proposed" idea was dropped, the reason is stated so it is not
re-introduced by accident.

## 1. Design constraints
- Windows development environment, 8 GB RAM.
- No required paid API — every feature except AI generation works without one.
- No Google Maps/Places integration.
- Single local user; no multi-tenant or account system.
- Images are processed locally and only leave the machine when the user
  explicitly consents to a Cohere call.

## 2. Stack (as built)
- **Frontend:** React 18 + TypeScript 5.6, bundled with Vite 5.
  `npm run build` runs `tsc && vite build`, so type errors fail the build.
- **Backend:** Python + FastAPI, synchronous SQLite access via a
  request-scoped connection dependency.
- **Data:** SQLite, file at `stockpilot.db` by default
  (`STOCKPILOT_DB_PATH` overrides it). Foreign keys are enabled on every
  connection (`PRAGMA foreign_keys = ON`).
- **Migrations:** plain `.sql` files in `app/migrations/`, applied in
  filename order exactly once and tracked in `schema_migrations`.
- **LLM:** Cohere Chat API v2 (`https://api.cohere.com`), vision-capable
  model `command-a-vision-07-2025` by default.
- **Tests:** pytest for the backend. Frontend test tooling was not added —
  the MVP relies on the TypeScript build plus a live smoke test.

## 3. Runtime layout
```
frontend/            React + Vite SPA (dev server on :5173)
  src/views/         Generate, Library, VisionInsights, Assets, Submissions, Dashboard
  src/api.ts         typed fetch wrapper for /api/v1
app/
  main.py            FastAPI app, CORS, lifespan runs migrations
  config.py          env-driven settings (.env via python-dotenv)
  db.py              connection factory + migration runner
  models.py          Pydantic request/response models
  routes/            assets, submissions, insights, uploads, ai, vision
  services/          asset, submission, insights, storage, cohere, vision
  migrations/        001_initial, 002_image_storage, 003_vision_insights
tests/               pytest suite + smoke_live.py (manual, real provider)
docs/                API, OPERATIONS, ARCHITECTURE, PRD, PRODUCT, ROADMAP, ...
```
The API is mounted at `/api/v1/...`. CORS allows only the configured origins
(default `http://localhost:5173`) and the methods
`GET, POST, PATCH, DELETE, OPTIONS`.

## 4. Logical components
- **Asset Catalog** (`routes/assets.py`, `services/asset_service.py`) — asset
  records, metadata, archive flag.
- **Upload / Storage Service** (`routes/uploads.py`,
  `services/storage_service.py`) — validates and stores images inside the
  app-managed `uploads/` directory; serves them back safely.
- **File Reference** — a plain-text path recorded on the asset. It is
  metadata only: the server never reads it, and permanent deletion never
  touches the file it points to.
- **Metadata Service** — validation and normalization of title, description,
  keywords, and category on write.
- **Submission Tracker** (`routes/submissions.py`) — platform, status, dates,
  rejection notes.
- **Insights Service** (`routes/insights.py`, `services/insights_service.py`)
  — deterministic aggregation of the user's own records. No model involved.
- **Cohere Service** (`services/cohere_service.py`) — the single provider
  adapter. It owns the HTTP call, the timeout, the JSON parsing, and the
  error mapping. Nothing else in the codebase imports `httpx`.
- **Vision Service** (`services/vision_service.py`) — runs the vision
  analysis and persists the result in `vision_insights`.
- **API Layer** — Pydantic validation, error mapping, versioning.

### Provider boundary

`cohere_service` is the only module that knows about Cohere, and it is the only
module in `app/` that imports `httpx`. It exposes two provider functions:

- `analyze_image(data, media_type) -> dict` — metadata draft.
- `analyze_vision_insights(data, media_type, existing_keywords) -> dict` —
  full vision analysis.

The configured/unconfigured state is read directly from
`config.COHERE_API_KEY` by `GET /api/v1/ai/status`; there is no
`is_configured()` helper.

It raises `CohereServiceError(status_code, message)` for every failure
condition, and the routes translate that into an `HTTPException`. Swapping
providers means replacing this one module.

## 5. Data entities (as migrated)
### `assets` (migration 001)
- id, display_name, file_reference, media_type, title, description
- keywords — JSON array, normalized on write
- category
- metadata_origin — `manual` | `imported` | `ai_suggested` (CHECK constraint)
- archived — 0/1 (CHECK constraint)
- created_at, updated_at

### `assets` additions (migration 002)
- stored_path — the managed filename inside `uploads/`
- file_size, width, height
- description, keywords, media_type become nullable-aware; `display_name`
  gains a server-generated default

### `submissions` (migration 001)
- id, asset_id (FK, `ON DELETE CASCADE`), platform
- status — `draft` | `submitted` | `accepted` | `rejected` | `withdrawn` | `unknown`
- submitted_at, reviewed_at, rejection_note, rejection_category, created_at

### `vision_insights` (migration 003)
- id, asset_id (FK, `ON DELETE CASCADE`)
- visual_attributes, commercial_use_ideas, keyword_gap_analysis,
  metadata_quality_review, actionable_recommendations — JSON text columns
- model — the model that produced the record
- created_at

One asset may have many analyses; the newest is served. The table is purely
additive — migration 003 does not touch existing tables or rows.

## 6. API surface (implemented)
- `GET /api/v1/assets` — filters: `q`, `category`, `archived`, `has_image`,
  `page`, `page_size`
- `POST /api/v1/assets` — create
- `GET /api/v1/assets/{asset_id}`
- `PATCH /api/v1/assets/{asset_id}` — update metadata, archive/restore
- `DELETE /api/v1/assets/{asset_id}` — permanent delete
- `POST /api/v1/uploads` — multipart image upload
- `GET /api/v1/images/{asset_id}` — serve the stored image
- `GET /api/v1/submissions` — filters: `asset_id`, `status`, `page`, `page_size`
- `POST /api/v1/submissions`
- `PATCH /api/v1/submissions/{submission_id}`
- `DELETE /api/v1/submissions/{submission_id}`
- `GET /api/v1/insights/summary`
- `GET /api/v1/ai/status`
- `POST /api/v1/ai/analyze`
- `POST /api/v1/vision/analyze/{asset_id}`
- `GET /api/v1/vision/insights/{asset_id}`

Full request/response schemas are in `docs/API.md`.

## 7. AI integration
- **Structured output.** Cohere's `response_format` with a JSON Schema is
  used for both AI endpoints.
- **Image handling.** Images are downscaled to a 1280 px longest side and
  base64-encoded for the API call; the raw upload is stored separately.
- **Budgets.** `max_tokens` 2048, `temperature` 0, whole-request timeout
  `STOCKPILOT_AI_TIMEOUT` (default 60 s).
- **Defensive parsing.** `parse_vision_insights` strips code fences, parses
  JSON, rejects non-objects, detects a schema echo, and requires the
  `visual_attributes`, `keyword_gap_analysis`, and `metadata_quality_review`
  sections before anything is returned or stored.
- **Error mapping.** Every failure becomes a `CohereServiceError` with an
  actionable message and an HTTP status. See `docs/AI_QUALITY.md` §7.

## 8. File handling
- Client-provided paths are never trusted. Uploads are validated by
  extension allow-list, magic bytes, a size limit enforced while streaming,
  and a full Pillow decode.
- Stored filenames are server-generated (UUID-based); the client's filename is
  kept only as display metadata.
- `GET /api/v1/images/{asset_id}` resolves the path from the database row
  and refuses to serve anything outside the managed directory.
- Permanent deletion removes the database record and the managed upload. It
  never deletes a file referenced by `file_reference`, because that file is
  outside the app's ownership.
- If the database insert fails after an upload was written, the stored file is
  removed before the error is re-raised, so a failed upload leaves no
  orphaned bytes in `uploads/`. Files orphaned by an earlier build are not
  swept automatically.
- Images are never uploaded to a remote service without explicit consent.
  Both AI screens (Generate and Vision Insights) require an explicit
  "I agree to send this image to Cohere for AI analysis" checkbox before the
  action button becomes enabled, and the consent state resets for every new
  image. The server-side `consent: true` validator remains the authoritative
  gate.

## 9. Design decisions not taken
- **Similarity / perceptual hashing.** Not implemented. No endpoint, table, or
  UI exists for it, and the PRD no longer promises it.
- **Asset import / export endpoints.** Not implemented.
- **`AppSetting` table.** Not implemented; configuration is environment-based.
- **Multi-user auth.** Not implemented; the MVP is single-user and local.
- **PostgreSQL.** SQLite is sufficient for the MVP. Move only if a validated
  multi-user or deployment need justifies the operational burden.

## 10. Migration strategy (historical, completed)
The repository was migrated from the earlier `llm-gmaps-backend` prototype in
phases: inventory → plan → branch → remove Maps → vertical slice (asset CRUD
+ persistence + tests) → uploads and storage → tracking → Cohere AI and
Vision → frontend integration. The current branch (`mvp/asset-workspace`)
holds the result. New migrations must be additive and must not rewrite
existing rows.

