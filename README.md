# StockPilot AI — Project Documentation Pack

This documentation pack establishes the product and engineering rules before implementation.

## Start here
1. Read `docs/PRODUCT.md` and agree on the product boundaries.
2. Read `docs/PRD.md` and confirm the MVP.
3. Read `docs/ARCHITECTURE.md` before changing the existing `llm-gmaps-backend` repository.
4. Follow `docs/AI_QUALITY.md`, `docs/SECURITY.md`, and `docs/CODING_STANDARDS.md` for every implementation task.
5. Use `AGENTS.md` as the instruction file for coding agents such as Cline, Cursor, or Claude Code.
6. Track decisions in `docs/DECISIONS.md`; update `docs/ROADMAP.md` only when scope changes are approved.

## Important status
These documents are a proposed baseline, not evidence that the current repository already follows this architecture. The existing repository must be audited first. Do not rename, delete, migrate, or rewrite files until the audit is reviewed and approved.

## Suggested repository layout after approval
```text
stockpilot-ai/
├── AGENTS.md
├── docs/
│   ├── PRODUCT.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── AI_QUALITY.md
│   ├── SECURITY.md
│   ├── CODING_STANDARDS.md
│   ├── TESTING.md
│   ├── ROADMAP.md
│   └── DECISIONS.md
├── backend/
└── frontend/
```

The final folder layout must be reconciled with the current repository after the audit. Avoid duplicating the same rules across many files: `AGENTS.md` points agents to the detailed documents.
