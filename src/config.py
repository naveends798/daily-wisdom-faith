"""Centralized config loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


REPO_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = REPO_ROOT / "work"


def _required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(
            f"Missing required env var: {name}. See .env.example and SETUP.md."
        )
    return val


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Config:
    channel_name: str
    channel_handle: str
    notify_email: str
    timezone: str
    publish_hour_local: int

    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    drive_queue_folder_id: str

    ollama_api_base: str
    ollama_api_key: str
    ollama_model: str

    smtp_user: str
    smtp_app_password: str

    @classmethod
    def load(cls, *, require_runtime: bool = True) -> "Config":
        """Load config. If require_runtime is False, only branding fields are
        validated — useful for offline tests and the bootstrap script."""
        load = _required if require_runtime else _optional
        return cls(
            channel_name=_optional("CHANNEL_NAME", "Daily Wisdom Faith"),
            channel_handle=_optional("CHANNEL_HANDLE", "@DailyWisdomFaith"),
            notify_email=_optional("NOTIFY_EMAIL", "naveends798@gmail.com"),
            timezone=_optional("TIMEZONE", "Asia/Kolkata"),
            publish_hour_local=int(_optional("PUBLISH_HOUR_LOCAL", "9")),
            google_client_id=load("GOOGLE_CLIENT_ID"),
            google_client_secret=load("GOOGLE_CLIENT_SECRET"),
            google_refresh_token=load("GOOGLE_REFRESH_TOKEN"),
            drive_queue_folder_id=load("DRIVE_QUEUE_FOLDER_ID"),
            ollama_api_base=_optional("OLLAMA_API_BASE", "https://ollama.com/api"),
            ollama_api_key=load("OLLAMA_API_KEY"),
            ollama_model=_optional("OLLAMA_MODEL", "deepseek-v4-flash"),
            smtp_user=_optional("SMTP_USER", "naveends798@gmail.com"),
            # Optional: leave SMTP_APP_PASSWORD unset to disable email
            # notifications. The notifier becomes a no-op; GitHub Actions
            # itself still emails the account owner on workflow failures.
            smtp_app_password=_optional("SMTP_APP_PASSWORD"),
        )
