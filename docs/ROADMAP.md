# Roadmap

Progress reflects the approved MVP scope for the October 17, 2026 demo
(ADR-007). Checkboxes are marked only with evidence.

## Phase 0 — Audit and validation
- [x] Inspect existing repository, Git status, dependencies, tests, and secrets. (Baseline audit, 2026-10-15)
- [x] Identify the current LLM provider/model and its cost requirements. (Generic HTTP adapter to `localhost:3000`; no provider installed; retired per ADR-004)
- [x] Map Google Maps/Places dependencies. (Optional key, mock fallback; retired per ADR-004)
- [ ] Compare existing creator tools and validate a concrete unmet need. (User research; out of engineering scope)
- [x] Confirm MVP acceptance criteria. (ADR-007)

## Phase 1 — Foundation
- [x] Approve migration plan and create a safe branch/backup. (`mvp/asset-workspace` off `d1a9d3c`)
- [x] Establish app configuration and local setup. (`.env.example`, README setup guide)
- [x] Add SQLite persistence and migrations. (stdlib sqlite3, ordered SQL migrations, FK on; 19 offline tests)
- [x] Implement asset CRUD with tests. (FR-01/02; `tests/test_assets.py`)
- [ ] Add CSV import/export with preview and validation. (**Deferred** — ADR-007; top post-demo priority)

## Phase 2 — Creator workflow
- [x] Add platform and submission status tracking. (`tests/test_submissions.py`)
- [x] Add rejection notes and editable categories. (PATCH submissions; test covers correction)
- [x] Add filtering and useful summary metrics based on real records. (`/api/v1/insights/summary` + dashboard; sample size shown)

## Phase 3 — Local asset quality
- [ ] Implement opt-in local similarity scanning. (**Deferred** — ADR-007)
- [ ] Explain score, threshold, and limitations. (Blocked on the above)
- [ ] Add tests using controlled sample images. (Blocked on the above)

## Phase 4 — Optional AI
- [ ] Compare small local models on target hardware. (**Deferred** — no provider installed; app works AI-off per AI_QUALITY §1)
- [ ] Add a provider adapter only if useful. (Blocked on the above)
- [ ] Add metadata suggestion review and validation. (Blocked on the above)
- [x] Confirm all core workflows still work with AI disabled. (AI status endpoint + offline suite; banner in frontend)

## Phase 5 — Release candidate
- [ ] Complete security review. (Interim: CORS locked to 5173, input length limits, no secrets; **full review pending**)
- [x] Verify backup/restore. (Manual: stop backend, copy `stockpilot.db` — documented in README; tooling deferred)
- [ ] Test clean installation on Windows. (**Pending** — needs a clean-machine rehearsal before the demo)
- [x] Run full tests and document known limitations. (`pytest`: 19 passed; `npm run build`: clean; limitations in README)
- [ ] Conduct user testing and revise based on evidence. (Post-demo)

## Release gate
Do not mark a phase complete without evidence: test results, user feedback, or a documented decision.
