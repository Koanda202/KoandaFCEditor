import shutil
import subprocess
from pathlib import Path

import pytest

from storyline_editor.project import load_project

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_project(tmp_path: Path, story_lines: list[str], vo_names: tuple = ()) -> Path:
    project = tmp_path / "myproject"
    (project / "clips").mkdir(parents=True)
    (project / "clips" / "a.mp4").touch()
    (project / "story.txt").write_text("\n".join(story_lines) + "\n")
    if vo_names:
        vo_dir = project / "vo"
        vo_dir.mkdir()
        for name in vo_names:
            _make_silence(vo_dir / name, duration=1.0)
    return project


def _make_silence(path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=mono:d={duration}",
            str(path),
        ],
        check=True, capture_output=True,
    )


def test_load_project_without_vo(tmp_path):
    project = _make_project(tmp_path, ["Opening hook", "Boss fight", "Victory"])

    storyline = load_project(project)

    assert storyline.title == "myproject"
    assert storyline.clips_dir == project / "clips"
    assert [s.name for s in storyline.scenes] == ["Opening hook", "Boss fight", "Victory"]
    assert all(s.vo is None for s in storyline.scenes)
    assert all(s.clip_volume == 1.0 for s in storyline.scenes)
    assert storyline.output == project / "output" / "final_video.mp4"


def test_load_project_ignores_blank_and_comment_lines(tmp_path):
    project = _make_project(tmp_path, ["# a comment", "", "Opening hook", "  ", "Victory"])

    storyline = load_project(project)

    assert [s.name for s in storyline.scenes] == ["Opening hook", "Victory"]


def test_load_project_missing_clips_dir(tmp_path):
    project = tmp_path / "myproject"
    project.mkdir()
    (project / "story.txt").write_text("Opening hook\n")

    with pytest.raises(FileNotFoundError):
        load_project(project)


def test_load_project_missing_story_file(tmp_path):
    project = tmp_path / "myproject"
    (project / "clips").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        load_project(project)


def test_load_project_empty_story_file(tmp_path):
    project = tmp_path / "myproject"
    (project / "clips").mkdir(parents=True)
    (project / "story.txt").write_text("# only a comment\n")

    with pytest.raises(ValueError):
        load_project(project)


@pytest.mark.skipif(not HAS_FFMPEG, reason="requires ffmpeg/ffprobe")
def test_load_project_matches_vo_files_in_order_and_ducks_volume(tmp_path):
    project = _make_project(
        tmp_path,
        ["Opening hook", "Boss fight", "Victory"],
        vo_names=("01_intro.mp3", "02_boss.mp3"),
    )

    storyline = load_project(project)

    assert storyline.scenes[0].vo == project / "vo" / "01_intro.mp3"
    assert storyline.scenes[1].vo == project / "vo" / "02_boss.mp3"
    assert storyline.scenes[2].vo is None
    assert storyline.scenes[0].clip_volume == 0.25
    assert storyline.scenes[1].clip_volume == 0.25
    assert storyline.scenes[2].clip_volume == 1.0


@pytest.mark.skipif(not HAS_FFMPEG, reason="requires ffmpeg/ffprobe")
def test_load_project_highlight_duration_grows_for_long_vo(tmp_path):
    project = _make_project(
        tmp_path,
        ["Opening hook"],
        vo_names=("01_intro.mp3",),
    )
    _make_silence(project / "vo" / "01_intro.mp3", duration=20.0)

    storyline = load_project(project)

    assert storyline.highlight_duration >= 20.0 + 3.0
