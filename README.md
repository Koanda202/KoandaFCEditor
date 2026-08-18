# KoandaFCEditor

A command-line video editor that turns a folder of **ROG Ally recordings**,
your **VO (voice-over) lines**, and a **storyline file** into one edited
video — automatically. You don't scrub through footage or write down
timestamps: point the tool at your recordings folder, list your scenes in
order (with optional VO lines), and it scans every recording for the
loudest/most-exciting moments and slots them into place for you.

Under the hood it uses ffmpeg to: scan each recording's audio for loud
moments (explosions, crowd noise, big plays), pick the strongest
non-overlapping ones, trim each into a scene, duck the gameplay audio under
any VO line, normalize everything to a common resolution/framerate, and
concatenate it all into the final video in your storyline's scene order.

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

## Quick start (fully automatic)

1. Put your raw recordings in a folder, e.g. `clips/`.
2. Put your VO lines (mp3/wav) in a folder, e.g. `vo/`.
3. Write a storyline file that just lists scene names in order — no clip
   paths, no timestamps:

   ```yaml
   title: "My Highlight Reel"
   output: "output/final_video.mp4"
   clips_dir: "clips"          # folder of recordings to scan for highlights

   scenes:
     - name: "Opening hook"
       vo: "vo/opening_line.mp3"
       clip_volume: 0.25         # duck gameplay audio so VO is audible

     - name: "Boss fight"
       vo: "vo/boss_fight_line.mp3"
       clip_volume: 0.3

     - name: "Victory"
       clip_volume: 1.0           # no VO here — full gameplay audio
   ```

4. Run it:

   ```bash
   koanda-editor storyline.yaml
   ```

That's it. The tool scans every recording in `clips_dir`, scores each one
second-by-second for loudness, picks the strongest non-overlapping moment
per scene (in chronological order across your recordings), and builds
`output/final_video.mp4` with VO mixed in and everything trimmed and
concatenated automatically.

See [`examples/example_storyline.yaml`](examples/example_storyline.yaml)
for a ready-to-copy version of this.

## Usage

```bash
python -m storyline_editor storyline.yaml
# or, if installed with `pip install -e .`:
koanda-editor storyline.yaml
```

Options:

- `-o, --output PATH` — override the output path set in the storyline file
- `--keep-scenes` — also save each rendered scene file next to the output,
  useful for checking which moment got picked for each scene
- `-q, --quiet` — suppress progress output

## Storyline file format

### Top level

| Key | Required | Description |
|---|---|---|
| `title` | no | Cosmetic, defaults to the filename |
| `output` | no | Final video path, defaults to `output.mp4` |
| `clips_dir` | only if any scene auto-detects | Folder of recordings to scan for highlights |
| `highlight_duration` | no | Seconds captured around each detected highlight (default `12`) |
| `highlight_min_gap` | no | Minimum seconds between two detected highlights (default `6`) |
| `scenes` | yes | Ordered list of scenes — see below |

### Scene fields

| Key | Required | Description |
|---|---|---|
| `name` | no | Label shown in progress output |
| `clip` / `start` / `end` | no (all three or none) | Set all three to manually pin this scene to an exact clip/time range instead of auto-detecting it |
| `vo` | no | VO audio file to mix over this scene |
| `vo_offset` | no | Delay before the VO starts, default `0` |
| `vo_volume` | no | VO gain multiplier, default `1.0` |
| `clip_volume` | no | Gameplay audio gain multiplier, default `1.0` — lower this (e.g. `0.25`) on scenes with VO so the line is audible |

**Leave `clip`/`start`/`end` out of a scene** and it's auto-detected from
`clips_dir`. **Set all three** and that scene uses exactly the clip/range you
specify, skipping detection — useful if you already know exactly which
moment you want for one particular scene while letting the rest be found
automatically. You can freely mix both kinds of scenes in one storyline; see
[`examples/manual_storyline.yaml`](examples/manual_storyline.yaml).

### How auto-detection works

For every recording in `clips_dir`, the tool measures audio loudness (RMS)
in ~1-second windows across the whole file, then greedily picks the
loudest moments at least `highlight_min_gap` (or `highlight_duration`,
whichever is larger) apart, so picks never overlap or bunch up next to each
other. All candidates across every recording are pooled, the strongest one
is kept per scene that needs auto-detection, and — because a "storyline"
usually flows in the order things happened — the picks are then handed to
your scenes in **chronological order** (earliest recording/timestamp first),
matching the order your `scenes:` list is written in.

Each detected highlight becomes a window of `highlight_duration` seconds
centered on the loud moment (clipped to the recording's actual bounds near
the start/end of a file).

If there aren't enough loud, sufficiently-spaced moments across your
recordings to fill every auto-detected scene, the tool stops with an error
telling you how many it found — add more recordings, lower
`highlight_min_gap`, or reduce the number of scenes.

### How each scene is rendered

1. Trim to the resolved `[start, end]` (whether auto-detected or manual).
2. Scale/pad the video to 1920x1080 @ 30fps so mismatched source clips
   (different resolutions or framerates) concatenate cleanly.
3. If `vo` is set, delay it by `vo_offset` and mix it with the
   volume-adjusted gameplay audio. The scene's duration is always the
   trimmed clip's length — a VO line longer than the scene is truncated,
   so widen `highlight_duration` (or a manual scene's `end`) if a line needs
   more room.
4. All rendered scenes are concatenated in order into the final output.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

Storyline-parsing and peak-picking logic is tested without needing ffmpeg.
A few highlight-detection tests generate real short clips with ffmpeg and
verify the loud moments are found correctly — they're skipped automatically
if ffmpeg/ffprobe aren't on `PATH`.
