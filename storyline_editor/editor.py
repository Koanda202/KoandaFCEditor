from __future__ import annotations

import tempfile
from pathlib import Path

from .ffmpeg_utils import probe_duration, run_ffmpeg, time_to_seconds
from .highlights import select_highlights
from .storyline import Scene, Storyline

TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_FPS = 30
_SCALE_FILTER = (
    f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
    f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
    f"fps={TARGET_FPS},setsar=1"
)


def build_video(storyline: Storyline, *, keep_temp: bool = False, verbose: bool = False) -> Path:
    if not storyline.scenes:
        raise ValueError("Storyline has no scenes to build")

    _resolve_auto_scenes(storyline, verbose=verbose)

    storyline.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="koanda_editor_") as tmp:
        tmp_dir = Path(tmp)
        scene_files = []
        for i, scene in enumerate(storyline.scenes):
            if verbose:
                print(f"[{i + 1}/{len(storyline.scenes)}] rendering scene: {scene.name}")
            scene_file = tmp_dir / f"scene_{i:03d}.mp4"
            _render_scene(scene, scene_file)
            scene_files.append(scene_file)

        if verbose:
            print("concatenating scenes...")
        _concat_scenes(scene_files, storyline.output, tmp_dir)

        if keep_temp:
            kept_dir = storyline.output.parent / f"{storyline.output.stem}_scenes"
            kept_dir.mkdir(parents=True, exist_ok=True)
            for f in scene_files:
                (kept_dir / f.name).write_bytes(f.read_bytes())

    return storyline.output


def _resolve_auto_scenes(storyline: Storyline, *, verbose: bool = False) -> None:
    """Fill in clip/start/end for scenes that didn't specify them explicitly.

    Such scenes are matched, in the order they're listed, to the strongest
    highlight moments auto-detected across every recording in clips_dir.
    """
    auto_scenes = [s for s in storyline.scenes if s.clip is None]
    if not auto_scenes:
        return

    if verbose:
        print(f"scanning {storyline.clips_dir} for {len(auto_scenes)} highlight(s)...")
    highlights = select_highlights(
        storyline.clips_dir,
        count=len(auto_scenes),
        duration=storyline.highlight_duration,
        min_gap=storyline.highlight_min_gap,
        verbose=verbose,
    )

    half = storyline.highlight_duration / 2
    for scene, candidate in zip(auto_scenes, highlights):
        file_duration = probe_duration(candidate.file)
        start = max(0.0, candidate.time - half)
        end = min(file_duration, candidate.time + half)
        scene.clip = candidate.file
        scene.start = f"{start:.3f}"
        scene.end = f"{end:.3f}"
        if verbose:
            print(
                f"  matched scene {scene.name!r} -> {candidate.file.name} "
                f"@ {start:.1f}s-{end:.1f}s (loudness score {candidate.score:.1f} dB)"
            )


def _render_scene(scene: Scene, out_path: Path) -> None:
    if not scene.clip.exists():
        raise FileNotFoundError(f"Scene {scene.name!r} references missing clip: {scene.clip}")
    if scene.vo and not scene.vo.exists():
        raise FileNotFoundError(f"Scene {scene.name!r} references missing VO file: {scene.vo}")

    # -ss/-to MUST precede the clip's own -i: placed after it (and before a
    # second -i for the VO track) they'd bind to that next input instead,
    # silently leaving the clip untrimmed.
    if scene.vo is None:
        run_ffmpeg([
            "-ss", scene.start,
            "-to", scene.end,
            "-i", str(scene.clip),
            "-vf", _SCALE_FILTER,
            "-af", f"volume={scene.clip_volume}",
            "-c:v", "libx264", "-c:a", "aac",
            str(out_path),
        ])
        return

    vo_offset_ms = max(0, int(time_to_seconds(scene.vo_offset) * 1000))
    filter_complex = (
        f"[0:v]{_SCALE_FILTER}[vout];"
        f"[0:a]volume={scene.clip_volume}[a0];"
        f"[1:a]adelay={vo_offset_ms}|{vo_offset_ms},volume={scene.vo_volume}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    run_ffmpeg([
        "-ss", scene.start,
        "-to", scene.end,
        "-i", str(scene.clip),
        "-i", str(scene.vo),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-c:a", "aac",
        str(out_path),
    ])


def _concat_scenes(scene_files: list[Path], output: Path, tmp_dir: Path) -> None:
    filelist = tmp_dir / "filelist.txt"
    with filelist.open("w", encoding="utf-8") as f:
        for scene_file in scene_files:
            f.write(f"file '{scene_file.as_posix()}'\n")

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", str(filelist),
        "-c", "copy",
        str(output),
    ])
