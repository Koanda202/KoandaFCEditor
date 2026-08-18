from __future__ import annotations

from pathlib import Path

from .ffmpeg_utils import probe_duration
from .storyline import Scene, Storyline

STORY_FILENAMES = ("story.txt", "story.md")
VO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

DEFAULT_HIGHLIGHT_DURATION = 10.0
VO_PADDING = 3.0
DUCKED_VOLUME = 0.25
FULL_VOLUME = 1.0


def load_project(project_dir: Path) -> Storyline:
    """Build a Storyline from a project folder with no other input needed.

    Expects:
        project_dir/clips/   - raw recordings to scan for highlights
        project_dir/vo/      - voice-over lines, matched to scenes in sorted
                                filename order (optional)
        project_dir/story.txt (or story.md) - one scene per line, in order

    Everything else (which moment matches which scene, audio ducking,
    highlight window length) is inferred automatically.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {project_dir}")

    clips_dir = project_dir / "clips"
    if not clips_dir.is_dir():
        raise FileNotFoundError(
            f"Expected a 'clips' folder of recordings at {clips_dir}"
        )

    story_file = _find_story_file(project_dir)
    lines = _read_story_lines(story_file)
    if not lines:
        raise ValueError(f"{story_file} has no scene lines")

    vo_dir = project_dir / "vo"
    vo_files = _find_vo_files(vo_dir) if vo_dir.is_dir() else []

    assigned_vo = vo_files[: len(lines)]
    highlight_duration = DEFAULT_HIGHLIGHT_DURATION
    if assigned_vo:
        longest_vo = max(probe_duration(f) for f in assigned_vo)
        highlight_duration = max(highlight_duration, longest_vo + VO_PADDING)

    scenes = []
    for i, line in enumerate(lines):
        vo = vo_files[i] if i < len(vo_files) else None
        scenes.append(Scene(
            name=line,
            vo=vo,
            vo_offset="0",
            vo_volume=FULL_VOLUME,
            clip_volume=DUCKED_VOLUME if vo else FULL_VOLUME,
        ))

    return Storyline(
        title=project_dir.name,
        output=project_dir / "output" / "final_video.mp4",
        scenes=scenes,
        clips_dir=clips_dir,
        highlight_duration=highlight_duration,
        highlight_min_gap=highlight_duration,
    )


def _find_story_file(project_dir: Path) -> Path:
    for name in STORY_FILENAMES:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No story file found in {project_dir} "
        f"(expected one of: {', '.join(STORY_FILENAMES)})"
    )


def _read_story_lines(story_file: Path) -> list[str]:
    lines = []
    for raw in story_file.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(text)
    return lines


def _find_vo_files(vo_dir: Path) -> list[Path]:
    return sorted(
        p for p in vo_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VO_EXTENSIONS
    )
