from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path

from .ffmpeg_utils import require_ffmpeg

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts"}

_FRAME_TIME_RE = re.compile(r"pts_time:(?P<time>[\d.]+)")
_RMS_RE = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(?P<rms>-?[\d.]+|-inf)")


@dataclasses.dataclass
class Candidate:
    file: Path
    time: float
    score: float


def find_recordings(clips_dir: Path) -> list[Path]:
    if not clips_dir.is_dir():
        raise FileNotFoundError(f"clips_dir does not exist or is not a directory: {clips_dir}")
    files = sorted(
        p for p in clips_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not files:
        raise FileNotFoundError(f"No video files found in clips_dir: {clips_dir}")
    return files


def _loudness_curve(path: Path) -> list[tuple[float, float]]:
    """Return (time_seconds, loudness_score) samples, roughly one per second.

    Loudness is the RMS level in dB of ~1-second audio windows; louder
    moments (higher, less-negative dB) score higher and are treated as more
    likely to be gameplay highlights (action, explosions, crowd/commentary
    reactions, etc).
    """
    cmd = [
        require_ffmpeg(), "-i", str(path),
        "-af",
        "asetnsamples=n=44100,astats=metadata=1:reset=1,"
        "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    points: list[tuple[float, float]] = []
    pending_time = None
    for line in result.stdout.splitlines():
        time_match = _FRAME_TIME_RE.search(line)
        if time_match:
            pending_time = float(time_match.group("time"))
            continue
        rms_match = _RMS_RE.search(line)
        if rms_match and pending_time is not None:
            rms_text = rms_match.group("rms")
            score = -100.0 if rms_text == "-inf" else float(rms_text)
            points.append((pending_time, score))
            pending_time = None
    return points


def _pick_peaks(
    points: list[tuple[float, float]], min_gap: float, max_count: int
) -> list[tuple[float, float]]:
    """Greedily pick the highest-scoring times, at least min_gap apart."""
    ranked = sorted(points, key=lambda p: p[1], reverse=True)
    picked: list[tuple[float, float]] = []
    for time, score in ranked:
        if len(picked) >= max_count:
            break
        if all(abs(time - t) >= min_gap for t, _ in picked):
            picked.append((time, score))
    return picked


def select_highlights(
    clips_dir: Path,
    count: int,
    duration: float,
    min_gap: float,
    *,
    verbose: bool = False,
) -> list[Candidate]:
    """Scan every recording in clips_dir and return `count` highlight moments.

    Each recording is scored second-by-second for loudness. The strongest
    non-overlapping peaks across all recordings are kept, then returned in
    chronological order (by file, then by time within the file) so callers
    can assign them to storyline scenes in the order those scenes are
    listed.
    """
    files = find_recordings(clips_dir)
    spacing = max(min_gap, duration)

    candidates: list[Candidate] = []
    for f in files:
        if verbose:
            print(f"  scanning {f.name} for highlights...")
        points = _loudness_curve(f)
        for time, score in _pick_peaks(points, min_gap=spacing, max_count=count):
            candidates.append(Candidate(file=f, time=time, score=score))

    if len(candidates) < count:
        raise ValueError(
            f"Only found {len(candidates)} highlight candidate(s) across "
            f"{len(files)} recording(s) in {clips_dir}, but the storyline needs {count}. "
            "Add more/longer recordings, lower 'highlight_min_gap', or reduce the number "
            "of scenes without an explicit 'clip'."
        )

    top = sorted(candidates, key=lambda c: c.score, reverse=True)[:count]
    file_order = {f: i for i, f in enumerate(files)}
    top.sort(key=lambda c: (file_order[c.file], c.time))
    return top
