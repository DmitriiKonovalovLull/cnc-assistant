"""
Production configuration for CNC Assistant.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://cnc_user:cnc_pass@localhost:5432/cnc_db"
)

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Telegram Bot
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Standards
STANDARDS_STORAGE_DIR = BASE_DIR / "standards" / "storage"
STANDARDS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Rate Limiting
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_BLOCK_DURATION = int(os.getenv("RATE_LIMIT_BLOCK_DURATION", "300"))

# Performance
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
PDF_PARSING_THREAD_POOL_SIZE = int(os.getenv("PDF_PARSING_THREAD_POOL_SIZE", "4"))

# Security
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Feature Flags
ENABLE_INTERNET_SEARCH = os.getenv("ENABLE_INTERNET_SEARCH", "true").lower() == "true"
ENABLE_OCR = os.getenv("ENABLE_OCR", "true").lower() == "true"
ENABLE_STANDARDS_UPLOAD = os.getenv("ENABLE_STANDARDS_UPLOAD", "true").lower() == "true"

# Monitoring
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"

# Internationalization
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru")
SUPPORTED_LANGUAGES = ["ru", "en", "zh"]

# Regional Standards
REGIONAL_STANDARDS_ENABLED = os.getenv("REGIONAL_STANDARDS_ENABLED", "true").lower() == "true"
