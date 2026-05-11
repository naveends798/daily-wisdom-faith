"""Email notifications via Gmail SMTP."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import Config

log = logging.getLogger(__name__)


def _send(cfg: Config, *, subject: str, body: str) -> None:
    if not cfg.smtp_app_password:
        log.warning("SMTP_APP_PASSWORD not set; skipping email")
        return
    msg = EmailMessage()
    msg["From"] = cfg.smtp_user
    msg["To"] = cfg.notify_email
    msg["Subject"] = subject
    msg.set_content(body)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(cfg.smtp_user, cfg.smtp_app_password)
        s.send_message(msg)
    log.info("Email sent to %s: %s", cfg.notify_email, subject)


def notify_success(cfg: Config, *, drive_link: str, title: str, scheduled_for: str) -> None:
    body = (
        f"Daily Wisdom Faith — video ready for upload.\n\n"
        f"Title: {title}\n"
        f"Date: {scheduled_for}\n\n"
        f"Your video is ready in Google Drive. Open the link below,\n"
        f"download final.mp4, and upload it manually to YouTube:\n\n"
        f"{drive_link}\n"
    )
    _send(cfg, subject=f"✅ Daily Wisdom — video ready: {title[:60]}", body=body)


def notify_failure(cfg: Config, *, error: str, log_tail: str) -> None:
    body = (
        f"Daily Wisdom Faith — upload FAILED.\n\n"
        f"Error: {error}\n\n"
        f"--- last log lines ---\n{log_tail}\n"
    )
    _send(cfg, subject="❌ Daily Wisdom — upload failed", body=body)
