"""One-time interactive bootstrap.

Run locally on your Mac:

    python scripts/bootstrap.py

What it does:
  1. Walks you through Google OAuth (opens a browser)
  2. Saves the resulting refresh token
  3. Creates the prayer-channel-queue/ folder in your Drive (if missing)
  4. Pre-creates the next 30 date folders + default/ + published/
  5. Prints all the values you need to paste into GitHub Secrets

Requires:
  - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment OR a
    client_secret.json downloaded from Google Cloud Console.

Re-running is safe — it will not duplicate folders.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from src import drive  # noqa: E402
from src.google_auth import SCOPES  # noqa: E402


@dataclass
class _PartialCfg:
    """Just enough config to construct google credentials."""
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    drive_queue_folder_id: str = ""


def _load_client_creds() -> tuple[str, str]:
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    csec = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if cid and csec:
        return cid, csec

    secret_path = REPO_ROOT / "client_secret.json"
    if secret_path.exists():
        data = json.loads(secret_path.read_text())
        installed = data.get("installed") or data.get("web") or {}
        return installed["client_id"], installed["client_secret"]

    print(
        "ERROR: Provide GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET via env vars\n"
        "       OR place client_secret.json (from Google Cloud Console) at the repo root.",
        file=sys.stderr,
    )
    sys.exit(2)


def _run_oauth(client_id: str, client_secret: str) -> str:
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        print(
            "ERROR: Google did not return a refresh token. Re-run with a fresh "
            "consent (revoke prior access at https://myaccount.google.com/permissions).",
            file=sys.stderr,
        )
        sys.exit(2)
    return creds.refresh_token


def main() -> None:
    print("=" * 70)
    print(" Daily Wisdom Faith — bootstrap")
    print("=" * 70)

    client_id, client_secret = _load_client_creds()
    print("\nStep 1/3: Sign in with the Google account that owns @DailyWisdomFaith.")
    print("          A browser window will open.\n")
    refresh_token = _run_oauth(client_id, client_secret)
    print("✓ OAuth complete\n")

    cfg = _PartialCfg(
        google_client_id=client_id,
        google_client_secret=client_secret,
        google_refresh_token=refresh_token,
    )

    print("Step 2/3: Locating or creating prayer-channel-queue/ in your Drive...")
    queue_id = drive.find_or_create_root(cfg, name="prayer-channel-queue")
    cfg.drive_queue_folder_id = queue_id
    print(f"✓ Drive queue folder ID: {queue_id}\n")

    print("Step 3/3: Pre-creating folders (next 30 days + default/ + published/)...")
    drive.ensure_special_folders(cfg)
    created = drive.maintain_window(cfg)
    print(f"✓ Created {len(created)} new date folders\n")

    print("=" * 70)
    print(" PASTE THESE INTO GITHUB SECRETS")
    print("=" * 70)
    print("(Settings → Secrets and variables → Actions → New repository secret)\n")
    print(f"GOOGLE_CLIENT_ID         = {client_id}")
    print(f"GOOGLE_CLIENT_SECRET     = {client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN     = {refresh_token}")
    print(f"DRIVE_QUEUE_FOLDER_ID    = {queue_id}")
    print()
    print("And the rest from your accounts:")
    print("  OPENAI_API_KEY, SMTP_APP_PASSWORD (optional)")
    print()
    print("Open Drive → 'prayer-channel-queue' → drop your audio + video into")
    print("today's date folder. The cron will publish it at 9 AM IST.")


if __name__ == "__main__":
    main()
