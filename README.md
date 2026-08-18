# KoandaFCEditor

Turns a folder of **ROG Ally recordings**, your **VO lines**, and a plain
**story text file** into one edited video — with nothing else required from
you. No timestamps, no clip names, no config file to write. Point the tool
at a folder and it does the rest.

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/download.html) (with `ffprobe`) on your `PATH`
- `PyYAML` (installed via the steps below)
- [tesseract](https://github.com/tesseract-ocr/tesseract) on your `PATH` —
  only needed for **guide-driven editing** (below); story.txt mode doesn't
  use it

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

## Guide-driven editing (for a real shot-by-shot edit script)

If you're editing a story-driven episode rather than a highlight reel, a
plain `story.txt` line list isn't enough — you want specific VO lines
placed over specific moments, graphics that appear at the right instant,
freeze frames, punch-ins, all in a defined order. For that, drop a
**`guide.txt`** into your project folder instead of `story.txt`:

```
my-video/
  clips/
    match_recording.mp4
  vo/
    01_intro.mp3
    02_reveal.mp3
    ...              <- one file per VO line in the guide, in guide order
  guide.txt
```

`guide.txt` is a structured shot list — ordered `SECTION N — TITLE` blocks,
each with a `TARGET LENGTH`, `VO` lines (quoted, spoken in order), a
`GRAPHIC` (on-screen text), and `EDITING` notes for freeze frames /
punch-in zoom percentages. Any block using this `HEADER` / `-----` /
content style is understood — write your own guide the same way, or see
[`examples/project/`](examples/project) for the format in detail.

**How it finds the right moment for each section, since footage isn't
labeled:** FC/FIFA Career Mode puts a lot of what a guide describes as
literal text on screen — ratings, OVR/potential numbers, transfer grades,
scorelines, minute markers, reveal screens. `koanda-editor` OCR-scans your
recordings for that text and matches it to numbers/phrases in each
section — these sections are **confirmed**. A section with no on-screen
signal (a pure gameplay action beat like an assist or a save) can't be
found this way, so it's **best-guessed** instead using loudness. Either
way, if you have multiple recordings in `clips/` (e.g. one file per match),
they're treated as one combined timeline in filename order — a single
cursor only ever moves forward through that timeline as sections are
resolved in guide order, so a keyword that happens to recur in an earlier
or later recording (a minute marker like `45'` shows up in every match)
can never pull a section backward or skip it ahead out of sequence. Best
guesses are constrained the same way, and every unconfirmed section is
clearly flagged in the output for you to check:

```bash
koanda-editor my-video

...
done: my-video/output/final_video.mp4

1 of 12 section(s) had no on-screen text to confirm the moment — best-guessed instead. Please review:
  - Section 7 (YALLOP 61' RABONA GOAL): match_recording.mp4 @ 842.3s
```

OCR results are cached per-recording in `.koanda_cache/` inside your
project folder, so editing `guide.txt` and re-running doesn't re-scan
footage that hasn't changed.

**VO files are matched to guide lines by content, not filename order.**
Name them however makes sense to you (`yallop_first_game.mp3`,
`hat_trick_line.mp3`, ...) — each `vo/` file is paired with whichever
quoted line in the guide shares the most words with its filename, so
sorted-alphabetically-by-name is never assumed to equal guide order.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Story/storyline/guide parsing and peak-picking logic are tested without
needing ffmpeg. Highlight-detection, OCR-matching, and VO-matching tests
generate real short clips with ffmpeg (and read them back with tesseract)
to verify the results — they're skipped automatically if ffmpeg/ffprobe/
tesseract aren't on `PATH`.
