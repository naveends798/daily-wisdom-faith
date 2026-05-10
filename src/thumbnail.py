"""Process the user-provided thumbnail: validate format, resize/crop to
1280x720, recompress under YouTube's 2 MB limit. No text overlay, no AI
generation — the user's image is used as-is."""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

W, H = 1280, 720
MAX_BYTES = 2 * 1024 * 1024  # YouTube thumbnail max
JPEG_QUALITY_START = 92
JPEG_QUALITY_FLOOR = 70


def prepare_thumbnail(src: Path, out_path: Path) -> Path:
    """Resize/crop src to 1280x720, save as JPEG under 2 MB. Returns out_path."""
    img = Image.open(src)
    img = img.convert("RGB")

    # Cover-fit to 16:9 with center crop (preserves the user's framing intent
    # while guaranteeing exact YouTube dimensions).
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = W / H

    if src_ratio > target_ratio:
        # Source is wider than 16:9 — crop sides.
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    elif src_ratio < target_ratio:
        # Source is taller than 16:9 — crop top and bottom.
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))

    img = img.resize((W, H), Image.LANCZOS)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Try decreasing quality until under YouTube's 2 MB cap.
    quality = JPEG_QUALITY_START
    while True:
        img.save(out_path, format="JPEG", quality=quality, optimize=True)
        size = out_path.stat().st_size
        if size <= MAX_BYTES or quality <= JPEG_QUALITY_FLOOR:
            break
        quality -= 4
    log.info("Prepared thumbnail %s (%d bytes, q=%d)", out_path, size, quality)
    return out_path
