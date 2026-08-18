import shutil
import subprocess
from pathlib import Path

import pytest

from storyline_editor.highlights import (
    Candidate,
    _pick_peaks,
    find_recordings,
    select_highlights,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_pick_peaks_prefers_higher_scores_and_respects_min_gap():
    points = [(0.0, -30.0), (1.0, -5.0), (2.0, -6.0), (10.0, -4.0), (11.0, -20.0)]

    picked = _pick_peaks(points, min_gap=5.0, max_count=10)

    picked_times = sorted(t for t, _ in picked)
    # (1.0, -5.0) and (2.0, -6.0) are within min_gap of each other, so only
    # the stronger of the two survives; (10.0, -4.0) is far enough away.
    assert picked_times == [1.0, 10.0]


def test_pick_peaks_respects_max_count():
    points = [(float(i), -float(i)) for i in range(20)]
    picked = _pick_peaks(points, min_gap=1.0, max_count=3)
    assert len(picked) == 3


def test_find_recordings_filters_by_extension(tmp_path):
    (tmp_path / "clip.mp4").touch()
    (tmp_path / "clip.mov").touch()
    (tmp_path / "notes.txt").touch()

    found = find_recordings(tmp_path)

    assert [f.name for f in found] == ["clip.mov", "clip.mp4"]


def test_find_recordings_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_recordings(tmp_path / "does_not_exist")


def test_find_recordings_no_videos(tmp_path):
    (tmp_path / "readme.txt").touch()
    with pytest.raises(FileNotFoundError):
        find_recordings(tmp_path)


def _make_tone_clip(path: Path, *, loud_at: float, total_duration: float) -> None:
    """Build a short video whose audio is quiet except for a 2s loud burst."""
    quiet_before = loud_at
    loud = 2.0
    quiet_after = max(0.0, total_duration - loud_at - loud)
    filter_complex = (
        f"aevalsrc=0.03*sin(2*PI*220*t):d={quiet_before}:s=44100[q1];"
        f"aevalsrc=0.9*sin(2*PI*440*t):d={loud}:s=44100[l];"
        f"aevalsrc=0.03*sin(2*PI*220*t):d={quiet_after}:s=44100[q2];"
        f"[q1][l][q2]concat=n=3:v=0:a=1[a];"
        f"color=c=blue:s=64x64:d={total_duration}[v]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac", "-t", str(total_duration),
            str(path),
        ],
        check=True, capture_output=True,
    )


@pytest.mark.skipif(not HAS_FFMPEG, reason="requires ffmpeg/ffprobe")
def test_select_highlights_finds_loud_moments(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    _make_tone_clip(clips_dir / "a.mp4", loud_at=5.0, total_duration=15.0)
    _make_tone_clip(clips_dir / "b.mp4", loud_at=8.0, total_duration=15.0)

    highlights = select_highlights(clips_dir, count=2, duration=4.0, min_gap=3.0)

    assert len(highlights) == 2
    assert all(isinstance(h, Candidate) for h in highlights)
    # chronological order: a.mp4 sorts before b.mp4
    assert highlights[0].file.name == "a.mp4"
    assert highlights[1].file.name == "b.mp4"
    assert 4.0 <= highlights[0].time <= 7.5
    assert 7.0 <= highlights[1].time <= 10.5


@pytest.mark.skipif(not HAS_FFMPEG, reason="requires ffmpeg/ffprobe")
def test_select_highlights_raises_when_not_enough_candidates(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    _make_tone_clip(clips_dir / "a.mp4", loud_at=5.0, total_duration=15.0)

    with pytest.raises(ValueError):
        select_highlights(clips_dir, count=5, duration=4.0, min_gap=3.0)
