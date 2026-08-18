# KoandaFCEditor

Turns a folder of **ROG Ally recordings**, your **VO lines**, and a plain
**story text file** into one edited video — with nothing else required from
you. No timestamps, no clip names, no config file to write. Point the tool
at a folder and it does the rest.

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/download.html) (with `ffprobe`) on your `PATH`
- `PyYAML` (installed via the steps below)

## Install

```bash
pip install -r requirements.txt
# or, to get the `koanda-editor` command on your PATH:
pip install -e .
```

## Quick start — the only three things you provide

Make a folder with this layout:

```
my-video/
  clips/
    session1.mp4      <- your raw recordings, any names, any number of them
    session2.mp4
  vo/
    01_opening.mp3     <- your voice lines, named so sorted order = story order
    02_boss_fight.mp3
  story.txt            <- one scene per line, in the order you want them
```

`story.txt` is plain text — nothing else:

```
Opening hook
Boss fight
Victory
```

Then run:

```bash
koanda-editor my-video
```

That's the entire interface. `koanda-editor`:

1. Reads `story.txt` — each line becomes one scene, in that order.
2. Matches your `vo/` files to those scenes 1:1 in sorted filename order
   (name them `01_...`, `02_...` etc. to control which line goes where; a
   scene with no matching VO file just plays with full gameplay audio).
3. Scans every recording in `clips/`, measuring loudness second-by-second,
   and picks the strongest, non-overlapping moment for each scene — in
   chronological order across your recordings, matching your story's order.
4. Automatically ducks gameplay audio under any VO line, and sizes each
   highlight window to comfortably fit its VO line if there is one.
5. Trims, normalizes resolution/framerate, and concatenates everything into
   `my-video/output/final_video.mp4`.

See [`examples/project/`](examples/project) for a copy-pasteable layout.

## Usage

```bash
koanda-editor my-video/          # zero-config project folder
koanda-editor my-video/ -o out.mp4   # override the output path
koanda-editor my-video/ --keep-scenes  # also save each rendered scene
koanda-editor my-video/ -q             # suppress progress output
```

## If it picks the wrong moment

Two ways to fix it, without giving up the automation for everything else:

- **Rename/add VO files** to nudge which VO pairs with which scene, or add
  more recordings to `clips/` to give it better material to choose from.
- **Drop down to a storyline YAML** for full manual control over one or all
  scenes — set an exact `clip`/`start`/`end` per scene, and/or tune
  `highlight_duration` / `highlight_min_gap` globally. This is the same
  engine, just with every knob exposed:

  ```bash
  koanda-editor storyline.yaml
  ```

  See [`examples/example_storyline.yaml`](examples/example_storyline.yaml)
  (auto-detect via YAML, with all the automatic knobs spelled out) and
  [`examples/manual_storyline.yaml`](examples/manual_storyline.yaml)
  (mixing manually-pinned and auto-detected scenes in one file). Every
  field in a storyline YAML is optional except `scenes`; anything you don't
  set falls back to sensible defaults, same as project mode.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Story/storyline parsing and peak-picking logic are tested without needing
ffmpeg. Highlight-detection and VO-matching tests generate real short clips
with ffmpeg and verify the results — they're skipped automatically if
ffmpeg/ffprobe aren't on `PATH`.
