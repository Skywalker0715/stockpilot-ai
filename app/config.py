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

