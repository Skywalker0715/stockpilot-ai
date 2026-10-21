# Roadmap

Progress reflects the approved MVP scope for the October 17, 2026 demo
(ADR-007), plus the Cohere AI work completed on October 20–21, 2026.
Checkboxes are marked only with evidence.

## Phase 0 — Audit and validation
- [x] Inspect existing repository, Git status, dependencies, tests, and secrets. (Baseline audit, 2026-10-15)
- [x] Identify the current LLM provider/model and its cost requirements. (Generic HTTP adapter to `localhost:3000`; no provider installed; retired per ADR-004)
- [x] Map Google Maps/Places dependencies. (Optional key, mock fallback; retired per ADR-004)
- [ ] Compare existing creator tools and validate a concrete unmet need. (User research; out of engineering scope)
- [x] Confirm MVP acceptance criteria. (ADR-007)

## Phase 1 — Foundation
- [x] Approve migration plan and create a safe branch/backup. (`mvp/asset-workspace` off `d1a9d3c`)
- [x] Establish app configuration and local setup. (`.env.example`, README setup guide, `start-stockpilot.ps1`)
- [x] Add SQLite persistence and migrations. (stdlib sqlite3, ordered SQL migrations, FK on; 3 migrations applied)
- [x] Implement asset CRUD with tests. (FR-01/02; `tests/test_assets.py`, `tests/test_archive_restore.py`)
- [x] Add image upload with validation and managed storage. (FR-01; `tests/test_uploads.py`; migration 002)
- [ ] Add CSV import/export with preview and validation. (**Deferred** — ADR-007; top post-demo priority)

## Phase 2 — Creator workflow
- [x] Add platform and submission status tracking. (`tests/test_submissions.py`)
- [x] Add rejection notes and editable categories. (PATCH submissions; test covers correction)
- [x] Add filtering and useful summary metrics based on real records. (`/api/v1/insights/summary` + dashboard; sample size shown)
- [x] Add pagination to the asset and submission lists. (`page` / `page_size`, max 200)

## Phase 3 — Local asset quality
- [ ] Implement opt-in local similarity scanning. (**Deferred** — ADR-007)
- [ ] Explain score, threshold, and limitations. (Blocked on the above)
- [ ] Add tests using controlled sample images. (Blocked on the above)

## Phase 4 — Optional AI
- [x] Select a provider and pin a model. (Cohere `command-a-vision-07-2025`; ADR-009)
- [x] Add a provider adapter behind one module. (`app/services/cohere_service.py`; no `httpx` import outside it)
- [x] Add metadata suggestion review and validation. (FR-07; `POST /api/v1/ai/analyze` returns a draft; the user must save it)
- [x] Add Vision Insights as a separate, persisted analysis. (FR-07; `POST /api/v1/vision/analyze/{id}`, migration 003)
- [x] Enforce explicit consent server-side. (ADR-010; both AI endpoints require `consent: true`)
- [x] Confirm all core workflows still work with AI disabled. (`GET /api/v1/ai/status` + offline suite; banner in frontend)
- [x] Harden provider output handling. (ADR-012 schema-echo prevention + detection; ADR-013 `temperature=0`, `max_tokens=2048`)

## Phase 5 — Release candidate
- [ ] Complete security review. (Interim: CORS locked to 5173, input length limits, no secrets; **full review pending**)
- [x] Verify backup/restore. (Manual: stop backend, copy `stockpilot.db` — documented in README; tooling deferred)
- [ ] Test clean installation on Windows. (**Pending** — needs a clean-machine rehearsal before the demo)
- [x] Run full tests and document known limitations. (`pytest`: 92 passed; `npm run build`: clean; limitations in README)
- [ ] Manually validate the UI flows in a browser. (**Pending** — browser automation is unavailable in this environment; see the "Manual validation checklist" below)
- [ ] Conduct user testing and revise based on evidence. (Post-demo)

## Manual validation checklist (not yet performed)
Browser automation is unavailable here, so these flows still need a human pass
against a running app:

- [ ] Consent prompt appears before any image leaves the machine, on **both**
      the Generate and Vision Insights screens, and the action button stays
      disabled until the consent checkbox is ticked.
- [ ] Generate produces an editable draft; nothing is saved until you save it.
- [ ] Vision Insights renders all four sections and does not alter asset metadata.
- [ ] Archive hides the asset; restore brings it back with data intact.
- [ ] Dashboard statistics match the records actually entered.
- [ ] Permanent delete removes the row and the app-managed image, asks for
      confirmation first, and also removes the asset's Vision Insight.
- [ ] Upload cleanup: a failed asset insert leaves no file behind in `uploads/`.

## Release gate
Do not mark a phase complete without evidence: test results, user feedback, or a documented decision.
