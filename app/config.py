# load .env, konfigurasi global

import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
ALLOWED_API_KEYS = [k.strip() for k in (os.getenv("ALLOWED_API_KEYS") or "").split(",") if k.strip()]
RATE_LIMIT = os.getenv("RATE_LIMIT", "10/minute")
