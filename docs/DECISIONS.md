# Architecture Decision Log

Record important decisions here. New decisions should include date, status, context, alternatives, and consequences.

## ADR-001: No mandatory paid external APIs
- **Status:** Proposed
- **Context:** The project should be buildable and usable without required Google Maps or paid LLM API calls.
- **Decision:** Keep core workflows local-first. Any remote AI integration is optional, disclosed, and replaceable.
- **Consequences:** Local model quality and hardware performance must be tested; some AI features may be slower or unavailable on low-memory machines.

## ADR-002: SQLite for the initial local MVP
- **Status:** Proposed
- **Context:** The developer's laptop has 8 GB RAM and the initial target is a single-user workspace.
- **Decision:** Start with SQLite, using migrations and backups.
- **Consequences:** Revisit only if a validated multi-user/cloud requirement appears.

## ADR-003: No automatic stock-platform account automation
- **Status:** Proposed
- **Context:** Platform APIs and permissions may be limited, and account automation introduces security and policy risks.
- **Decision:** Start with manual tracking and documented CSV import/export.
- **Consequences:** No promise of automatic uploads, sales retrieval, or submission-status synchronization.

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

## Decision template
### ADR-XXX: Short title
- **Date:**
- **Status:** Proposed / Accepted / Rejected / Superseded
- **Context:**
- **Decision:**
- **Alternatives:**
- **Consequences:**
