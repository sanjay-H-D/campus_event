"""Application configuration loaded from environment variables and .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_setting(name: str, default: str = "") -> str:
    """Return a trimmed environment setting after loading the project .env."""
    return os.getenv(name, default).strip()


DATABASE_URL = get_setting("DATABASE_URL", "sqlite:///./campus_event_engine.db")
SECRET_KEY = get_setting("SECRET_KEY")
