# Testing Strategy

## Test layers
### Unit tests
- Metadata normalization and validation.
- CSV row validation and import summaries.
- Submission status transitions.
- Similarity score/threshold behavior.
- Analytics aggregation and small-sample handling.
- LLM output schema validation and fallback.

### Integration tests
- Asset CRUD persistence.
- Import/export round trip.
- Submission and rejection-note persistence.
- Similarity scan against a small controlled image set.
- LLM adapter timeout, malformed response, and unavailable-provider behavior.

### Frontend tests
- Create/edit asset form validation.
- Search/filter behavior.
- Import preview and error display.
- AI suggestion review before saving.
- Empty/loading/error states.

### End-to-end smoke tests
- Start application from documented instructions.
- Create an asset, edit metadata, record a submission outcome, restart, and verify persistence.
- Use core workflows with the LLM disabled.

## Test data
- Use synthetic or user-authorized sample assets only.
- Keep test fixtures clearly separated from production data.
- Do not include personal documents, account credentials, or licensed assets without permission.

## Completion rule
A task is not “done” just because code was written. Report the exact tests and checks executed, pass/fail counts, and any checks not run.
