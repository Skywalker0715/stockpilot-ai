# StockPilot AI

A local-first workspace for independent stock creators: organize asset records,
track submissions and review outcomes, and review honest, evidence-based
summaries of your own history. No paid APIs, no account automation, no
internet required for core workflows.

**Status:** MVP (October 2026). Single-user, localhost-only.

## What this MVP does

- **Asset library** — create, edit, search, filter, and archive asset records
  (name, title, description, keywords, category, file reference, media type).
  Keywords are normalized (trimmed, de-duplicated case-insensitively).
  (PRD FR-01, FR-02)
- **Submission/review tracking** — record platform, status
  (`draft/submitted/accepted/rejected/withdrawn/unknown`), submission date,
  rejection note, and a user-correctable rejection category. (FR-04, FR-05)
- **Dashboard** — counts derived only from your recorded data, with sample
  size and time range shown; no predictions or invented analytics.
- **Persistence** — SQLite with ordered, idempotent migrations and foreign-key
  enforcement. Records survive restarts.
- **Honest AI status** — this build has no AI provider. The app says so
  (`GET /api/v1/ai/status`) and all metadata entry is manual.

## Deliberately deferred (not in this MVP)

- CSV import/export with preview (PRD FR-03)
- Image near-duplicate/similarity scanning (FR-06)
- AI metadata suggestions (FR-07) — an adapter can be added later; the app
  must keep working without one
- Backup/restore tooling (FR-09) — for now, stop the backend and copy
  `stockpilot.db`; restore by placing the file back
- Multi-user, cloud sync, platform automation (excluded by PRD §3)

## Stack

- Backend: Python 3.12, FastAPI, standard-library `sqlite3` (no ORM)
- Frontend: React 18, TypeScript (strict), Vite; no UI framework
- Tests: pytest with FastAPI `TestClient` (fully offline)

## Setup

### Backend (terminal 1)

```powershell
cd "d:\Ngoding dan AI Project\AI Project Mini\stockpilot-ai"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Migrations run automatically at startup. The database file defaults to
`<repo>\stockpilot.db`; override with the `STOCKPILOT_DB_PATH` environment
variable (see `.env.example`).

### Frontend (terminal 2)

```powershell
cd "d:\Ngoding dan AI Project\AI Project Mini\stockpilot-ai\frontend"
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to the backend
on port 8000.

## Tests and builds

```powershell
# Backend: 19 offline tests, no network or external services
python -m pytest tests/ -v

# Frontend: strict TypeScript check + production build
cd frontend
npm run build
```

## Backup and restore

1. Stop the backend.
2. Copy `stockpilot.db` somewhere safe (that file is the entire database).
3. To restore, stop the backend, put the file back, and restart.

## Security notes

- The app has **no authentication** and binds like any local dev tool; it is
  intended for `localhost` only. Do not expose port 8000 to a network.
- CORS is restricted to `http://localhost:5173` (the Vite dev server).
- No secrets are required or stored. `.env` is gitignored; keep it that way.

## API overview

| Method | Path                              | Purpose                          |
| ------ | --------------------------------- | -------------------------------- |
| GET    | `/api/v1/assets`                  | List/search assets (paginated)   |
| POST   | `/api/v1/assets`                  | Create an asset                  |
| GET    | `/api/v1/assets/{id}`             | Fetch one asset                  |
| PATCH  | `/api/v1/assets/{id}`             | Update/archive an asset          |
| GET    | `/api/v1/submissions`             | List submissions (filterable)    |
| POST   | `/api/v1/submissions`             | Record a submission              |
| GET    | `/api/v1/submissions/{id}`        | Fetch one submission             |
| PATCH  | `/api/v1/submissions/{id}`        | Update status/notes/categories   |
| GET    | `/api/v1/insights/summary`        | Honest aggregates of your data   |
| GET    | `/api/v1/ai/status`               | AI configuration disclosure      |

Interactive docs: http://127.0.0.1:8000/docs

## History

This repository began as `llm-gmaps-backend` (a Google Maps + LLM technical
test). The legacy `/search` endpoint and its Google Maps/LLM clients were
retired on the `mvp/asset-workspace` branch in October 2026; Git history is
preserved. Product and engineering rules live in `docs/`.

