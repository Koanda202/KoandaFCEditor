from __future__ import annotations

import re
from pathlib import Path

from .anchors import find_section_anchors
from .guide import parse_guide
from .project import DUCKED_VOLUME, FULL_VOLUME, _find_vo_files
from .storyline import Scene, Storyline

GUIDE_FILENAMES = ("guide.txt", "editing_guide.txt", "edit_guide.txt")
DEFAULT_SECTION_SECONDS = 6.0
MIN_SECTION_SECONDS = 3.0
# The anchor (an OCR-confirmed graphic/rating reveal, or a loudness peak
# from crowd/commentary reaction) consistently lands AT OR AFTER the actual
# moment a guide note describes ("save", "goal") — never before it. So the
# window needs to end close to the anchor, not straddle it: almost all of
# the clip is what leads up to and includes the moment itself.
PRE_ROLL_FRACTION = 0.88
MIN_POST_ROLL_SECONDS = 0.75  # small trailing buffer so cuts aren't mid-action
_WORD_RE = re.compile(r"[a-z0-9]+")


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
    vo_by_section = _match_vo_files_to_lines(sections, vo_files)

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
        post = min(duration - MIN_POST_ROLL_SECONDS, max(MIN_POST_ROLL_SECONDS, duration * (1 - PRE_ROLL_FRACTION)))
        pre = duration - post
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
        # Bias toward the shorter end of the guide's own range rather than
        # the midpoint — a tight cut on the actual moment reads better than
        # a loose one, and the guide's lower bound is already an editor's
        # judgment call on the minimum that reads clearly.
        duration = lo + (hi - lo) * 0.25
    else:
        duration = DEFAULT_SECTION_SECONDS
    return max(MIN_SECTION_SECONDS, duration)


def _words(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _match_vo_files_to_lines(sections, vo_files):
    """Match vo/ files to guide VO lines by content, not filename order.

    Files are commonly named after what's said (e.g. "yallop_first_game.mp3"
    for the line "This was Mitchell Yallop's first game...") rather than
    numbered to match guide order, so sorted-filename pairing silently
    scrambles playback. Score every (line, file) pair by how much of the
    filename's words appear in the line's words, then greedily assign
    highest-confidence pairs first.
    """
    line_entries = [
        (section.number, line) for section in sections for line in section.vo_lines
    ]
    if not line_entries or not vo_files:
        return {}

    file_words = {f: _words(f.stem) for f in vo_files}
    line_word_sets = [_words(text) for _, text in line_entries]

    pairs = []
    for li, lw in enumerate(line_word_sets):
        for f in vo_files:
            fw = file_words[f]
            if not fw:
                continue
            overlap = len(lw & fw)
            if overlap == 0:
                continue
            pairs.append((overlap / len(fw), li, f))
    pairs.sort(key=lambda p: p[0], reverse=True)

    assigned = [None] * len(line_entries)
    used_files = set()
    for _score, li, f in pairs:
        if assigned[li] is not None or f in used_files:
            continue
        assigned[li] = f
        used_files.add(f)

    # Leftover lines/files (no shared words at all) get paired in original
    # order as a last resort, so nothing is silently dropped.
    remaining_files = [f for f in vo_files if f not in used_files]
    ri = 0
    for li in range(len(line_entries)):
        if assigned[li] is None and ri < len(remaining_files):
            assigned[li] = remaining_files[ri]
            ri += 1

    assignments = {}
    for (section_number, _text), f in zip(line_entries, assigned):
        if f is not None:
            assignments.setdefault(section_number, []).append(f)
    return assignments
