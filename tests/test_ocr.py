import shutil
import subprocess
from pathlib import Path

import pytest

from storyline_editor.ocr import build_text_index, search_index

HAS_TOOLS = (
    shutil.which("ffmpeg") is not None
    and shutil.which("ffprobe") is not None
    and shutil.which("tesseract") is not None
)
pytestmark = pytest.mark.skipif(not HAS_TOOLS, reason="requires ffmpeg/ffprobe/tesseract")


def _make_clip_with_text(path: Path, *, text: str, at: float, duration: float) -> None:
    end = at + 2
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=640x360:d={duration}",
            "-vf",
            f"drawtext=text='{text}':fontcolor=white:fontsize=50:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,{at},{end})'",
            "-t", str(duration), str(path),
        ],
        check=True, capture_output=True,
    )


def test_build_text_index_and_search(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip_with_text(clip, text="99 POTENTIAL", at=3, duration=10)

    index = build_text_index(clip, interval=1.0, cache_dir=tmp_path / "cache")

    matches = search_index(index, "99 POTENTIAL")
    assert matches
    assert all(2.5 <= t <= 5.5 for t, _score in matches)


def test_search_index_no_match_returns_empty(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip_with_text(clip, text="HAT TRICK", at=3, duration=6)

    index = build_text_index(clip, interval=1.0, cache_dir=tmp_path / "cache")

    assert search_index(index, "SOMETHING ELSE ENTIRELY") == []


def test_build_text_index_uses_cache(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip_with_text(clip, text="MOTM", at=1, duration=4)
    cache_dir = tmp_path / "cache"

    first = build_text_index(clip, interval=1.0, cache_dir=cache_dir)
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1

    second = build_text_index(clip, interval=1.0, cache_dir=cache_dir)
    assert first == second
