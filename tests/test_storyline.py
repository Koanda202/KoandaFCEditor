import textwrap
from pathlib import Path

import pytest

from storyline_editor.ffmpeg_utils import time_to_seconds
from storyline_editor.storyline import load_storyline


def write_storyline(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "storyline.yaml"
    path.write_text(textwrap.dedent(content))
    return path


def test_load_storyline_basic(tmp_path):
    path = write_storyline(tmp_path, """
        title: Test
        output: out.mp4
        scenes:
          - name: Scene 1
            clip: clips/a.mp4
            start: "0"
            end: "5"
    """)

    storyline = load_storyline(path)

    assert storyline.title == "Test"
    assert storyline.output == tmp_path / "out.mp4"
    assert len(storyline.scenes) == 1
    scene = storyline.scenes[0]
    assert scene.name == "Scene 1"
    assert scene.clip == tmp_path / "clips" / "a.mp4"
    assert scene.vo is None
    assert scene.clip_volume == 1.0


def test_load_storyline_with_vo(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Scene 1
            clip: clips/a.mp4
            start: "0"
            end: "5"
            vo: vo/line.mp3
            vo_offset: "00:00:01"
            vo_volume: 0.9
            clip_volume: 0.2
    """)

    storyline = load_storyline(path)
    scene = storyline.scenes[0]

    assert scene.vo == tmp_path / "vo" / "line.mp3"
    assert scene.vo_offset == "00:00:01"
    assert scene.vo_volume == 0.9
    assert scene.clip_volume == 0.2


def test_load_storyline_defaults_output_and_title(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Scene 1
            clip: clips/a.mp4
            start: "0"
            end: "5"
    """)

    storyline = load_storyline(path)

    assert storyline.title == "storyline"
    assert storyline.output == tmp_path / "output.mp4"


def test_load_storyline_missing_scenes(tmp_path):
    path = write_storyline(tmp_path, "title: Empty\n")
    with pytest.raises(ValueError):
        load_storyline(path)


def test_load_storyline_missing_required_field(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Scene 1
            start: "0"
            end: "5"
    """)
    with pytest.raises(ValueError):
        load_storyline(path)


@pytest.mark.parametrize("value,expected", [
    ("5", 5.0),
    ("5.5", 5.5),
    ("01:05", 65.0),
    ("00:01:05", 65.0),
    ("01:00:00", 3600.0),
])
def test_time_to_seconds(value, expected):
    assert time_to_seconds(value) == expected


def test_time_to_seconds_invalid():
    with pytest.raises(ValueError):
        time_to_seconds("not-a-time")
