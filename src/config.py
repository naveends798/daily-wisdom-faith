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
INPUT_DIR = REPO_ROOT / "input"
PUBLISHED_DIR = REPO_ROOT / "published"


def _required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(
            f"Missing required env var: {name}. Add it to your .env file."
        )
    return val


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Config:
    channel_name: str
    channel_handle: str
    notify_email: str

    openai_api_base: str
    openai_api_key: str
    openai_model: str

    smtp_user: str
    smtp_app_password: str

    @classmethod
    def load(cls) -> "Config":
        return cls(
            channel_name=_optional("CHANNEL_NAME", "Daily Wisdom Faith"),
            channel_handle=_optional("CHANNEL_HANDLE", "@DailyWisdomFaith"),
            notify_email=_optional("NOTIFY_EMAIL", "naveends798@gmail.com"),
            openai_api_base=_optional("OPENAI_API_BASE", "https://api.openai.com/v1"),
            openai_api_key=_required("OPENAI_API_KEY"),
            openai_model=_optional("OPENAI_MODEL", "gpt-4o-mini"),
            smtp_user=_optional("SMTP_USER", "naveends798@gmail.com"),
            smtp_app_password=_optional("SMTP_APP_PASSWORD"),
        )
