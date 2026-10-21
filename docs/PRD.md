# Product Requirements Document (PRD)

**Status:** Implemented scope as of October 2026 (see `docs/ROADMAP.md` for
progress and `docs/DECISIONS.md` for scope decisions). Requirements marked
**Deferred** are not built yet.

## 1. MVP goal
Deliver a usable local-first workspace for one creator to organize stock assets, review metadata, generate metadata and visual insights with AI, and track submission outcomes.

## 2. Core user stories
### Asset library
- As a creator, I can upload an image or add a record with a file
  path/reference, title, keywords, category, and media type.
- I can search, filter, page, edit, archive, and permanently delete my asset
  records.
- Keyword lists are normalized on write (trimmed, de-duplicated
  case-insensitively).
- The app warns before duplicate records are created. **Deferred** — no
  duplicate detection is implemented yet.

### Metadata assistant
- I can ask for a suggested title, description, category, and keyword list.
- I can review and edit every suggestion before saving; nothing is persisted
  until I explicitly save it.
- The system labels generated content as a suggestion, not verified
  platform-compliant metadata.
- If the AI provider is unavailable or unconfigured, I can still edit metadata
  manually.

### Vision Insights
- I can run a deeper structured analysis of an uploaded image: observable
  visual attributes, possible commercial use cases, a keyword gap analysis
  against my existing keywords, a metadata quality review, and actionable
  recommendations.
- Results are stored per asset as their own history and never silently
  overwrite my editable metadata.
- The app states clearly that observations are model output, not verified facts.

### Submission and review history
- I can record a submission date, platform, status, and rejection note.
- I can categorize a rejection manually and correct the category later.
- The dashboard summarizes only data actually entered or imported by the user.

### Personal insights
- I can view counts and trends derived from my recorded history.
- The app shows sample size and time range.
- It must not claim causation or predict acceptance/sales without validated
  evidence.

## 3. MVP exclusions
- Automatic uploading to Adobe Stock or other platforms.
- Scraping contributor dashboards.
- Platform login/session automation.
- Paid APIs as a requirement.
- Multi-user SaaS, billing, team permissions, or cloud sync.
- Claims that an asset will be accepted, rank higher, or sell.
- Training a custom model on user assets by default.

## 4. Functional requirements
- FR-01: Create, read, update, archive, and search asset records. **Done**
  (`GET/POST/PATCH/DELETE /api/v1/assets`, plus `POST /api/v1/uploads`).
- FR-02: Store editable metadata and track its source: user-entered, imported,
  or AI-suggested (`metadata_origin`). **Done**
- FR-03: Import/export a documented CSV format with validation and an import
  preview. **Deferred** (ADR-007) — not implemented.
- FR-04: Track platform and submission/review status. **Done**
- FR-05: Record rejection notes and optional user-selected categories. **Done**
- FR-06: Run local image similarity checks on explicitly selected files.
  **Deferred** (ADR-007) — not implemented.
- FR-07: Generate metadata suggestions only when an AI provider is configured.
  **Done** — plus Vision Insights, which persists per-asset analysis records
  separately from editable metadata.
- FR-08: Display understandable errors and allow retry without data loss.
  **Done** — errors return a `detail` message; the frontend shows retry
  affordances.
- FR-09: Back up and restore the local database through a documented process.
  **Partially done** — the process is documented (stop backend, copy
  `stockpilot.db`); backup *tooling* is deferred.
- FR-10: Keep an audit trail for important user edits where practical.
  **Deferred** — not implemented. Timestamps are recorded, but there is no
  per-edit history.

## 5. Non-functional requirements
- NFR-01: Must run on Windows with 8 GB RAM for core workflows.
- NFR-02: Core library, tracking, and manual editing must work without
  internet.
- NFR-03: Do not send images or metadata to an external provider without
  explicit user awareness. **Done** — both AI endpoints require
  `consent: true`, enforced server-side, and both AI screens require an
  explicit consent checkbox before the action button is enabled.
- NFR-04: Keep API keys and secrets out of source control and frontend
  bundles. **Done** — `COHERE_API_KEY` is server-side only, `.env` is
  gitignored.
- NFR-05: Use migrations and backups before any destructive data change.
  **Done** — ordered, idempotent SQL migrations applied at startup.
- NFR-06: Use pagination or incremental loading for larger libraries. **Done**
  — `page` / `page_size` on the asset and submission lists.
- NFR-07: Provide clear loading, empty, error, and success states. **Done**
- NFR-08: Avoid inaccessible color-only status indicators; provide text
  labels. **Done**

## 6. Acceptance criteria
A release candidate is not accepted until:
- New, edited, archived, and imported records persist after restart.
  **Imported records — Deferred** (no CSV import).
- CSV import reports invalid rows and does not silently discard them.
  **Deferred.**
- Similarity scan is repeatable on the same files and settings. **Deferred.**
- LLM failures do not break non-AI workflows. **Done** — `GET /api/v1/ai/status`
  discloses configuration, and the offline suite runs with no key.
- AI suggestions require user review before being saved. **Done** — the
  metadata endpoint returns a draft that is not persisted until the user
  saves it.
- Unit and integration tests pass. **Done** — `python -m pytest tests/`.
- Setup and backup instructions have been tested on a clean environment.
  **Partially done** — setup is scripted (`start-stockpilot.ps1`); a full
  clean-machine rehearsal is still pending.
