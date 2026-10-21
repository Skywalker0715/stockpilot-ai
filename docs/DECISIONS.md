# Architecture Decision Log

Record important decisions here. New decisions should include date, status, context, alternatives, and consequences.

## ADR-001: No mandatory paid external APIs
- **Status:** Accepted
- **Context:** The project should be buildable and usable without required Google Maps or paid LLM API calls.
- **Decision:** Keep core workflows local-first. Any remote AI integration is optional, disclosed, and replaceable.
- **Consequences:** The catalog, upload, metadata editing, submission tracking, and insights summary all work with no API key. AI features degrade to a clear "not configured" state instead of failing. AI quality and latency must be tested on the actual laptop, not assumed.

## ADR-002: SQLite for the initial local MVP
- **Status:** Accepted
- **Context:** The developer's laptop has 8 GB RAM and the initial target is a single-user workspace.
- **Decision:** Start with SQLite, using migrations and backups.
- **Consequences:** Revisit only if a validated multi-user/cloud requirement appears.

## ADR-003: No automatic stock-platform account automation
- **Status:** Accepted
- **Context:** Platform APIs and permissions may be limited, and account automation introduces security and policy risks.
- **Decision:** Start with manual tracking of platform, status, dates, and rejection notes.
- **Consequences:** No promise of automatic uploads, sales retrieval, or submission-status synchronization. Note that CSV import/export (planned in the PRD) is **not** implemented in the current build — see ADR-009.

## ADR-004: Retire the legacy Google Maps search flow and its LLM client
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Audit showed the only endpoint (`POST /search`) required an LLM server that is not installed, returned a failing test, and exposed the Google Maps API key in responses. None of it serves the StockPilot product (PRODUCT.md §5).
- **Decision:** Delete `/search`, `maps.py`, and `llm_service.py` on `mvp/asset-workspace`; keep Git history unmodified.
- **Consequences:** The failing legacy test is gone; the new offline suite replaces it. No Maps/LLM credentials are needed or used.

## ADR-005: Localhost-only MVP without authentication
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Single user, single machine, 8 GB RAM dev laptop. Auth adds complexity without mitigating a threat model that does not exist yet.
- **Decision:** No authentication while the app is bound to localhost; CORS restricted to `http://localhost:5173`. Never expose port 8000 to a network. Revisit before any multi-user or remote deployment.
- **Consequences:** Documented in README security notes; tests do not exercise auth.

## ADR-006: SQLite via standard-library sqlite3; stdlib-only backend
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** ORM/migration frameworks add dependencies and RAM cost without benefit at this scale.
- **Decision:** Use `sqlite3` with foreign keys on, ordered `.sql` migrations tracked in a `schema_migrations` table, applied at startup. No SQLAlchemy/Alembic.
- **Consequences:** Migrations are plain SQL files; must be append-only (never edit an applied file—add a new numbered one).

## ADR-007: MVP scope cut for the October 17, 2026 demo
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Two days were available. PRD FR-03 (CSV), FR-06 (similarity), FR-07 (AI suggestions), and FR-09 (backup tooling) could not be delivered with tests in that window.
- **Decision:** Ship asset CRUD, submission tracking, insights summary, persistence, and the frontend workflow. Defer CSV, similarity, AI suggestions, and backup tooling; document them honestly in README.
- **Consequences:** Demo covers FR-01/02/04/05/08. CSV import/export remains the top post-demo priority per PRD.

## ADR-008: User-requested deletion of app-managed upload copies
- **Date:** 2026-10-20
- **Status:** Accepted
- **Context:** SECURITY.md ("Never automatically delete originals") and ARCHITECTURE.md ("Do not delete original files automatically") protect the user's own files. The CRUD audit meanwhile found no way to permanently remove anything: `uploads/` holds app-owned copies that grew without bound, and a real Delete was requested for Assets.
- **Decision:** Allow permanent deletion only as an explicit, confirmed user action (`DELETE /api/v1/assets/{id}` with an accessible confirmation dialog showing the asset name and its linked-submission count). The endpoint deletes the asset row (submissions cascade via the existing FK), commits, then best-effort removes the app-managed copy inside `UPLOAD_DIR` using the existing path-traversal-safe resolver. Files outside the managed directory — the user's originals referenced by `file_reference` — are never touched, and nothing is ever deleted automatically. Library "removal" stays non-destructive (Archive via `PATCH archived=true`).
- **Alternatives:** Archive as the only delete (rejected: managed copies would accumulate forever with no user-controlled cleanup); automatic orphan-file sweeping (rejected: contradicts the never-delete-automatically rule and risks racing active uploads).
- **Consequences:** Deletion is irreversible, so the UI must confirm with the blast radius first; a failed file unlink after the DB commit is logged and returned as `image_removed=false` without failing the request; `backups/` remains the rollback path; tests must use isolated temp databases and upload directories, never the real ones.

