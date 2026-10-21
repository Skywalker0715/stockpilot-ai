 # StockPilot AI

A local-first workspace for independent stock creators: organize asset records,
generate and review metadata with AI, review deeper image insights, and track
submissions and outcomes against honest, evidence-based summaries of your own
history. No paid APIs are required, no account automation, and the core
workflows work without internet.

**Status:** MVP (October 2026). Single-user, localhost-only.

## What this MVP does

- **Asset library** — upload images and create, edit, search, filter, and
  archive asset records (name, title, description, keywords, category, file
  reference, media type). Keywords are normalized (trimmed, de-duplicated
  case-insensitively). (PRD FR-01, FR-02)
- **AI metadata generation (optional)** — Cohere vision produces a *draft*
  title, description, category, and 30–50 keywords. Nothing is saved until you
  review and save it. Requires a Cohere API key; the app stays fully usable
  without one. (FR-07)
- **Vision Insights** — a deeper, structured analysis of an uploaded image:
  observable visual attributes, possible commercial use cases, a keyword gap
  analysis against your existing keywords, a metadata quality review, and
  actionable recommendations. Results are persisted per asset. (FR-07)
- **Submission/review tracking** — record platform, status
  (`draft/submitted/accepted/rejected/withdrawn/unknown`), submission date,
  rejection note, and a user-correctable rejection category. (FR-04, FR-05)
- **Dashboard** — counts derived only from your recorded data, with sample
  size and time range shown; no predictions or invented analytics.
- **Persistence** — SQLite with ordered, idempotent migrations and foreign-key
  enforcement. Records survive restarts.
- **Honest AI status** — `GET /api/v1/ai/status` reports whether a key is
  actually configured right now. Images leave your machine only when you click
  Generate or Run Analysis and tick the consent checkbox ("I agree to send
  this image to Cohere for AI analysis"). The button stays disabled until you
  do, and consent resets for every new image.

## Deliberately deferred (not in this MVP)

- CSV import/export with preview (PRD FR-03)
- Image near-duplicate/similarity scanning (FR-06)
- Backup/restore tooling (FR-09) — for now, stop the backend and copy
  `stockpilot.db`; restore by placing the file back
- Multi-user, cloud sync, platform automation (excluded by PRD §3)

## Stack

- Backend: Python 3.12, FastAPI, standard-library `sqlite3` (no ORM)
- Frontend: React 18, TypeScript (strict), Vite; no UI framework
- AI: Cohere Chat API v2, model `command-a-vision-07-2025` (optional)
- Tests: pytest with FastAPI `TestClient` (fully offline)

## Setup

### One-command startup (Windows, recommended)

```powershell
cd "<repo folder>"
.\start-stockpilot.ps1
```

Starts the backend (port 8000) and the Vite dev server (port 5173) together
in the same terminal (their logs are prefixed `[backend]` / `[frontend]`; no
extra console windows are opened), prints both local URLs, and verifies each
service answers HTTP before reporting it ready. Press **Ctrl+C** to stop both
services; the script stops only the processes it started.

- Uses the existing `venv` and `frontend\node_modules`; it installs nothing
  and never recreates the virtual environment.
- Never touches `stockpilot.db`, `.env`, source files, or user data.
- Refuses to start if port 8000 or 5173 is already occupied, and names the
  owning process (no duplicate servers).
- Reports missing prerequisites (Python/venv, npm, `frontend\node_modules`)
  and server startup errors instead of hiding them.

If script execution is blocked by policy:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-stockpilot.ps1
```

### Backend (terminal 1)

```powershell
cd "d:\Ngoding dan AI Project\AI Project Mini\stockpilot-ai"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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

### Enabling AI (optional)

Copy `.env.example` to `.env` and set your key:

```dotenv
COHERE_API_KEY=your-key-here
```

Get one at https://dashboard.cohere.com/api-keys. The key stays server-side
and is never sent to the browser. If `COHERE_API_KEY` is empty, every manual
workflow still works and the UI shows an honest "AI not configured" notice.

See `docs/OPERATIONS.md` for configuration, troubleshooting, and AI error
handling.

## Tests and builds

```powershell
# Backend: 92 offline tests, no network or external services
python -m pytest tests/ -v

# Frontend: strict TypeScript check + production build
cd frontend
npm run build
```

`tests/smoke_live.py` is a separate **live** smoke test that runs against an
already-running server and calls the real Cohere API. It is not part of the
offline suite:

```powershell
python tests\smoke_live.py 8000
```

## Backup and restore

1. Stop the backend.
2. Copy `stockpilot.db` somewhere safe (that file is the entire database).
3. To restore, stop the backend, put the file back, and restart.

Uploaded images live in `uploads/` and are separate from the database. Copy
that directory too if you want the image files preserved.

## Security notes

- The app has **no authentication** and binds like any local dev tool; it is
  intended for `localhost` only. Do not expose port 8000 to a network.
- CORS is restricted to `http://localhost:5173` (the Vite dev server).
- `COHERE_API_KEY` stays in the gitignored `.env`; it is never committed and
  never returned to the frontend.
- Uploads are validated (extension allow-list, magic bytes, size limit, full
  decode) and stored under server-generated filenames inside `uploads/`. If the
  database insert fails, the stored file is removed, so a failed upload leaves
  no orphaned bytes behind.
- Permanent deletion (`DELETE /api/v1/assets/{id}`) only ever removes the
  app-managed copy inside `uploads/`. Files you referenced by `file_reference`
  are never touched. The asset's Vision Insight is deleted along with it.
- Both AI endpoints require `consent: true`; requests without it are rejected
  with `422` and never reach the provider.

## API overview

| Method | Path                              | Purpose                          |
| ------ | --------------------------------- | -------------------------------- |
| GET    | `/api/v1/assets`                  | List/search assets (paginated)   |
| POST   | `/api/v1/assets`                  | Create an asset                  |
| GET    | `/api/v1/assets/{id}`             | Fetch one asset                  |
| PATCH  | `/api/v1/assets/{id}`             | Update/archive an asset          |
| DELETE | `/api/v1/assets/{id}`             | Permanently delete an asset      |
| POST   | `/api/v1/uploads`                 | Upload an image, create an asset |
| GET    | `/api/v1/images/{id}`             | Serve an uploaded image          |
| GET    | `/api/v1/submissions`             | List submissions (filterable)    |
| POST   | `/api/v1/submissions`             | Record a submission              |
| GET    | `/api/v1/submissions/{id}`        | Fetch one submission             |
| PATCH  | `/api/v1/submissions/{id}`        | Update status/notes/categories   |
| GET    | `/api/v1/insights/summary`        | Honest aggregates of your data   |
| GET    | `/api/v1/ai/status`               | AI configuration disclosure      |
| POST   | `/api/v1/ai/analyze`              | Generate a metadata **draft**     |
| POST   | `/api/v1/vision/analyze/{id}`     | Run and persist Vision Insights  |
| GET    | `/api/v1/vision/insights/{id}`    | Latest Vision Insights record    |

Full request/response detail and error codes: `docs/API.md`.
Interactive docs: http://127.0.0.1:8000/docs

## History

This repository began as `llm-gmaps-backend` (a Google Maps + LLM technical
test). The legacy `/search` endpoint and its Google Maps/LLM clients were
retired on the `mvp/asset-workspace` branch in October 2026; Git history is
preserved. Product and engineering rules live in `docs/`.

