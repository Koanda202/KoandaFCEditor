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
            _render_scene(scene, scene_file, tmp_dir, i)
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


def _render_scene(scene: Scene, out_path: Path, tmp_dir: Path, index: int) -> None:
    if not scene.clip.exists():
        raise FileNotFoundError(f"Scene {scene.name!r} references missing clip: {scene.clip}")

    vo_file = scene.vo
    if scene.vo_lines:
        for vo in scene.vo_lines:
            if not vo.exists():
                raise FileNotFoundError(f"Scene {scene.name!r} references missing VO file: {vo}")
        vo_file = tmp_dir / f"scene_{index:03d}_vo.m4a"
        _build_vo_track(scene.vo_lines, scene.vo_pause, vo_file)
    elif scene.vo and not scene.vo.exists():
        raise FileNotFoundError(f"Scene {scene.name!r} references missing VO file: {scene.vo}")

    has_effects = scene.freeze_seconds > 0 or scene.zoom_percent > 1 or scene.graphic_text
    base_path = tmp_dir / f"scene_{index:03d}_base.mp4" if has_effects else out_path

    base_duration = _render_base_scene(scene, vo_file, base_path)

    if has_effects:
        _apply_effects(scene, base_path, out_path, base_duration)


def _render_base_scene(scene: Scene, vo_file, out_path: Path) -> float:
    """Trim the clip and mix in VO (if any). Returns the rendered duration."""
    duration = time_to_seconds(scene.end) - time_to_seconds(scene.start)

    # -ss/-to MUST precede the clip's own -i: placed after it (and before a
    # second -i for the VO track) they'd bind to that next input instead,
    # silently leaving the clip untrimmed.
    if vo_file is None:
        run_ffmpeg([
            "-ss", scene.start,
            "-to", scene.end,
            "-i", str(scene.clip),
            "-vf", _SCALE_FILTER,
            "-af", f"volume={scene.clip_volume}",
            "-c:v", "libx264", "-c:a", "aac",
            str(out_path),
        ])
        return duration

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
        "-i", str(vo_file),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264", "-c:a", "aac",
        str(out_path),
    ])
    return duration


def _build_vo_track(vo_lines: list, pause: float, out_path: Path) -> None:
    """Concatenate several VO files into one track, with `pause` seconds of
    silence between each line."""
    inputs = []
    filter_parts = []
    concat_inputs = []
    for i, vo in enumerate(vo_lines):
        inputs += ["-i", str(vo)]
        filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=mono[a{i}]")
        concat_inputs.append(f"[a{i}]")
        if i < len(vo_lines) - 1 and pause > 0:
            filter_parts.append(f"anullsrc=r=44100:cl=mono:d={pause}[sil{i}]")
            concat_inputs.append(f"[sil{i}]")
    filter_complex = ";".join(
        filter_parts + [f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=0:a=1[out]"]
    )
    run_ffmpeg([*inputs, "-filter_complex", filter_complex, "-map", "[out]", str(out_path)])


def _apply_effects(scene: Scene, base_file: Path, out_path: Path, base_duration: float) -> None:
    """Second pass over an already-rendered scene: static punch-in zoom,
    freeze-frame hold, and a burned-in graphic overlay — each optional."""
    video_parts = []
    if scene.zoom_percent > 1:
        factor = scene.zoom_percent / 100.0
        video_parts.append(
            f"crop=w='iw/{factor}':h='ih/{factor}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',"
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}"
        )
    if scene.freeze_seconds > 0:
        video_parts.append(f"tpad=stop_mode=clone:stop_duration={scene.freeze_seconds}")

    total_duration = base_duration + scene.freeze_seconds

    audio_parts = []
    if scene.freeze_seconds > 0:
        audio_parts.append(f"apad=pad_dur={scene.freeze_seconds}")

    if scene.graphic_text:
        hold = min(scene.graphic_hold_seconds, total_duration)
        start = max(0.0, total_duration - hold)
        text = _escape_drawtext(scene.graphic_text)
        video_parts.append(
            f"drawtext=text='{text}':fontcolor=white:fontsize=96:"
            f"box=1:boxcolor=black@0.5:boxborderw=30:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,{start:.3f})'"
        )

    args = ["-i", str(base_file)]
    if video_parts:
        args += ["-vf", ",".join(video_parts), "-c:v", "libx264"]
    else:
        args += ["-c:v", "copy"]
    if audio_parts:
        args += ["-af", ",".join(audio_parts), "-c:a", "aac"]
    else:
        args += ["-c:a", "copy"]
    args += ["-t", f"{total_duration:.3f}", str(out_path)]
    run_ffmpeg(args)


def _escape_drawtext(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("%", "\\%")
    return escaped


def _concat_scenes(scene_files: list, output: Path, tmp_dir: Path) -> None:
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
