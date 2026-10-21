# Operations Guide

Running, configuring, and troubleshooting StockPilot AI locally.

## 1. Running the app

### One command (Windows)

```powershell
.\start-stockpilot.ps1
```

The script starts the backend (port 8000) and the Vite dev server (port 5173)
in the current terminal, prefixes their logs with `[backend]` / `[frontend]`,
and verifies each service answers HTTP before printing the ready banner.
**Ctrl+C** stops both services — it stops only the processes it started.

It refuses to start if port 8000 or 5173 is already in use and names the
owning process, so you never end up with two backends writing to the same
database. It never modifies `stockpilot.db`, `.env`, or source files.

### Manual start

Backend:

```powershell
venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend (separate terminal):

```powershell
cd frontend
npm run dev
```

Migrations run automatically when the app starts. There is no separate
migration command.

## 2. Configuration

All configuration is environment-based; `.env` is read at startup via
`python-dotenv`. See `.env.example` for the full list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `COHERE_API_KEY` | *(empty)* | Enables AI features. Empty = AI off, everything else still works |
| `STOCKPILOT_AI_MODEL` | `command-a-vision-07-2025` | Vision model used for analysis |
| `STOCKPILOT_AI_TIMEOUT` | `60` | Per-request timeout (seconds) for a Cohere call |
| `COHERE_BASE_URL` | `https://api.cohere.com` | API base override (testing against a stub) |
| `STOCKPILOT_DB_PATH` | `<repo>/stockpilot.db` | SQLite database location |
| `STOCKPILOT_UPLOAD_DIR` | `<repo>/uploads` | Managed image storage directory |
| `STOCKPILOT_MAX_UPLOAD_BYTES` | `10485760` (10 MiB) | Upload size limit |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed browser origins |

### Enabling AI

1. Get a key at https://dashboard.cohere.com/api-keys.
2. Copy `.env.example` to `.env`.
3. Set `COHERE_API_KEY=...`.
4. Restart the backend (config is read at startup).

Verify:

```powershell
curl.exe http://127.0.0.1:8000/api/v1/ai/status
```

`ai_configured` should be `true` and `model` should name the active model.

The key stays server-side. It is never sent to the browser and never appears
in an API response.


## 3. AI behavior and failure modes

Both AI endpoints require explicit `consent: true`. Images are sent to Cohere
only when a user action triggers the request.

| Symptom | Cause | What to do |
| --- | --- | --- |
| `503` — "AI generation is not configured" | `COHERE_API_KEY` is empty or the backend was not restarted after adding it | Set the key and restart the backend |
| `503` — model does not support image input | The account cannot use the configured vision model | Set `STOCKPILOT_AI_MODEL` to a vision model your account has access to |
| `429` — rate limit reached | Too many requests to Cohere | Wait a moment and retry |
| `504` — timed out | The call exceeded `STOCKPILOT_AI_TIMEOUT` | Raise the timeout, or use a smaller image |
| `502` — "not valid JSON" | The response was truncated at the token cap | Retry; the prompt asks for 30–50 keywords and the budget is 2048 tokens |
| `502` — "returned the response schema instead of an analysis" | Cohere echoed the JSON Schema instead of an instance of it | Retry — a known transient provider behavior, now detected explicitly instead of surfacing as a misleading "missing visual attributes" error |

All of these are honest failures: the API never reports a successful analysis
it did not receive. Manual metadata entry is unaffected in every case.

### Why the Vision prompt repeats the output shape

Cohere's structured-output mode does not guarantee the model returns an
*instance* of the supplied schema. With the deeply nested vision schema the
model sometimes replies with the schema document itself, which is not usable
analysis. The prompt therefore appends a concrete JSON skeleton showing the
exact shape expected, and the parser rejects a schema echo with a specific
error rather than a generic one.

## 4. Data, backup, and restore

The database is a single SQLite file (`stockpilot.db` by default). Uploaded
images live separately in `uploads/`.

**Backup**

1. Stop the backend (Ctrl+C in the start script's terminal).
2. Copy `stockpilot.db` to a safe location.
3. Copy `uploads/` if you want the image files too.

**Restore**

1. Stop the backend.
2. Put `stockpilot.db` (and `uploads/`) back in place.
3. Start the backend. Migrations run automatically and are idempotent.

Restoring an older database file into a newer codebase is safe as long as
migrations are append-only — never edit a migration that has already been
applied; add a new numbered one instead.

## 5. Storage and cleanup

- Uploaded images are stored under server-generated filenames in `uploads/`.
- `DELETE /api/v1/assets/{id}` removes the asset, its submissions (foreign
  key cascade), its vision insights, and the app-managed image copy.
- Deleting an asset never touches files you referenced by `file_reference`.
- The Library's "Remove from Library" action is **Archive**
  (`PATCH archived=true`), which is fully reversible.

## 6. Troubleshooting

**Port already in use** — the start script names the owning process. Stop it,
or change the port in `app/main.py` / `frontend/vite.config.ts`.

**`No module named 'app'`** — run uvicorn from the repository root.

**Frontend loads but the API calls fail** — the Vite dev server proxies `/api`
to `127.0.0.1:8000`. Confirm the backend is up with
`curl.exe http://127.0.0.1:8000/api/v1/ai/status`.

**"AI not configured" in the UI** — the frontend reads `GET /api/v1/ai/status`.
If that endpoint reports configured but the UI still shows the notice, the
frontend is talking to a different backend instance.

**Database is locked** — two backends are running against the same file.
Stop the extra one; the start script prevents this in the normal path.

**Tests fail with import errors** — activate the venv and install
`requirements.txt` before running pytest.
