"""Local smoke test of metadata generation + thumbnail processing.

Provide a filename stem and a path to a thumbnail image; uses your real
OpenAI key but does NOT touch Drive or YouTube. Outputs to ./out/.

    python scripts/test_pipeline.py "trust-in-the-lord-psalm-23" /path/to/image.jpg
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import openai_client, thumbnail  # noqa: E402
from src.config import Config  # noqa: E402


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if len(sys.argv) < 3:
        print(
            'Usage: python scripts/test_pipeline.py "<filename-stem>" <image-path>',
            file=sys.stderr,
        )
        sys.exit(2)
    stem = sys.argv[1]
    image_src = Path(sys.argv[2]).expanduser().resolve()
    if not image_src.exists():
        print(f"Image not found: {image_src}", file=sys.stderr)
        sys.exit(2)

    cfg = Config.load(require_runtime=False)
    if not cfg.openai_api_key:
        print("Need OPENAI_API_KEY in env or .env", file=sys.stderr)
        sys.exit(2)

    out_dir = REPO_ROOT / "out"
    out_dir.mkdir(exist_ok=True)

    meta = openai_client.generate_metadata(cfg, audio_filename_stem=stem, notes=None)
    print("\n--- METADATA ---")
    print(f"Title       : {meta.title}")
    print(f"Tags        : {meta.tags}")
    print(f"Hero        : {meta.thumbnail_words}")
    print(f"Subtitle    : {meta.thumbnail_subtitle}")
    print(f"Scripture   : {meta.scripture_reference}")
    print(f"Description :\n{meta.description}\n")

    thumb = out_dir / "thumbnail.jpg"
    thumbnail.prepare_thumbnail(image_src, thumb)
    print(f"\n✓ Wrote thumbnail → {thumb}")
    print("  Open it to verify it cropped/resized correctly.")


if __name__ == "__main__":
    main()
