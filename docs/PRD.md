# Product Requirements Document (PRD)

**Status:** Draft — must be validated before implementation.

## 1. MVP goal
Deliver a usable local-first workspace for one creator to organize stock assets, review metadata, compare images for similarity, and track submission outcomes.

## 2. Core user stories
### Asset library
- As a creator, I can add an asset with file path/reference, title, keywords, category, platform, and status.
- I can search, filter, sort, edit, archive, and export my asset records.
- The app warns before duplicate records are created.

### Metadata assistant
- I can ask for a suggested title, description, and keyword list.
- I can review and edit every suggestion before saving.
- The system labels generated content as a suggestion, not verified platform-compliant metadata.
- If the LLM is unavailable, I can still edit metadata manually.

### Similarity checker
- I can scan selected images from my own library.
- The app reports likely near-duplicates with a score or distance and explains that similarity is an estimate.
- I can adjust a threshold and review results before taking action.
- The checker must not automatically delete or reject an image.

### Submission and review history
- I can record a submission date, platform, status, and rejection note.
- I can categorize a rejection manually and correct the category later.
- The dashboard summarizes only data actually entered or imported by the user.

### Personal insights
- I can view counts and trends derived from my recorded history.
- The app shows sample size and time range.
- It must not claim causation or predict acceptance/sales without validated evidence.

## 3. MVP exclusions
- Automatic uploading to Adobe Stock or other platforms.
- Scraping contributor dashboards.
- Platform login/session automation.
- Paid APIs as a requirement.
- Multi-user SaaS, billing, team permissions, or cloud sync.
- Claims that an asset will be accepted, rank higher, or sell.
- Training a custom model on user assets by default.

## 4. Functional requirements
- FR-01: Create, read, update, archive, and search asset records.
- FR-02: Store editable metadata and track its source: user-entered, imported, or AI-suggested.
- FR-03: Import/export a documented CSV format with validation and an import preview.
- FR-04: Track platform and submission/review status.
- FR-05: Record rejection notes and optional user-selected categories.
- FR-06: Run local image similarity checks on explicitly selected files.
- FR-07: Generate metadata suggestions only when an AI provider is configured.
- FR-08: Display understandable errors and allow retry without data loss.
- FR-09: Back up and restore the local database through a documented process.
- FR-10: Keep an audit trail for important user edits where practical.

## 5. Non-functional requirements
- NFR-01: Must run on Windows with 8 GB RAM for core workflows.
- NFR-02: Core library, tracking, and manual editing must work without internet.
- NFR-03: Do not send images or metadata to an external provider without explicit user awareness.
- NFR-04: Keep API keys and secrets out of source control and frontend bundles.
- NFR-05: Use migrations and backups before any destructive data change.
- NFR-06: Use pagination or incremental loading for larger libraries.
- NFR-07: Provide clear loading, empty, error, and success states.
- NFR-08: Avoid inaccessible color-only status indicators; provide text labels.

## 6. Acceptance criteria
A release candidate is not accepted until:
- New, edited, archived, and imported records persist after restart.
- CSV import reports invalid rows and does not silently discard them.
- Similarity scan is repeatable on the same files and settings.
- LLM failures do not break non-AI workflows.
- AI suggestions require user review before being saved.
- Unit and integration tests pass.
- Setup and backup instructions have been tested on a clean environment.
