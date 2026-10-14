# Architecture and System Design

**Status:** Proposed target architecture; not yet verified against the current repository.

## 1. Design constraints
- Windows development environment, 8 GB RAM.
- No required paid API.
- No Google Maps/Places integration.
- Preserve useful code and Git history from `llm-gmaps-backend`; do not assume it is reusable until audited.
- Start with one local user and a simple deployment model.

## 2. Proposed stack
- Frontend: React + TypeScript (Vite is a lightweight default).
- Backend: Python + FastAPI if the existing app is already FastAPI-compatible.
- Data: SQLite for MVP.
- Image similarity: perceptual hashing and/or image embeddings only after comparing resource needs and accuracy.
- LLM adapter: provider-agnostic interface; local Ollama adapter is optional, not a hard dependency.
- Tests: pytest for backend; frontend test tooling selected after inspecting current package setup.

Do not migrate frameworks merely to match this document. First inspect the current repository and propose the smallest safe migration.

## 3. Logical components
- Asset Catalog: metadata and asset records.
- File Reference Service: validates allowed local file references; avoid arbitrary filesystem access.
- Metadata Service: validates and stores user-edited metadata.
- Similarity Service: computes and compares fingerprints for selected assets.
- Submission Tracker: stores platform, status, dates, and review notes.
- Insights Service: aggregates user-provided records without unsupported predictions.
- LLM Adapter: optional suggestions with timeouts, validation, and graceful fallback.
- API Layer: request validation, authentication if needed, error mapping, and versioning.

## 4. Suggested data entities
### Asset
- id
- display_name
- file_reference or managed_storage_path
- media_type
- title
- description
- keywords (normalized structured representation)
- category
- created_at
- updated_at
- metadata_origin (`manual`, `imported`, `ai_suggested`)

### Submission
- id
- asset_id
- platform
- submitted_at
- status (`draft`, `submitted`, `accepted`, `rejected`, `withdrawn`, `unknown`)
- rejection_note
- rejection_category
- reviewed_at

### SimilarityScan
- id
- asset_a_id
- asset_b_id
- algorithm
- score_or_distance
- threshold
- created_at

### AppSetting
- key
- value (no secrets in plain database unless properly protected)
- updated_at

Use migrations and enforce foreign keys. Store only the data needed for the workflow.

## 5. API design sketch
Examples only; align paths with existing conventions after audit:
- `GET /api/v1/assets`
- `POST /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `PATCH /api/v1/assets/{asset_id}`
- `POST /api/v1/assets/import`
- `GET /api/v1/assets/export`
- `POST /api/v1/similarity-scans`
- `GET /api/v1/submissions`
- `POST /api/v1/submissions`
- `POST /api/v1/metadata/suggestions` (optional LLM)
- `GET /api/v1/insights/summary`

## 6. AI integration
Define a small interface such as `MetadataSuggestionProvider.suggest(input)`. The rest of the app must not depend directly on Ollama or a particular vendor. Validate output using schemas, limit input size, handle timeouts, and never execute model output as code.

## 7. File handling
- Do not trust client-provided paths.
- Restrict operations to user-selected files or an app-managed directory.
- Do not recursively scan the entire disk by default.
- Do not delete original files automatically.
- Avoid uploading images to remote services without clear consent.

## 8. Migration strategy
Phase A: inventory repo, dependencies, tests, Git status, configuration, and current LLM provider.
Phase B: create a migration plan with exact files to keep, replace, or retire.
Phase C: approve plan and make a branch/backup.
Phase D: remove Maps only after checking imports, tests, and runtime references.
Phase E: implement a thin vertical slice (asset CRUD + persistence + one test).
Phase F: add similarity, tracking, then optional LLM suggestions.
Phase G: integrate frontend and run end-to-end tests.

## 9. Architecture decision
SQLite is preferred for the initial local MVP. Move to PostgreSQL only if a validated multi-user or deployment need justifies the added operational burden.
