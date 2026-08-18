import shutil
import subprocess
from pathlib import Path

import pytest

from storyline_editor.guide_project import find_guide_file, load_guide_project

HAS_TOOLS = (
    shutil.which("ffmpeg") is not None
    and shutil.which("ffprobe") is not None
    and shutil.which("tesseract") is not None
)
pytestmark = pytest.mark.skipif(not HAS_TOOLS, reason="requires ffmpeg/ffprobe/tesseract")

GUIDE = """
============================================================
SECTION 1 — REVEAL
============================================================

TARGET LENGTH
-------------
8-10 seconds

GRAPHIC
-------
99 POTENTIAL

VO
--
"Ninety-nine potential."


============================================================
SECTION 2 — ACTION
============================================================

TARGET LENGTH
-------------
8-10 seconds

VO
--
"So naturally, we were never selling him."
"""


def _make_clip(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-filter_complex",
            "aevalsrc=0.03*sin(2*PI*220*t):d=15:s=44100[a1];"
            "aevalsrc=0.9*sin(2*PI*440*t):d=2:s=44100[a2];"
            "aevalsrc=0.03*sin(2*PI*220*t):d=13:s=44100[a3];"
            "[a1][a2][a3]concat=n=3:v=0:a=1[a];"
            "color=c=blue:s=640x360:d=30,"
            "drawtext=text='99 POTENTIAL':fontcolor=white:fontsize=40:"
            "x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,5,7)'[v]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac", "-t", "30", str(path),
        ],
        check=True, capture_output=True,
    )


def test_find_guide_file(tmp_path):
    assert find_guide_file(tmp_path) is None
    (tmp_path / "guide.txt").write_text(GUIDE)
    assert find_guide_file(tmp_path) == tmp_path / "guide.txt"


def test_load_guide_project_builds_scenes_and_matches_vo(tmp_path):
    project = tmp_path / "proj"
    (project / "clips").mkdir(parents=True)
    (project / "vo").mkdir()
    _make_clip(project / "clips" / "match.mp4")
    (project / "vo" / "01.mp3").write_bytes(b"")
    (project / "vo" / "02.mp3").write_bytes(b"")
    guide_file = project / "guide.txt"
    guide_file.write_text(GUIDE)

    storyline, anchors = load_guide_project(project, guide_file)

    assert len(storyline.scenes) == 2
    assert storyline.scenes[0].guide_number == 1
    assert storyline.scenes[0].graphic_text == "99 POTENTIAL"
    assert storyline.scenes[0].vo_lines == [project / "vo" / "01.mp3"]
    assert storyline.scenes[1].vo_lines == [project / "vo" / "02.mp3"]

    assert len(anchors) == 2
    assert anchors[0].confirmed is True
    assert 4.5 <= anchors[0].time <= 7.5


def test_load_guide_project_missing_clips_dir(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    guide_file = project / "guide.txt"
    guide_file.write_text(GUIDE)

    with pytest.raises(FileNotFoundError):
        load_guide_project(project, guide_file)
