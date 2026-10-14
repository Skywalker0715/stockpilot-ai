# Instructions for AI Coding Agents

These rules apply to Cline, Cursor, Claude Code, and other coding agents working in this repository.

## Before coding
1. Read `docs/PRODUCT.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/AI_QUALITY.md`, `docs/SECURITY.md`, and `docs/CODING_STANDARDS.md`.
2. Inspect the actual code and Git status. Treat documentation as intended direction, not proof of current implementation.
3. For a new task, first summarize the problem, affected files, risks, and a short plan.
4. If the user asked for audit or planning only, do not modify files.
5. Ask for approval before broad refactors, destructive changes, migrations, dependency changes, or repository renames.

## Anti-slop rules
- Do not generate large amounts of code before understanding the existing implementation.
- Do not add features that were not requested or approved.
- Do not use placeholder/mock data in production paths. Clearly label fixtures and demo data.
- Do not claim a feature works unless it has been run and tested.
- Do not swallow exceptions or return fake success responses.
- Do not use random, hardcoded, or fabricated analytics.
- Do not create duplicate helpers, components, or services without checking for existing equivalents.
- Avoid over-abstraction; prefer the simplest design that solves a demonstrated need.
- Do not introduce a dependency without explaining why it is needed.
- Keep changes small and cohesive; show a file-by-file summary.

## Implementation workflow
1. State the acceptance criteria.
2. Inspect the relevant code and tests.
3. Make the smallest coherent change.
4. Add or update tests.
5. Run relevant tests, lint, and type checks when available.
6. Report commands run and exact results. If a command could not run, state why.
7. Update docs only when behavior or decisions changed.

## Quality bar
- Validate all external and user-provided input.
- Handle loading, empty, error, and success states.
- Use accessible labels and keyboard behavior for UI.
- Keep business logic out of UI components when practical.
- Never commit secrets, credentials, personal data, or local machine paths.
- Never use destructive shell commands without explicit approval.
