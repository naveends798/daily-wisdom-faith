#!/usr/bin/env python3
"""Run the Daily Wisdom Faith video pipeline locally.

Usage:
    python run.py              # process today's input folder (input/YYYY-MM-DD/)
    python run.py 2026-05-12   # process a specific date folder

Steps:
  1. Put your audio (.mp3), background video (.mp4), and thumbnail (.jpg)
     into  input/YYYY-MM-DD/
  2. Optionally add notes.txt with metadata hints
  3. Run this script
  4. Find finished video + upload card in  output/YYYY-MM-DD/
"""
import sys
from datetime import date


def _parse_date(arg: str) -> date:
    try:
        return date.fromisoformat(arg)
    except ValueError:
        print(f"Error: date must be YYYY-MM-DD, got {arg!r}")
        sys.exit(1)


if __name__ == "__main__":
    target = _parse_date(sys.argv[1]) if len(sys.argv) > 1 else None

    from src.main import run
    sys.exit(run(target_date=target))
