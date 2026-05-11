"""Daily pipeline entry point. Run by GitHub Actions cron each morning IST.

Pipeline:
  1. Find today's Drive folder (fallback to default/ if today is empty)
  2. Download audio + video + user-supplied thumbnail image (+ optional notes)
  3. Generate title/description/tags via OpenAI (gpt-4o-mini)
  4. Resize/compress the user thumbnail to YouTube's 1280x720 / 2 MB spec
  5. Stitch final 1080p MP4 with looping video and faded audio
  6. Upload finished video + thumbnail + metadata to Drive ready-to-upload/<date>/
  7. Archive the Drive folder under published/ (with artifacts)
  8. Maintain rolling 30-day folder window
  9. Email with Drive link for manual YouTube upload
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from collections import deque
from datetime import date

from .config import WORK_DIR, Config
from . import drive, notifier, openai_client, thumbnail, video

LOG_TAIL = deque(maxlen=80)


class _TailHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        LOG_TAIL.append(self.format(record))


def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    tail = _TailHandler()
    tail.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[stream, tail])


def _log_tail_text() -> str:
    return "\n".join(LOG_TAIL)


def run() -> int:
    _setup_logging()
    log = logging.getLogger("main")
    cfg = Config.load()

    today = date.today()
    work = WORK_DIR / today.strftime("%Y-%m-%d")
    work.mkdir(parents=True, exist_ok=True)

    # One-off override: SOURCE_FOLDER_NAME lets workflow_dispatch re-process a
    # folder under published/ without touching the normal daily flow. When set
    # we skip archival (the source is already archived).
    source_override = os.environ.get("SOURCE_FOLDER_NAME", "").strip()
    using_fallback = False
    skip_archive = False

    if source_override:
        log.info("SOURCE_FOLDER_NAME override: %r", source_override)
        folder = drive.find_folder_in_published(cfg, source_override)
        if not folder:
            raise RuntimeError(
                f"SOURCE_FOLDER_NAME={source_override!r} not found under published/"
            )
        skip_archive = True
    else:
        folder = drive.find_today_folder(cfg, today=today)
        if not folder:
            log.warning("Today's folder %s missing; falling back to default/", today)
            folder = drive.find_default_folder(cfg)
            using_fallback = True
            if not folder:
                raise RuntimeError(
                    "No today-folder and no default/ folder. Channel cannot publish."
                )

    try:
        audio_path, video_path, image_path, notes, audio_stem = drive.download_assets(
            cfg, folder, work
        )

        if using_fallback:
            audio_stem = f"daily-wisdom-{today.strftime('%Y-%m-%d')}"

        log.info("Generating metadata for stem=%r", audio_stem)
        meta = openai_client.generate_metadata(
            cfg, audio_filename_stem=audio_stem, notes=notes
        )
        log.info(
            "Metadata: title=%r tags=%d category=%s",
            meta.title, len(meta.tags), meta.category_id,
        )

        thumb_path = work / "thumbnail.jpg"
        thumbnail.prepare_thumbnail(image_path, thumb_path)

        final_path = work / "final.mp4"
        video.stitch(audio_path, video_path, final_path)

        meta_path = work / "metadata.json"
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

        folder_name = today.strftime("%Y-%m-%d")
        drive_link = drive.upload_ready_video(
            cfg,
            folder_name=folder_name,
            final_path=final_path,
            thumb_path=thumb_path,
            meta_path=meta_path,
        )

        if not using_fallback and not skip_archive:
            drive.archive_folder(
                cfg, folder, artifacts=[final_path, thumb_path, meta_path]
            )
        if not skip_archive:
            drive.maintain_window(cfg, today=today)

        notifier.notify_success(
            cfg,
            drive_link=drive_link,
            title=meta.title,
            scheduled_for=today.strftime("%Y-%m-%d"),
        )
        log.info("Pipeline complete. videoId=%s", video_id)
        return 0

    except Exception as e:
        log.exception("Pipeline failed")
        try:
            notifier.notify_failure(
                cfg, error=f"{type(e).__name__}: {e}", log_tail=_log_tail_text()
            )
        except Exception:
            log.exception("Also failed to send failure email")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run())
