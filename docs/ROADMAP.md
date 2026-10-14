# Roadmap

This roadmap is provisional and must be adjusted after repository audit and competitor validation.

## Phase 0 — Audit and validation
- [ ] Inspect existing repository, Git status, dependencies, tests, and secrets.
- [ ] Identify the current LLM provider/model and its cost requirements.
- [ ] Map Google Maps/Places dependencies.
- [ ] Compare existing creator tools and validate a concrete unmet need.
- [ ] Confirm MVP acceptance criteria.

## Phase 1 — Foundation
- [ ] Approve migration plan and create a safe branch/backup.
- [ ] Establish app configuration and local setup.
- [ ] Add SQLite persistence and migrations.
- [ ] Implement asset CRUD with tests.
- [ ] Add CSV import/export with preview and validation.

## Phase 2 — Creator workflow
- [ ] Add platform and submission status tracking.
- [ ] Add rejection notes and editable categories.
- [ ] Add filtering and useful summary metrics based on real records.

## Phase 3 — Local asset quality
- [ ] Implement opt-in local similarity scanning.
- [ ] Explain score, threshold, and limitations.
- [ ] Add tests using controlled sample images.

## Phase 4 — Optional AI
- [ ] Compare small local models on target hardware.
- [ ] Add a provider adapter only if useful.
- [ ] Add metadata suggestion review and validation.
- [ ] Confirm all core workflows still work with AI disabled.

## Phase 5 — Release candidate
- [ ] Complete security review.
- [ ] Verify backup/restore.
- [ ] Test clean installation on Windows.
- [ ] Run full tests and document known limitations.
- [ ] Conduct user testing and revise based on evidence.

## Release gate
Do not mark a phase complete without evidence: test results, user feedback, or a documented decision.
