from __future__ import annotations

import re
import shutil
import subprocess


class FFmpegNotFoundError(RuntimeError):
    pass


def require_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise FFmpegNotFoundError(
            "ffmpeg was not found on PATH. Install it and make sure it's accessible "
            "(e.g. `sudo apt install ffmpeg` or https://ffmpeg.org/download.html)."
        )
    return exe


def require_ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if exe is None:
        raise FFmpegNotFoundError(
            "ffprobe was not found on PATH. It ships alongside ffmpeg; reinstall ffmpeg "
            "if only the ffmpeg binary is present."
        )
    return exe


def probe_duration(path) -> float:
    cmd = [
        require_ffprobe(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed to read duration for {path}:\n{result.stderr}")
    return float(result.stdout.strip())


_TIME_RE = re.compile(
    r"^(?:(?:(?P<hours>\d+):)?(?P<minutes>\d+):)?(?P<seconds>\d+(?:\.\d+)?)$"
)


def time_to_seconds(value: str) -> float:
    """Parse a time value in SS, MM:SS, or HH:MM:SS(.ms) form into seconds."""
    text = str(value).strip()
    match = _TIME_RE.match(text)
    if not match:
        raise ValueError(f"Invalid time value: {value!r} (expected SS, MM:SS, or HH:MM:SS)")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds"))
    return hours * 3600 + minutes * 60 + seconds


def run_ffmpeg(args: list[str]) -> None:
    cmd = [require_ffmpeg(), "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode})\n"
            f"command: {' '.join(cmd)}\n"
            f"stderr:\n{result.stderr}"
        )
