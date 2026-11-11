"""Environment-backed application settings and shared paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=BACKEND_DIR / ".env")

ROOT = str(BACKEND_DIR.parent)
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
MODEL_NAME = os.getenv("MODEL_NAME", "gurubot/girl")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
APP_SESSION_SECRET = os.getenv("APP_SESSION_SECRET", "")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SD_PATH = os.path.normpath(os.path.join(ROOT, os.getenv("SD_PATH", "models/dreamshaper")))
VAE_PATH = os.path.normpath(os.path.join(ROOT, os.getenv("VAE_PATH", "models/vae")))
MEDIA_FOLDER = os.path.normpath(os.path.join(ROOT, "media"))
IMAGE_FOLDER = os.path.join(MEDIA_FOLDER, "images")
GIF_FOLDER = os.path.join(MEDIA_FOLDER, "gifs")
AVATAR_FOLDER = os.path.join(MEDIA_FOLDER, "avatars")
DATA_DIR = os.path.normpath(os.getenv("DATA_DIR", ROOT))
HISTORY_DIR = os.path.join(DATA_DIR, "chat_sessions")
SERVER_DATA_VERSION_FILE = os.path.join(DATA_DIR, ".server-data-version")

MAX_HISTORY = 20
MAX_INPUT_CHARS = 1000
MAX_PROMPT_CHARS = 300
MAX_PERSONALITY_CHARS = 80
MAX_AVATAR_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_AVATAR_PIXELS = 25_000_000
IMAGE_WIDTH = 576
IMAGE_HEIGHT = 768
GIF_WIDTH = 384
GIF_HEIGHT = 512
DEFAULT_SESSION_ID = "default"

for directory in (IMAGE_FOLDER, GIF_FOLDER, AVATAR_FOLDER, HISTORY_DIR):
    os.makedirs(directory, exist_ok=True)
