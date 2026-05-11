"""Google Drive operations: folder maintenance, asset download, archival."""
from __future__ import annotations

import io
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .config import Config
from .google_auth import credentials

log = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
WINDOW_DAYS = 30


def _service(cfg: Config):
    return build("drive", "v3", credentials=credentials(cfg), cache_discovery=False)


def _list_children(svc, parent_id: str) -> list[dict]:
    """Return all non-trashed children of a folder."""
    out: list[dict] = []
    page_token: Optional[str] = None
    while True:
        resp = svc.files().list(
            q=f"'{parent_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageToken=page_token,
            pageSize=200,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def _find_child(svc, parent_id: str, name: str) -> Optional[dict]:
    safe = name.replace("'", "\\'")
    resp = svc.files().list(
        q=f"'{parent_id}' in parents and name = '{safe}' and trashed = false",
        fields="files(id, name, mimeType)",
        pageSize=1,
    ).execute()
    files = resp.get("files", [])
    return files[0] if files else None


def _create_folder(svc, parent_id: str, name: str) -> dict:
    body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    return svc.files().create(body=body, fields="id, name").execute()


def _download_file(svc, file_id: str, dest: Path) -> None:
    request = svc.files().get_media(fileId=file_id)
    with io.FileIO(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    log.info("Downloaded %s → %s (%d bytes)", file_id, dest, dest.stat().st_size)


def ensure_special_folders(cfg: Config) -> dict[str, str]:
    """Ensure default/ and published/ exist; return their IDs."""
    svc = _service(cfg)
    out = {}
    for name in ("default", "published"):
        existing = _find_child(svc, cfg.drive_queue_folder_id, name)
        if existing:
            out[name] = existing["id"]
        else:
            created = _create_folder(svc, cfg.drive_queue_folder_id, name)
            out[name] = created["id"]
            log.info("Created Drive folder %s/%s", cfg.drive_queue_folder_id, name)
    return out


def maintain_window(cfg: Config, *, today: Optional[date] = None) -> list[str]:
    """Ensure the next WINDOW_DAYS date folders exist. Returns names created."""
    today = today or date.today()
    svc = _service(cfg)
    created: list[str] = []
    for offset in range(WINDOW_DAYS):
        d = today + timedelta(days=offset)
        name = d.strftime("%Y-%m-%d")
        if _find_child(svc, cfg.drive_queue_folder_id, name) is None:
            _create_folder(svc, cfg.drive_queue_folder_id, name)
            created.append(name)
    if created:
        log.info("Created %d future folders: %s", len(created), ", ".join(created))
    return created


def find_today_folder(cfg: Config, *, today: Optional[date] = None) -> Optional[dict]:
    today = today or date.today()
    svc = _service(cfg)
    return _find_child(svc, cfg.drive_queue_folder_id, today.strftime("%Y-%m-%d"))


def find_default_folder(cfg: Config) -> Optional[dict]:
    svc = _service(cfg)
    return _find_child(svc, cfg.drive_queue_folder_id, "default")


def find_folder_in_published(cfg: Config, name: str) -> Optional[dict]:
    """Find a subfolder by name under prayer-channel-queue/published/."""
    svc = _service(cfg)
    published = _find_child(svc, cfg.drive_queue_folder_id, "published")
    if not published:
        return None
    return _find_child(svc, published["id"], name)


def download_assets(
    cfg: Config, folder: dict, dest_dir: Path
) -> tuple[Path, Path, Path, Optional[str], str]:
    """Download audio + video + user-supplied thumbnail image from a Drive
    folder. Returns (audio_path, video_path, image_path, notes_text,
    audio_filename_stem).

    Picks the first .mp3/.wav/.m4a/.aac/.flac/.ogg as audio, the first
    .mp4/.mov/.webm/.mkv as video, and the first .jpg/.jpeg/.png as
    thumbnail. If a notes.txt exists, returns its text content too.
    """
    svc = _service(cfg)
    children = _list_children(svc, folder["id"])

    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
    video_exts = {".mp4", ".mov", ".webm", ".mkv"}
    image_exts = {".jpg", ".jpeg", ".png"}
    # Skip generated artifacts that may exist when re-processing an archived
    # folder via SOURCE_FOLDER_NAME (final.mp4 is our stitched output;
    # metadata.json is the saved sidecar).
    ARTIFACT_NAMES = {"final.mp4", "metadata.json"}

    def _is_source(c: dict, exts: set[str]) -> bool:
        name = c["name"]
        return name not in ARTIFACT_NAMES and Path(name).suffix.lower() in exts

    audio = next((c for c in children if _is_source(c, audio_exts)), None)
    video = next((c for c in children if _is_source(c, video_exts)), None)
    image = next((c for c in children if _is_source(c, image_exts)), None)
    notes = next((c for c in children if c["name"].lower() == "notes.txt"), None)

    if not audio:
        raise FileNotFoundError(f"No audio file in Drive folder {folder['name']}")
    if not video:
        raise FileNotFoundError(f"No video file in Drive folder {folder['name']}")
    if not image:
        raise FileNotFoundError(
            f"No thumbnail image (.jpg/.png) in Drive folder {folder['name']}"
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    audio_path = dest_dir / audio["name"]
    video_path = dest_dir / video["name"]
    image_path = dest_dir / image["name"]
    _download_file(svc, audio["id"], audio_path)
    _download_file(svc, video["id"], video_path)
    _download_file(svc, image["id"], image_path)

    notes_text: Optional[str] = None
    if notes:
        notes_path = dest_dir / "notes.txt"
        _download_file(svc, notes["id"], notes_path)
        notes_text = notes_path.read_text(encoding="utf-8", errors="ignore").strip()

    audio_stem = Path(audio["name"]).stem
    return audio_path, video_path, image_path, notes_text, audio_stem


def archive_folder(cfg: Config, folder: dict, *, artifacts: list[Path]) -> None:
    """Move the folder under published/, optionally uploading artifacts to it."""
    svc = _service(cfg)
    specials = ensure_special_folders(cfg)
    published_id = specials["published"]

    if artifacts:
        for art in artifacts:
            if not art.exists():
                continue
            media = MediaFileUpload(str(art), resumable=False)
            svc.files().create(
                body={"name": art.name, "parents": [folder["id"]]},
                media_body=media,
                fields="id",
            ).execute()
            log.info("Uploaded artifact to Drive: %s", art.name)

    # Move folder: remove parent (queue), add parent (published)
    svc.files().update(
        fileId=folder["id"],
        addParents=published_id,
        removeParents=cfg.drive_queue_folder_id,
        fields="id, parents",
    ).execute()
    log.info("Archived folder %s under published/", folder["name"])


def find_or_create_root(cfg_partial, name: str = "prayer-channel-queue") -> str:
    """First-run helper: look up or create the queue root folder by name in My Drive.

    cfg_partial only needs google_client_id, google_client_secret, google_refresh_token.
    Returns the folder ID.
    """
    svc = build("drive", "v3", credentials=credentials(cfg_partial), cache_discovery=False)
    safe = name.replace("'", "\\'")
    resp = svc.files().list(
        q=(
            f"name = '{safe}' and mimeType = '{FOLDER_MIME}' "
            f"and 'root' in parents and trashed = false"
        ),
        fields="files(id, name)",
        pageSize=1,
    ).execute()
    found = resp.get("files", [])
    if found:
        return found[0]["id"]
    body = {"name": name, "mimeType": FOLDER_MIME}
    created = svc.files().create(body=body, fields="id").execute()
    return created["id"]
