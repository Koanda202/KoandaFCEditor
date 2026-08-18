from __future__ import annotations

from pathlib import Path

from .anchors import find_section_anchors
from .guide import parse_guide
from .project import DUCKED_VOLUME, FULL_VOLUME, _find_vo_files
from .storyline import Scene, Storyline

GUIDE_FILENAMES = ("guide.txt", "editing_guide.txt", "edit_guide.txt")
DEFAULT_SECTION_SECONDS = 12.0
PRE_ROLL_FRACTION = 0.7  # most of the window leads up to the anchor moment


def find_guide_file(project_dir: Path):
    for name in GUIDE_FILENAMES:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    return None


def load_guide_project(project_dir: Path, guide_file: Path, *, verbose: bool = False):
    """Build a Storyline from an editing guide + clips/ + vo/.

    Returns (Storyline, list[SectionAnchor]) — the anchors are returned
    alongside so callers can report which sections were confirmed via
    on-screen text versus best-guessed.
    """
    project_dir = Path(project_dir)
    clips_dir = project_dir / "clips"
    if not clips_dir.is_dir():
        raise FileNotFoundError(f"Expected a 'clips' folder of recordings at {clips_dir}")

    sections = parse_guide(guide_file.read_text(encoding="utf-8"))
    if not sections:
        raise ValueError(
            f"{guide_file} has no 'SECTION N — ...' blocks the tool recognizes"
        )

    vo_dir = project_dir / "vo"
    vo_files = _find_vo_files(vo_dir) if vo_dir.is_dir() else []
    vo_by_section = _assign_vo_files(sections, vo_files)

    cache_dir = project_dir / ".koanda_cache"
    anchors = find_section_anchors(sections, clips_dir, cache_dir, verbose=verbose)

    from .ffmpeg_utils import probe_duration
    file_durations = {}

    scenes = []
    for section, anchor in zip(sections, anchors):
        if anchor.file not in file_durations:
            file_durations[anchor.file] = probe_duration(anchor.file)
        file_duration = file_durations[anchor.file]

        duration = _section_duration(section)
        pre = duration * PRE_ROLL_FRACTION
        post = duration - pre
        start = max(0.0, anchor.time - pre)
        end = min(file_duration, anchor.time + post)

        vo_lines = vo_by_section.get(section.number, [])
        scenes.append(Scene(
            name=f"{section.number}. {section.title}",
            clip=anchor.file,
            start=f"{start:.3f}",
            end=f"{end:.3f}",
            vo_lines=vo_lines or None,
            vo_pause=0.6,
            graphic_text="\n".join(section.graphic_text),
            graphic_hold_seconds=section.graphic_hold_seconds,
            freeze_seconds=section.freeze_seconds,
            zoom_percent=section.zoom_percent,
            clip_volume=DUCKED_VOLUME if vo_lines else FULL_VOLUME,
            confirmed=anchor.confirmed,
            guide_number=section.number,
        ))

    storyline = Storyline(
        title=project_dir.name,
        output=project_dir / "output" / "final_video.mp4",
        scenes=scenes,
        clips_dir=clips_dir,
    )
    return storyline, anchors


def _section_duration(section) -> float:
    if section.target_length:
        lo, hi = section.target_length
        return (lo + hi) / 2
    return DEFAULT_SECTION_SECONDS


def _assign_vo_files(sections, vo_files):
    """Flatten VO lines across sections, in guide order, and pair them 1:1
    with sorted vo/ files (same convention as plain story.txt mode)."""
    assignments = {}
    cursor = 0
    for section in sections:
        count = len(section.vo_lines)
        assigned = vo_files[cursor:cursor + count]
        if assigned:
            assignments[section.number] = assigned
        cursor += count
    return assignments
