import shutil
import subprocess
from pathlib import Path

import pytest

from storyline_editor.anchors import find_section_anchors
from storyline_editor.guide import GuideSection

HAS_TOOLS = (
    shutil.which("ffmpeg") is not None
    and shutil.which("ffprobe") is not None
    and shutil.which("tesseract") is not None
)
pytestmark = pytest.mark.skipif(not HAS_TOOLS, reason="requires ffmpeg/ffprobe/tesseract")


def _section(number, title, keywords):
    return GuideSection(
        number=number, title=title, target_length=(10, 15), vo_lines=[],
        graphic_text=keywords, graphic_hold_seconds=2.5, keywords=keywords,
        freeze_seconds=0.0, zoom_percent=0.0, raw_fields={},
    )


def _make_clip(path: Path, *, duration: float, loud_at: float, texts) -> None:
    """A clip with a loud burst at `loud_at` and drawtext overlays from
    `texts` = [(text, start, end)]."""
    quiet1 = loud_at
    loud = 2.0
    quiet2 = max(0.0, duration - loud_at - loud)
    audio = (
        f"aevalsrc=0.03*sin(2*PI*220*t):d={quiet1}:s=44100[q1];"
        f"aevalsrc=0.9*sin(2*PI*440*t):d={loud}:s=44100[l];"
        f"aevalsrc=0.03*sin(2*PI*220*t):d={quiet2}:s=44100[q2];"
        f"[q1][l][q2]concat=n=3:v=0:a=1[a]"
    )
    video_filters = [f"color=c=blue:s=640x360:d={duration}"]
    label = "v0"
    filter_complex = audio + f";{video_filters[0]}[{label}]"
    for i, (text, start, end) in enumerate(texts):
        next_label = f"v{i + 1}"
        filter_complex += (
            f";[{label}]drawtext=text='{text}':fontcolor=white:fontsize=40:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,{start},{end})'[{next_label}]"
        )
        label = next_label
    subprocess.run(
        [
            "ffmpeg", "-y", "-filter_complex", filter_complex,
            "-map", f"[{label}]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac", "-t", str(duration),
            str(path),
        ],
        check=True, capture_output=True,
    )


def test_find_section_anchors_confirms_ocr_matches_and_flags_fallback(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    _make_clip(
        clips_dir / "session1.mp4",
        duration=20, loud_at=10,
        texts=[("99 POTENTIAL", 3, 5), ("HAT TRICK", 15, 17)],
    )

    sections = [
        _section(1, "REVEAL", ["99 POTENTIAL"]),
        _section(2, "ACTION", []),
        _section(3, "TRICK", ["HAT TRICK"]),
    ]

    anchors = find_section_anchors(
        sections, clips_dir, tmp_path / "cache", ocr_interval=1.0
    )

    by_number = {a.section.number: a for a in anchors}
    assert by_number[1].confirmed is True
    assert 2.5 <= by_number[1].time <= 5.5
    assert by_number[3].confirmed is True
    assert 14.5 <= by_number[3].time <= 17.5

    assert by_number[2].confirmed is False
    assert by_number[1].time <= by_number[2].time <= by_number[3].time
