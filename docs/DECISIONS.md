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

## Decision template
### ADR-XXX: Short title
- **Date:**
- **Status:** Proposed / Accepted / Rejected / Superseded
- **Context:**
- **Decision:**
- **Alternatives:**
- **Consequences:**
