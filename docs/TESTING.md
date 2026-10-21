# Testing Strategy

The suite is **fully offline**: it never calls the Cohere API. Provider calls
are replaced with a stub transport, so the tests are deterministic and run
without a key or internet access.

## Test layers
### Unit tests
- Metadata normalization and validation (keyword trimming, de-duplication,
  length caps).
- Submission status and platform validation.
- Analytics aggregation and small-sample handling (sample size and date range
  describe the same set of rows).
- Provider output parsing: valid JSON, fenced JSON, non-object JSON, missing
  required fields, and the **schema-echo** case.
- Image downscaling to the 1280 px max side and unsupported-input rejection.
- Storage path resolution and path-traversal rejection.

### Integration tests
- Asset CRUD persistence.
- Upload validation end to end (extension, magic bytes, decode, size limit,
  orphan cleanup when the insert fails).
- Submission and rejection-note persistence, including category correction.
- Archive and restore.
- Deleting an asset cascades its submissions and vision insights.
- Migrations are ordered, idempotent, and re-applied safely on restart.
- AI endpoints: consent is required, a missing key returns a clear status, and
  provider failures map to the documented HTTP codes (`502`, `503`, `504`).

### Frontend tests
Not yet automated — the frontend has no test runner configured. The
following are covered by the manual validation checklist in
`docs/ROADMAP.md`:
- Create/edit asset form validation.
- Search/filter behavior.
- AI suggestion review before saving.
- Empty/loading/error states.

### End-to-end smoke tests
`tests/smoke_live.py` is a **live** smoke test, kept out of the offline suite
by design. It runs against an already-running server and calls the real
Cohere API:

```powershell
python tests\smoke_live.py 8000
```

It checks the running app end to end: AI status honesty, upload (including
dimension detection and image serving), AI generation with a real Cohere call,
consent enforcement (`422`), the draft-versus-save boundary (analysis persists
nothing), keyword de-duplication on save, reload from the library, rejection
of a bogus upload, and permanent deletion. It cleans up its own probe asset
so repeated runs leave no residue.

## Test data
- Use synthetic or user-authorized sample assets only.
- Keep test fixtures clearly separated from production data.
- Do not include personal documents, account credentials, or licensed assets without permission.
- Every test uses an **isolated temp database and upload directory**
  (see `tests/conftest.py`). Tests must never read or write the real
  `stockpilot.db` or `uploads/`.

## Current status
- Offline suite: `python -m pytest tests/` — 92 passed.
- Live smoke test: 20 checks passed against a running server.
- Frontend: `npm run build` (strict TypeScript + production build) passes.

## Known gaps
- The frontend has **no test runner**, so the consent gate on the Generate
  screen is not covered by automated tests. The backend gate (`consent: true`
  → `422`) is covered in `tests/test_ai.py` and `tests/test_vision.py`; the
  Generate screen's checkbox must still be confirmed by hand in the manual
  validation checklist in `docs/ROADMAP.md`.
- Orphan cleanup is covered for the **upload insert** failure
  (`tests/test_uploads.py::test_failed_upload_insert_removes_the_orphaned_file`).
  Files orphaned by an earlier build are **not** swept automatically — removing
  them requires explicit approval.

## Completion rule
A task is not “done” just because code was written. Report the exact tests and checks executed, pass/fail counts, and any checks not run.
