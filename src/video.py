"""Stitch a final 1080p MP4 from a looping background video and an audio track."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _run(cmd: list[str]) -> None:
    log.info("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("ffmpeg stderr: %s", proc.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode})")


def _probe_duration(path: Path) -> float:
    """Return media duration in seconds via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def stitch(
    audio_path: Path,
    video_path: Path,
    out_path: Path,
    *,
    fade_in: float = 2.0,
    fade_out: float = 3.0,
) -> Path:
    """Loop the background video to match audio duration, fade audio, encode."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not on PATH")

    audio_dur = _probe_duration(audio_path)
    fade_out_start = max(0.0, audio_dur - fade_out)
    log.info("Audio duration: %.2fs (fade-out at %.2fs)", audio_dur, fade_out_start)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-filter_complex",
        (
            "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,setsar=1,fps=30[v];"
            f"[1:a]afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade_out}[a]"
        ),
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-shortest",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd)

    final_dur = _probe_duration(out_path)
    log.info("Stitched video duration: %.2fs → %s", final_dur, out_path)
    return out_path
