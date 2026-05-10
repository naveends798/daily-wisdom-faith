"""Standalone CLI to top up the rolling 30-day folder window.

Useful if a workflow run was skipped/failed and the window has been depleted.
Safe to run repeatedly.

    python scripts/maintain_folders.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import drive  # noqa: E402
from src.config import Config  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = Config.load()
    drive.ensure_special_folders(cfg)
    created = drive.maintain_window(cfg)
    if created:
        print(f"Created {len(created)} folder(s):")
        for n in created:
            print(f"  - {n}")
    else:
        print("Window already full; nothing to create.")


if __name__ == "__main__":
    main()
