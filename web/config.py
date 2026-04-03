import os

from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_V1_PREFIX = "/api/v1"
API_BASE_URL = f"{BACKEND_URL}{API_V1_PREFIX}"
STORAGE_SECRET = os.getenv("STORAGE_SECRET", "change-me-to-a-random-string")
