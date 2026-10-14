# Coding Standards

## General
- Prefer clear, boring, maintainable code over clever abstractions.
- Follow the conventions already present unless a migration is approved.
- Keep functions focused and names explicit.
- Add comments for non-obvious reasoning, not to narrate every line.
- Avoid speculative interfaces and unused extension points.

## Python backend
- Add type hints to public functions.
- Validate API payloads with the project's chosen validation library.
- Keep route handlers thin; put business logic in services.
- Use structured, useful error responses.
- Avoid broad `except Exception` unless it is a final boundary with logging and safe error mapping.
- Do not block the event loop with heavy work in async routes; use suitable worker/thread/process handling if needed.
- Keep dependencies minimal and pinned or constrained consistently.

## TypeScript frontend
- Enable strict TypeScript where practical.
- Avoid `any`; use a documented narrow exception when unavoidable.
- Keep API calls in a shared client/service layer.
- Provide loading, empty, error, and success states.
- Use reusable components only when there is a real repeated pattern.
- Do not make buttons decorative: every interactive control must work or be visibly disabled.

## Data
- Use explicit enums/status values.
- Normalize keywords consistently while preserving user-visible spelling where needed.
- Add migrations for schema changes.
- Never rely on frontend validation alone.

## UI/UX
- Use consistent spacing, typography, colors, and status language.
- Prioritize scanability for large asset libraries.
- Use text plus icons for important statuses; do not rely on color alone.
- Avoid fake charts, decorative metrics, excessive gradients, and unnecessary animation.
- Ensure keyboard navigation and readable contrast.

## Change management
- Keep changes scoped to the approved task.
- Update tests and relevant documentation.
- Explain trade-offs and list files changed in the final report.
