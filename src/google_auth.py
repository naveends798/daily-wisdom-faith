"""Single OAuth credential factory shared by Drive and YouTube clients."""
from __future__ import annotations

from google.oauth2.credentials import Credentials

from .config import Config

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/drive",
]


def credentials(cfg: Config) -> Credentials:
    """Build a Credentials object from the stored refresh token."""
    return Credentials(
        token=None,
        refresh_token=cfg.google_refresh_token,
        client_id=cfg.google_client_id,
        client_secret=cfg.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
