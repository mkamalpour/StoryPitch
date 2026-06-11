"""
config.py - Centralized Configuration for Story Maker Bot
==========================================================

This file contains ALL configuration settings for the Story Maker Bot project.
It provides sensible defaults and loads from environment variables when available.

USAGE:
    from config import API_HOST, API_PORT, DATABASE_URL, LM_STUDIO_URL
    
ENVIRONMENT VARIABLES:
    You can override any setting by creating a .env file or setting environment variables:
    - API_HOST: Host for the FastAPI server (default: 127.0.0.1)
    - API_PORT: Port for the FastAPI server (default: 8000)
    - DATABASE_URL: SQLite database URL (default: sqlite:///story.db)
    - LM_STUDIO_URL: URL for local LM Studio server (default: http://127.0.0.1:1234)
    - HF_API_KEY: Hugging Face API key for online AI models
    - TELEGRAM_TOKEN: Telegram bot token for Telegram integration
    
CONFIGURATION SECTIONS:
    1. API Configuration - FastAPI server settings
    2. Database Configuration - SQLite database settings
    3. LLM Configuration - AI model settings (local & online)
    4. Telegram Bot Configuration - Telegram bot settings
    5. Story Generation Settings - Story complexity and behavior
    6. Networking Configuration - HTTP timeouts and concurrency
    7. Logging Configuration - Log files and levels

NOTES:
    - No .env file is required - all settings have sensible defaults
    - Settings are loaded in order: defaults → environment variables → .env file
    - This file is imported by all modules, so changes here affect the entire project
"""

from pathlib import Path
import os
import logging
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

# Load .env if present for easier setup (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # .env is optional

# Base directory and database path
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "story.db"

# ============================================================================
# API Configuration
# ============================================================================
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_KEY = os.getenv("API_KEY", "")  # Optional API key for authentication

# Computed API base URL (centralized)
API_BASE_URL = os.getenv("API_BASE", f"http://{API_HOST}:{API_PORT}")

# ============================================================================
# Database Configuration
# ============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# ============================================================================
# LLM Configuration
# ============================================================================
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "local")   # 'local' or 'hf'

# LM Studio (Local AI)
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "")    # If empty, auto-detect
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "") # Optional
LM_STUDIO_USE_CHAT = os.getenv("LM_STUDIO_USE_CHAT", "true").lower() in ("1","true","yes")

# Hugging Face (Online AI)
HF_API_KEY = os.getenv("HF_API_KEY", "")  # REQUIRED: Set via environment variable or .env file
HF_MODEL = os.getenv("HF_MODEL", "gpt2")

# LLM Generation Settings
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))  # Max tokens per generation (increased for complete JSON output)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.8"))  # Creativity level (0.0-1.0) - increased for more creative, unpredictable stories
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.95"))  # Nucleus sampling
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # Cache time-to-live in seconds
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "true").lower() in ("1","true","yes")

# ============================================================================
# Telegram Bot Configuration
# ============================================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7605233774:AAE-Ug1s-UbEdPzUGa3QemENDK1_US4Kn8w")  # Required for Telegram bot
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")  # Optional webhook

# ============================================================================
# Story Generation Settings
# ============================================================================
# Number of choices to generate per story step
STORY_CHOICES_COUNT = int(os.getenv("STORY_CHOICES_COUNT", "4"))

# Narration length (in sentences)
STORY_NARRATION_MIN_SENTENCES = int(os.getenv("STORY_NARRATION_MIN_SENTENCES", "5"))
STORY_NARRATION_MAX_SENTENCES = int(os.getenv("STORY_NARRATION_MAX_SENTENCES", "10"))

# Story complexity and depth
STORY_COMPLEXITY = os.getenv("STORY_COMPLEXITY", "medium")  # low, medium, high - Changed to HIGH for maximum intelligence and depth
STORY_ENABLE_CLUES = os.getenv("STORY_ENABLE_CLUES", "true").lower() in ("1","true","yes")
STORY_ENABLE_CONSEQUENCES = os.getenv("STORY_ENABLE_CONSEQUENCES", "true").lower() in ("1","true","yes")

# ============================================================================
# Networking Configuration
# ============================================================================
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "300"))  # Request timeout in seconds for AI and external calls
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))

# Logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "story_maker.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Log rotation settings
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB per log file (reduced to prevent bloat)
LOG_BACKUP_COUNT = 2  # Keep only 2 backup files (reduced from 5)
LOG_RETENTION_MINUTES = 60  # Delete logs older than 60 minutes (1 hour)

def cleanup_old_logs():
    """Remove log files older than LOG_RETENTION_MINUTES"""
    try:
        current_time = time.time()
        retention_seconds = LOG_RETENTION_MINUTES * 60  # Convert minutes to seconds
        
        deleted_count = 0
        for log_file in LOG_DIR.glob("*.log*"):
            # Skip the main log file
            if log_file == LOG_FILE:
                continue
            
            # Check file age
            file_age = current_time - log_file.stat().st_mtime
            if file_age > retention_seconds:
                try:
                    log_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Warning: Could not delete old log {log_file}: {e}")
        
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old log file(s) (older than {LOG_RETENTION_MINUTES} minutes)")
    except Exception as e:
        print(f"Warning: Log cleanup failed: {e}")


def configure_logging():
    """Configure logging with rotation and automatic cleanup"""
    # Clean old logs first
    cleanup_old_logs()
    
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    
    # Remove old handlers to avoid duplicates (useful in reload)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)
    
    # Enhanced formatter with more details
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler with size-based rotation
    # Rotates when file reaches LOG_MAX_BYTES, keeps LOG_BACKUP_COUNT backups
    fh = RotatingFileHandler(
        LOG_FILE, 
        maxBytes=LOG_MAX_BYTES, 
        backupCount=LOG_BACKUP_COUNT, 
        encoding="utf-8"
    )
    fh.setFormatter(formatter)
    root.addHandler(fh)
    
    # Console handler with same format
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    root.addHandler(ch)
    
    # Log startup message
    root.info("=" * 80)
    root.info("🚀 Story Maker Bot - Logging Initialized")
    root.info(f"📁 Log file: {LOG_FILE}")
    root.info(f"📊 Max size: {LOG_MAX_BYTES / 1024 / 1024:.1f}MB, Backups: {LOG_BACKUP_COUNT}")
    root.info(f"🧹 Retention: {LOG_RETENTION_MINUTES} minutes")
    root.info("=" * 80)

configure_logging()
logger = logging.getLogger(__name__)
logger.info("Config loaded. DB=%s MODEL=%s LM_STUDIO_URL=%s", DATABASE_URL, DEFAULT_MODEL, LM_STUDIO_URL)
