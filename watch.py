#!/usr/bin/env python3
"""Auto-watcher: monitors input/ folders and runs the pipeline automatically.

As soon as a date folder has all three assets (audio + video + thumbnail),
it stitches the video and saves everything to published/YYYY-MM-DD/.

Usage:
    python watch.py          # runs forever, checks every 60 seconds
    python watch.py --once   # check right now and exit

How it works:
  - Scans every folder in input/YYYY-MM-DD/
  - When it finds one with audio + video + thumbnail (and not yet published),
    it runs the pipeline automatically
  - Finished videos land in published/YYYY-MM-DD/ with:
      final.mp4           ← upload this to YouTube
      thumbnail.jpg       ← upload as custom thumbnail
      YOUTUBE-UPLOAD.txt  ← copy-paste title, description, tags
      metadata.json       ← saved metadata
"""
import sys
import time
import logging
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("watcher")

# Lazy import so config errors surface cleanly
from src.config import INPUT_DIR, PUBLISHED_DIR

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
CHECK_INTERVAL = 60  # seconds between scans


def _assets_ready(folder: Path) -> bool:
    files = [f for f in folder.iterdir() if f.is_file()]
    has_audio = any(f.suffix.lower() in AUDIO_EXTS for f in files)
    has_video = any(f.suffix.lower() in VIDEO_EXTS and f.name != "final.mp4" for f in files)
    has_image = any(f.suffix.lower() in IMAGE_EXTS for f in files)
    if has_audio and has_video and has_image:
        audio_count = sum(1 for f in files if f.suffix.lower() in AUDIO_EXTS)
        log.info("  %s — ready (%d audio file(s) + video + thumbnail)", folder.name, audio_count)
        return True
    return False


def _already_published(date_str: str) -> bool:
    return (PUBLISHED_DIR / date_str / "final.mp4").exists()


def _is_date_folder(name: str) -> bool:
    try:
        date.fromisoformat(name)
        return True
    except ValueError:
        return False


def scan_and_process() -> list[str]:
    """Scan input/ for ready folders. Process each one. Return list of dates processed."""
    processed = []
    if not INPUT_DIR.exists():
        return processed

    folders = sorted(
        f for f in INPUT_DIR.iterdir()
        if f.is_dir() and _is_date_folder(f.name)
    )

    for folder in folders:
        date_str = folder.name
        if _already_published(date_str):
            continue
        if not _assets_ready(folder):
            continue

        log.info("━━━ All assets ready for %s — starting pipeline ━━━", date_str)
        try:
            from src.main import run
            result = run(target_date=date.fromisoformat(date_str))
            if result == 0:
                log.info("✅ %s — finished. Check published/%s/", date_str, date_str)
                processed.append(date_str)
            else:
                log.error("❌ %s — pipeline returned error", date_str)
        except Exception as e:
            log.exception("❌ %s — pipeline crashed: %s", date_str, e)

    return processed


def main() -> None:
    once = "--once" in sys.argv

    log.info("Daily Wisdom Faith — Asset Watcher")
    log.info("Watching:  %s", INPUT_DIR)
    log.info("Output to: %s", PUBLISHED_DIR)
    if once:
        log.info("Mode: single check")
    else:
        log.info("Mode: continuous (checking every %ds)", CHECK_INTERVAL)
        log.info("Press Ctrl+C to stop.")
    log.info("")

    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    if once:
        processed = scan_and_process()
        if not processed:
            log.info("No folders ready yet. Add audio + video + thumbnail to an input/YYYY-MM-DD/ folder.")
        return

    while True:
        scan_and_process()
        log.info("Waiting %ds before next check... (Ctrl+C to stop)", CHECK_INTERVAL)
        try:
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log.info("Watcher stopped.")
            break


if __name__ == "__main__":
    main()
