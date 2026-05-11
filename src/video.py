"""Stitch a final 720p MP4 from a looping background video and an audio track.

720p (1280x720) is YouTube's "HD" tier. For gospel meditation videos that are
mostly static atmospheric loops, 720p is visually indistinguishable from 1080p
in the YouTube feed and encodes ~4x faster on small CI runners. 24 fps is
enough for ambient loop content.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)


_PROGRESS_RE = re.compile(r"out_time_us=(\d+)|frame=(\d+)|speed=([0-9.]+)x")


def _run_with_progress(cmd: list[str], total_seconds: float) -> None:
    """Run FFmpeg and emit progress every ~10s so the workflow log shows
    forward motion (instead of going silent for minutes)."""
    log.info("$ %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    last_log = time.monotonic()
    last_pct = -10
    assert proc.stdout is not None
    for line in proc.stdout:
        m = re.search(r"out_time_ms=(\d+)", line)
        if not m:
            continue
        elapsed_s = int(m.group(1)) / 1_000_000.0
        pct = min(100, int(elapsed_s / total_seconds * 100)) if total_seconds else 0
        now = time.monotonic()
        if pct >= last_pct + 10 or now - last_log >= 10:
            log.info("FFmpeg progress: %d%% (%.1fs / %.1fs)", pct, elapsed_s, total_seconds)
            last_log = now
            last_pct = pct
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed (exit {rc})")


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


def _concat_audio(audio_paths: list[Path], dest: Path) -> Path:
    """Concatenate multiple audio files into one using ffmpeg concat demuxer."""
    if len(audio_paths) == 1:
        return audio_paths[0]
    list_file = dest.parent / "audio_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in audio_paths),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(dest),
    ]
    log.info("Concatenating %d audio files → %s", len(audio_paths), dest.name)
    subprocess.run(cmd, check=True)
    list_file.unlink(missing_ok=True)
    return dest


def stitch(
    audio_paths: "Path | list[Path]",
    video_path: Path,
    out_path: Path,
    *,
    fade_in: float = 2.0,
    fade_out: float = 3.0,
) -> Path:
    """Loop the background video to match audio duration, fade audio, encode.

    audio_paths can be a single Path or a list of Paths — multiple files are
    concatenated in sorted order before stitching (for long-form videos).
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not on PATH")

    if isinstance(audio_paths, Path):
        audio_paths = [audio_paths]

    audio_paths = sorted(audio_paths)
    combined_audio = out_path.parent / "_combined_audio.mp3"
    audio_path = _concat_audio(audio_paths, combined_audio)

    audio_dur = _probe_duration(audio_path)
    fade_out_start = max(0.0, audio_dur - fade_out)
    log.info("Audio duration: %.2fs (fade-out at %.2fs)", audio_dur, fade_out_start)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Note: -t (output duration cap) is mandatory because -shortest is
    # unreliable when paired with -stream_loop -1 (infinite input). Without
    # -t, FFmpeg can encode for hours without exiting.
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "warning",
        "-progress", "pipe:1",
        "-stream_loop", "-1",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-filter_complex",
        (
            "[0:v]scale=1280:720:force_original_aspect_ratio=increase,"
            "crop=1280:720,setsar=1,fps=24[v];"
            f"[1:a]afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={fade_out_start:.2f}:d={fade_out}[a]"
        ),
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-ar", "44100",
        "-t", f"{audio_dur:.2f}",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run_with_progress(cmd, audio_dur)

    # Remove temp concat file if we created one
    if combined_audio.exists() and combined_audio != audio_paths[0]:
        combined_audio.unlink(missing_ok=True)

    final_dur = _probe_duration(out_path)
    final_size = out_path.stat().st_size / (1024 * 1024)
    log.info(
        "Stitched video: %.2fs, %.1f MB → %s", final_dur, final_size, out_path
    )
    return out_path
