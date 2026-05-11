"""Daily pipeline — run locally to stitch a gospel video and generate upload card.

Usage:
    python run.py              # process today's input folder
    python run.py 2026-05-12   # process a specific date

Input folder:  input/YYYY-MM-DD/
  - One audio file  (.mp3 / .wav / .m4a)
  - One video file  (.mp4 / .mov)
  - One image file  (.jpg / .jpeg / .png)
  - notes.txt       (optional — metadata hints)

Output folder: output/YYYY-MM-DD/
  - final.mp4           ← upload this to YouTube
  - thumbnail.jpg       ← upload as thumbnail
  - metadata.json       ← saved metadata
  - YOUTUBE-UPLOAD.txt  ← copy-paste fields for YouTube
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Optional

from .config import INPUT_DIR, PUBLISHED_DIR, Config
from . import openai_client, thumbnail, video
from .notifier import notify_success, notify_failure


log = logging.getLogger(__name__)

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _setup_logging() -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)],
                        format="%(asctime)s %(levelname)s: %(message)s")


def _find_file(folder: Path, exts: set[str]) -> Optional[Path]:
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in exts and f.name != "final.mp4":
            return f
    return None


def _find_all_files(folder: Path, exts: set[str]) -> list[Path]:
    return sorted(f for f in folder.iterdir() if f.suffix.lower() in exts and f.name != "final.mp4")


def _write_upload_card(
    path: Path,
    *,
    date_str: str,
    meta: openai_client.Metadata,
    output_dir: Path,
    channel_handle: str,
) -> None:
    tags_str = ", ".join(meta.tags)
    card = f"""╔══════════════════════════════════════════════════════════════╗
  YOUTUBE UPLOAD CARD — {date_str}
  Daily Wisdom & Faith  |  {channel_handle}
╚══════════════════════════════════════════════════════════════╝

━━━  TITLE  (copy exactly into YouTube title field)  ━━━━━━━━━

{meta.title}

━━━  DESCRIPTION  (copy everything between the lines)  ━━━━━━━

{meta.description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━  TAGS  (paste into YouTube tags field)  ━━━━━━━━━━━━━━━━━━

{tags_str}

━━━  OTHER SETTINGS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Category:       Music (select "Music" from the dropdown)
Made for kids:  No
Thumbnail:      Upload  thumbnail.jpg  from this folder
Playlist:       Daily Gospel Songs (create if it doesn't exist)
Visibility:     Public  (or Schedule for 9:00 AM IST)

━━━  FILES IN THIS FOLDER  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Video to upload:   {output_dir / "final.mp4"}
Thumbnail image:   {output_dir / "thumbnail.jpg"}

╔══════════════════════════════════════════════════════════════╗
  Done! Upload final.mp4 to YouTube, then paste the fields
  above. Upload thumbnail.jpg as the custom thumbnail.
╚══════════════════════════════════════════════════════════════╝
"""
    path.write_text(card, encoding="utf-8")
    log.info("YouTube upload card saved: %s", path)


def run(target_date: Optional[date] = None) -> int:
    _setup_logging()
    cfg = Config.load()
    today = target_date or date.today()
    date_str = today.strftime("%Y-%m-%d")

    input_dir = INPUT_DIR / date_str
    output_dir = PUBLISHED_DIR / date_str

    if not input_dir.exists():
        log.error("Input folder not found: %s", input_dir)
        log.error("Create the folder and add your audio, video, and thumbnail files.")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio_paths = _find_all_files(input_dir, AUDIO_EXTS)
        video_path = _find_file(input_dir, VIDEO_EXTS)
        image_path = _find_file(input_dir, IMAGE_EXTS)
        notes_file = input_dir / "notes.txt"
        notes = notes_file.read_text(encoding="utf-8").strip() if notes_file.exists() else None

        if not audio_paths:
            raise FileNotFoundError(f"No audio file in {input_dir}")
        if not video_path:
            raise FileNotFoundError(f"No video file in {input_dir}")
        if not image_path:
            raise FileNotFoundError(f"No thumbnail image in {input_dir}")

        for ap in audio_paths:
            log.info("Audio:     %s", ap.name)
        log.info("Video:     %s", video_path.name)
        log.info("Thumbnail: %s", image_path.name)
        if len(audio_paths) > 1:
            log.info("Multiple audio files — will concatenate in filename order")

        audio_stem = audio_paths[0].stem
        log.info("Generating metadata for: %s", audio_stem)
        meta = openai_client.generate_metadata(cfg, audio_filename_stem=audio_stem, notes=notes)
        log.info("Title: %s", meta.title)
        log.info("Tags:  %d tags", len(meta.tags))

        thumb_path = output_dir / "thumbnail.jpg"
        thumbnail.prepare_thumbnail(image_path, thumb_path)

        final_path = output_dir / "final.mp4"
        video.stitch(audio_paths, video_path, final_path)

        meta_path = output_dir / "metadata.json"
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

        card_path = output_dir / "YOUTUBE-UPLOAD.txt"
        _write_upload_card(
            card_path,
            date_str=date_str,
            meta=meta,
            output_dir=output_dir,
            channel_handle=cfg.channel_handle,
        )

        notify_success(cfg, drive_link=str(output_dir), title=meta.title, scheduled_for=date_str)

        log.info("=" * 60)
        log.info("DONE. Output folder: %s", output_dir)
        log.info("  1. Open YOUTUBE-UPLOAD.txt for all copy-paste fields")
        log.info("  2. Upload final.mp4 to YouTube")
        log.info("  3. Upload thumbnail.jpg as the custom thumbnail")
        log.info("=" * 60)
        return 0

    except Exception as e:
        log.exception("Pipeline failed")
        try:
            notify_failure(cfg, error=f"{type(e).__name__}: {e}", log_tail="")
        except Exception:
            pass
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run())
