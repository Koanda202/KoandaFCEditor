# KoandaFCEditor

A command-line video editor that assembles **ROG Ally recording clips**, **VO
(voice-over) lines**, and a **storyline file** into one edited video, with
every clip and VO line placed exactly where the storyline says it should go.

You write a storyline (a YAML script) describing, scene by scene, which clip
to use, what time range to cut out of it, and which VO line (if any) to lay
over it. `koanda-editor` renders each scene with ffmpeg, ducks the gameplay
audio under the VO, normalizes every clip to a common resolution/framerate,
and concatenates everything into the final video.

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`
- `PyYAML` (installed via the steps below)

## Install

```bash
pip install -r requirements.txt
# or, to get the `koanda-editor` command on your PATH:
pip install -e .
```

## Usage

```bash
python -m storyline_editor examples/example_storyline.yaml
# or, if installed with `pip install -e .`:
koanda-editor examples/example_storyline.yaml
```

Options:

- `-o, --output PATH` — override the output path set in the storyline file
- `--keep-scenes` — also save each rendered scene file next to the output,
  useful for debugging sync/timing issues
- `-q, --quiet` — suppress progress output

## Storyline file format

A storyline is a YAML file with a title, an output path, and an ordered list
of scenes. Clip and VO paths are resolved relative to the storyline file's
own directory (or can be absolute).

```yaml
title: "ROG Ally Highlight Reel"
output: "output/highlight_reel.mp4"

scenes:
  - name: "Opening hook"          # label, shown in progress output
    clip: "clips/opening_gameplay.mp4"  # required: source recording
    start: "00:00:05"             # required: in-point (SS, MM:SS, or HH:MM:SS)
    end: "00:00:18"                # required: out-point
    vo: "vo/opening_line.mp3"      # optional: VO line to mix over this scene
    vo_offset: "00:00:01"          # optional: delay before VO starts, default 0
    vo_volume: 1.0                 # optional: VO gain, default 1.0
    clip_volume: 0.25              # optional: gameplay audio gain, default 1.0

  - name: "Boss fight"
    clip: "clips/boss_fight.mp4"
    start: "00:01:12"
    end: "00:02:00"
    # no `vo` here — this scene just plays gameplay audio as-is
```

Only `clip`, `start`, and `end` are required per scene. `output` and `title`
at the top level are optional too (`output` defaults to `output.mp4`).

See [`examples/example_storyline.yaml`](examples/example_storyline.yaml) for
a full example.

### How scenes are built

For each scene, `koanda-editor`:

1. Trims `clip` to `[start, end]`.
2. Scales/pads the video to 1920x1080 @ 30fps so mismatched source clips
   (different resolutions or framerates) concatenate cleanly.
3. If `vo` is set, delays it by `vo_offset` and mixes it with the
   volume-adjusted gameplay audio (`clip_volume` for the gameplay track,
   `vo_volume` for the VO track). The scene's duration is the clip's trimmed
   length — a VO line longer than the scene will be truncated, so trim the
   scene to fit the line if you need it to play in full.
4. All rendered scenes are concatenated in order into the final output.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Tests cover storyline parsing and time-string handling; they don't require
ffmpeg or sample media to run.
