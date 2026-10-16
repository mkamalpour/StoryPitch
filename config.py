"""StoryPitch settings. Environment variables override the optional root .env."""

from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "story.db"

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_KEY = os.getenv("API_KEY", "")
API_BASE_URL = os.getenv("API_BASE", f"http://{API_HOST}:{API_PORT}")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "local")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "")
LM_STUDIO_USE_CHAT = os.getenv("LM_STUDIO_USE_CHAT", "true").lower() in {
    "1",
    "true",
    "yes",
}
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "true").lower() in {"1", "true", "yes"}
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.8"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.95"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "300"))
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
STORY_CHOICES_COUNT = int(os.getenv("STORY_CHOICES_COUNT", "4"))
STORY_NARRATION_MIN_SENTENCES = int(os.getenv("STORY_NARRATION_MIN_SENTENCES", "5"))
STORY_NARRATION_MAX_SENTENCES = int(os.getenv("STORY_NARRATION_MAX_SENTENCES", "10"))
STORY_COMPLEXITY = os.getenv("STORY_COMPLEXITY", "medium")
STORY_ENABLE_CLUES = os.getenv("STORY_ENABLE_CLUES", "true").lower() in {
    "1",
    "true",
    "yes",
}
STORY_ENABLE_CONSEQUENCES = os.getenv("STORY_ENABLE_CONSEQUENCES", "true").lower() in {
    "1",
    "true",
    "yes",
}

LOG_DIR = Path(os.getenv("STORYPITCH_LOG_DIR", str(BASE_DIR / "logs")))
LOG_FILE = LOG_DIR / "story_maker.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 2


def configure_logging():
    """Rotate bounded logs without truncating them or disturbing other handlers."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "storypitch_handler", False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers = [
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ]
    for handler in handlers:
        handler.storypitch_handler = True
        handler.setFormatter(formatter)
        root.addHandler(handler)