## ADR-009: Cohere as the single AI provider, behind one adapter module
- **Date:** 2026-10-20
- **Status:** Accepted
- **Context:** The MVP needs real image understanding for metadata generation and Vision Insights. An earlier Gemini reference remained in `requirements.txt` with no implementation behind it.
- **Decision:** Use Cohere's Chat API v2 with the vision-capable model `command-a-vision-07-2025` (override with `STOCKPILOT_AI_MODEL`). All provider access lives in `app/services/cohere_service.py`; no other module imports `httpx`. The stale Gemini dependency was removed from `requirements.txt`.
- **Alternatives:** A local Ollama adapter (rejected: no GPU budget and weaker vision quality on an 8 GB laptop); calling the provider directly from routes (rejected: makes the provider impossible to swap or stub).
- **Consequences:** `COHERE_API_KEY` lives in `.env` and never reaches the frontend. Without it the app is fully usable minus AI, and `GET /api/v1/ai/status` reports that honestly.

## ADR-010: Explicit consent gate on both AI endpoints
- **Date:** 2026-10-20
- **Status:** Accepted
- **Context:** Uploading an image to a third-party API transfers user data off the machine.
- **Decision:** Both `POST /api/v1/ai/analyze` and `POST /api/v1/vision/analyze/{id}` require `consent: true`, enforced by a Pydantic field validator (not just a frontend checkbox). The frontend shows a consent notice before any image leaves the machine. Both screens (Generate and Vision Insights) use the same explicit checkbox — "I agree to send this image to Cohere for AI analysis" — and the action button stays disabled until it is ticked.
- **Consequences:** Requests without consent are rejected with `422` and no provider call is made. Tests assert this. Consent is per image: it resets when a new image is uploaded, when a different asset is reopened, and when the screen is reset, so a single tick can never authorize a different image.

## ADR-011: Vision Insights persist separately and never auto-edit metadata
- **Date:** 2026-10-20
- **Status:** Accepted
- **Context:** AI analysis produces suggestions (missing keywords, quality issues). Auto-applying them would silently overwrite user work.
- **Decision:** Analysis results are stored in the additive `vision_insights` table (migration 003) as their own history. The asset's editable metadata is never modified by the AI. Keyword suggestions must be applied by the user via `PATCH /api/v1/assets/{id}`.
- **Consequences:** An asset can accumulate multiple analyses; the newest is served by `GET /api/v1/vision/insights/{id}`. Deleting the asset cascades the insights away.

## ADR-012: Structured output with a concrete skeleton plus schema-echo detection
- **Date:** 2026-10-21
- **Status:** Accepted
- **Context:** Cohere's structured-output mode does not guarantee an *instance* of the supplied schema. With the deeply nested vision schema the model sometimes replied with the schema document itself — echoing `type`/`properties`/`required` and filling properties with placeholder strings. Users saw a misleading "missing usable visual attributes" error.
- **Decision:** Two defenses. (1) Prevention: the vision prompt appends a concrete JSON skeleton showing the exact expected shape and forbids emitting schema keys. (2) Detection: the parser recognizes an echoed schema (top-level `properties`/`required` without `visual_attributes`) and rejects it with a specific `502` message.
- **Alternatives:** Retrying automatically (rejected: it multiplies latency and cost without guaranteeing a different response); accepting and post-processing the echo (rejected: the data would be placeholder strings, i.e. fabricated).
- **Consequences:** Regression tests cover the echo case in `tests/test_vision.py`. The parser stays the single gate between raw model text and anything persisted.

## ADR-013: Deterministic decoding and a raised token budget for metadata generation
- **Date:** 2026-10-20
- **Status:** Accepted
- **Context:** Measured runs showed unconstrained sampling produced a runaway keyword list that hit the token cap in 3 of 5 runs, and a compliant 50-keyword answer peaks at roughly 1205 tokens.
- **Decision:** Pin `temperature=0` and raise `max_tokens` to 2048 (from 1024) for both AI endpoints.
- **Consequences:** Output is reproducible enough to diff, and a compliant answer no longer risks truncation.

## ADR-014: Consent must be an explicit, per-image user action
- **Date:** 2026-10-21
- **Status:** Accepted
- **Context:** Generate originally showed a consent notice and then sent the image automatically. The Vision Insights screen already required an explicit checkbox. The inconsistency meant the two screens had different privacy postures for the same data transfer, and the Generate notice alone relied on the user reading it.
- **Decision:** Align Generate with Vision Insights. Both require ticking an explicit consent checkbox before the action button becomes enabled, and the request handler refuses to call the API when consent is missing (defense in depth — the server-side `422` remains the authoritative gate, per ADR-010).
- **Alternatives:** Keeping the auto-submit notice on Generate (rejected: it makes the consent posture differ per screen and is weaker than the ADR-010 baseline); a modal dialog (rejected: an inline checkbox matches the existing Vision Insights pattern and needs no new component).
- **Consequences:** The Generate button is disabled until consent is given, adding one deliberate click. The consent state resets per image, so the user must re-confirm for each new upload.

## Decision template
### ADR-XXX: Short title
- **Date:**
- **Status:** Proposed / Accepted / Rejected / Superseded
- **Context:**
- **Decision:**
- **Alternatives:**
- **Consequences:**
