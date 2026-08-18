from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .ffmpeg_utils import require_ffmpeg


class TesseractNotFoundError(RuntimeError):
    pass


def require_tesseract() -> str:
    exe = shutil.which("tesseract")
    if exe is None:
        raise TesseractNotFoundError(
            "tesseract was not found on PATH. It's needed to read on-screen text "
            "(ratings, scores, grades) for guide-driven editing. Install it with "
            "`brew install tesseract` (macOS), `sudo apt install tesseract-ocr` "
            "(Debian/Ubuntu), or https://github.com/tesseract-ocr/tesseract."
        )
    return exe


def _normalize(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9%'’ ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_text_index(clip: Path, interval: float, cache_dir: Path) -> list:
    """OCR-scan a video roughly every `interval` seconds; return
    [(time_seconds, normalized_text), ...]. Results are cached on disk keyed
    by the clip's path/size/mtime/interval, since OCR-ing a long recording
    takes a while and guide files get tweaked and re-run often.
    """
    cache_file = _cache_path(clip, interval, cache_dir)
    if cache_file.exists():
        with cache_file.open("r", encoding="utf-8") as f:
            return [tuple(entry) for entry in json.load(f)]

    require_tesseract()
    ffmpeg = require_ffmpeg()

    index = []
    with tempfile.TemporaryDirectory(prefix="koanda_ocr_") as tmp:
        tmp_dir = Path(tmp)
        subprocess.run(
            [
                ffmpeg, "-y", "-i", str(clip),
                "-vf", f"fps=1/{interval}",
                str(tmp_dir / "f_%06d.png"),
            ],
            check=True, capture_output=True,
        )
        frames = sorted(tmp_dir.glob("f_*.png"))
        for i, frame in enumerate(frames):
            time = i * interval
            result = subprocess.run(
                ["tesseract", str(frame), "stdout"],
                capture_output=True, text=True,
            )
            text = _normalize(result.stdout)
            if text:
                index.append((time, text))

    cache_dir.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(index, f)
    return index


def _cache_path(clip: Path, interval: float, cache_dir: Path) -> Path:
    stat = clip.stat()
    key = f"{clip.resolve()}|{stat.st_size}|{stat.st_mtime}|{interval}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def search_index(index: list, keyword: str) -> list:
    """Return [(time, score)] for occurrences of keyword in the index,
    highest score first. score 1.0 = exact substring match, lower = partial
    word overlap (to tolerate OCR noise)."""
    needle = _normalize(keyword)
    if not needle:
        return []
    needle_words = set(needle.split())

    matches = []
    for time, text in index:
        if needle in text:
            matches.append((time, 1.0))
            continue
        text_words = set(text.split())
        if not needle_words:
            continue
        overlap = len(needle_words & text_words) / len(needle_words)
        if overlap >= 0.6:
            matches.append((time, overlap))
    matches.sort(key=lambda m: m[1], reverse=True)
    return matches
