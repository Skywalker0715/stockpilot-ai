# StockPilot AI — FastAPI entry point.

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply pending schema migrations before serving traffic.
    conn = db.connect()
    try:
        db.run_migrations(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="StockPilot AI", version="0.1.0", lifespan=lifespan)

# Local, single-user MVP: only the Vite dev frontend may call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# API routes (/api/v1/...)
from app.routes import ai, assets, insights, submissions, uploads, vision  # noqa: E402

app.include_router(assets.router)
app.include_router(submissions.router)
app.include_router(insights.router)
app.include_router(uploads.router)
app.include_router(ai.router)
app.include_router(vision.router)
