"""Upload a video and its thumbnail to YouTube, scheduled at today 9 AM IST."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Config
from .google_auth import credentials

log = logging.getLogger(__name__)

# India Standard Time is fixed UTC+05:30 (no DST).
IST = timezone(timedelta(hours=5, minutes=30))


def _service(cfg: Config):
    return build("youtube", "v3", credentials=credentials(cfg), cache_discovery=False)


def _publish_at_iso(cfg: Config, *, now_utc: Optional[datetime] = None) -> str:
    """Compute today 09:00 IST in RFC3339; if already past, use tomorrow.
    YouTube refuses scheduled times in the past."""
    now_utc = now_utc or datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)
    target = now_ist.replace(
        hour=cfg.publish_hour_local, minute=0, second=0, microsecond=0
    )
    if target <= now_ist + timedelta(minutes=2):
        target = target + timedelta(days=1)
    return target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _upload_with_resume(request) -> dict:
    """Drive the resumable upload to completion."""
    response = None
    progress = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                if pct >= progress + 10:
                    log.info("Upload progress: %d%%", pct)
                    progress = pct
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                log.warning("Transient HTTP %s, retrying chunk", e.resp.status)
                time.sleep(2)
                continue
            raise
    return response


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True,
)
def upload_video(
    cfg: Config,
    *,
    video_path: Path,
    thumbnail_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    schedule: bool = True,
) -> str:
    """Upload a video, attach the thumbnail, optionally schedule public release.
    Returns the YouTube video ID."""
    svc = _service(cfg)

    status: dict = {
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": True,  # AI-generated music disclosure
    }
    if schedule:
        status["privacyStatus"] = "private"
        status["publishAt"] = _publish_at_iso(cfg)
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }

    media = MediaFileUpload(
        str(video_path), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4"
    )
    request = svc.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=True,
    )

    log.info("Uploading video: %s", title)
    response = _upload_with_resume(request)
    video_id = response["id"]
    log.info("Uploaded videoId=%s", video_id)

    # Attach thumbnail
    if thumbnail_path.exists():
        svc.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
        ).execute()
        log.info("Thumbnail set for %s", video_id)

    return video_id
