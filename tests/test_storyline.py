import textwrap
from pathlib import Path

import pytest

from storyline_editor.ffmpeg_utils import time_to_seconds
from storyline_editor.storyline import load_storyline


def write_storyline(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "storyline.yaml"
    path.write_text(textwrap.dedent(content))
    return path


def test_load_storyline_manual_scene(tmp_path):
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


def test_load_storyline_start_without_clip(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Scene 1
            start: "0"
            end: "5"
    """)
    with pytest.raises(ValueError):
        load_storyline(path)


def test_load_storyline_clip_without_start_end(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Scene 1
            clip: clips/a.mp4
    """)
    with pytest.raises(ValueError):
        load_storyline(path)


def test_load_storyline_auto_scene_requires_clips_dir(tmp_path):
    path = write_storyline(tmp_path, """
        scenes:
          - name: Auto scene
    """)
    with pytest.raises(ValueError):
        load_storyline(path)


def test_load_storyline_auto_scene_with_clips_dir(tmp_path):
    path = write_storyline(tmp_path, """
        clips_dir: clips
        highlight_duration: 8
        highlight_min_gap: 15
        scenes:
          - name: Auto scene
            vo: vo/line.mp3
    """)

    storyline = load_storyline(path)

    assert storyline.clips_dir == tmp_path / "clips"
    assert storyline.highlight_duration == 8.0
    assert storyline.highlight_min_gap == 15.0
    scene = storyline.scenes[0]
    assert scene.clip is None
    assert scene.start is None
    assert scene.end is None
    assert scene.vo == tmp_path / "vo" / "line.mp3"


def test_load_storyline_mixed_manual_and_auto_scenes(tmp_path):
    path = write_storyline(tmp_path, """
        clips_dir: clips
        scenes:
          - name: Manual scene
            clip: clips/intro.mp4
            start: "0"
            end: "5"
          - name: Auto scene
    """)

    storyline = load_storyline(path)

    assert storyline.scenes[0].clip == tmp_path / "clips" / "intro.mp4"
    assert storyline.scenes[1].clip is None


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
