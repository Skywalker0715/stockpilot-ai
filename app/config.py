# Runtime configuration loaded from environment variables.

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite database file. Overridable for tests and portable installs.
DB_PATH = Path(os.getenv("STOCKPILOT_DB_PATH", str(BASE_DIR / "stockpilot.db")))

# The MVP is single-user and local: only the frontend dev server may call the API.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# ---- Cohere vision metadata generation -------------------------------------
# COHERE_API_KEY stays server-side in .env; it is never sent to the frontend.
# Get a key at https://dashboard.cohere.com/api-keys and put it in .env.

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "").strip()

# Cohere Chat API base (v2). Override only for testing against a stub.
COHERE_BASE_URL = os.getenv("COHERE_BASE_URL", "https://api.cohere.com").rstrip("/")

# Vision-capable model: command-a-vision-07-2025, Cohere's first multimodal
# model (docs.cohere.com/docs/image-inputs). Override with STOCKPILOT_AI_MODEL
# if Cohere changes the lineup or this account lacks access to it.
AI_MODEL = (
    os.getenv("STOCKPILOT_AI_MODEL", "command-a-vision-07-2025").strip()
    or "command-a-vision-07-2025"
)

# Whole-request timeout for the Cohere call (vision requests can be slow).
AI_TIMEOUT_SECONDS = float(os.getenv("STOCKPILOT_AI_TIMEOUT", "60"))

# ---- Upload storage --------------------------------------------------------
# Application-managed directory for uploaded images (gitignored). The server
# only ever reads/writes inside this directory for image handling; client
# paths are never trusted.

UPLOAD_DIR = Path(os.getenv("STOCKPILOT_UPLOAD_DIR", str(BASE_DIR / "uploads")))

# Upload size limit (bytes). 10 MiB keeps requests comfortably under the
# Cohere 20 MB per-request cap after base64 expansion for typical stock photos;
# the limit is configurable for local use.
MAX_UPLOAD_BYTES = int(os.getenv("STOCKPILOT_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

