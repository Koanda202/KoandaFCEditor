from __future__ import annotations

import dataclasses
from pathlib import Path

from .guide import GuideSection
from .highlights import _loudness_curve, _pick_peaks, find_recordings
from .ocr import build_text_index, search_index


@dataclasses.dataclass
class SectionAnchor:
    section: GuideSection
    file: Path
    time: float
    matched_keyword: str  # empty string if unconfirmed
    confirmed: bool


def find_section_anchors(
    sections: list,
    clips_dir: Path,
    cache_dir: Path,
    *,
    ocr_interval: float = 2.0,
    verbose: bool = False,
) -> list:
    """Match each guide section to a (file, time) in the raw recordings.

    Recordings are treated as one combined timeline in filename order (e.g.
    session_1, session_2, session_3 — a natural convention for "part 1 of
    the story", "part 2", ...). Sections are walked in guide order with a
    single cursor that only ever moves forward through that combined
    timeline: a keyword match behind the cursor is never used, because
    guide order already reflects narrative order, so accepting a backward
    match would mean showing footage out of sequence. Sections with no
    forward on-screen match are unconfirmed and best-guessed via loudness,
    still constrained to move forward, and flagged for review.
    """
    files = find_recordings(clips_dir)
    file_order = {f: i for i, f in enumerate(files)}

    if verbose:
        print(f"  OCR-indexing {len(files)} recording(s) (this can take a while)...")
    text_indexes = {}
    for f in files:
        if verbose:
            print(f"    reading on-screen text in {f.name}...")
        text_indexes[f] = build_text_index(f, ocr_interval, cache_dir)

    loudness_cache = {}

    def loudness_for(f: Path):
        if f not in loudness_cache:
            loudness_cache[f] = _loudness_curve(f)
        return loudness_cache[f]

    claimed = {f: [] for f in files}
    cursor_idx = 0
    cursor_time = 0.0

    results = []
    for section in sections:
        match = _find_forward_ocr_match(
            section, files, file_order, text_indexes, claimed, cursor_idx, cursor_time
        )
        if match is not None:
            f, time, keyword = match
            results.append(SectionAnchor(section, f, time, keyword, confirmed=True))
            if verbose:
                print(
                    f"  section {section.number} ({section.title!r}): "
                    f"confirmed via {keyword!r} -> {f.name} @ {time:.1f}s"
                )
        else:
            f, time = _forward_fallback(files, loudness_for, claimed, cursor_idx, cursor_time)
            results.append(SectionAnchor(section, f, time, "", confirmed=False))
            if verbose:
                print(
                    f"  section {section.number} ({section.title!r}): "
                    f"UNCONFIRMED (no forward on-screen match) -> "
                    f"best guess {f.name} @ {time:.1f}s"
                )

        claimed[f].append(time)
        cursor_idx = file_order[f]
        cursor_time = time

    return results


def _find_forward_ocr_match(section, files, file_order, text_indexes, claimed, cursor_idx, cursor_time):
    for keyword in section.keywords:
        candidates = []
        for f in files:
            fi = file_order[f]
            for time, score in search_index(text_indexes[f], keyword):
                if fi < cursor_idx or (fi == cursor_idx and time < cursor_time):
                    continue  # behind the cursor — would play footage out of order
                if any(abs(time - c) < 1.0 for c in claimed[f]):
                    continue
                candidates.append((fi, time, -score, f))
        if candidates:
            candidates.sort()  # closest forward position first
            fi, time, _neg_score, f = candidates[0]
            return f, time, keyword
    return None


def _forward_fallback(files, loudness_for, claimed, cursor_idx, cursor_time):
    for fi in range(cursor_idx, len(files)):
        f = files[fi]
        lo = cursor_time if fi == cursor_idx else 0.0
        points = loudness_for(f)
        pool = [(t, s) for t, s in points if t >= lo] or points
        peaks = _pick_peaks(pool, min_gap=1.0, max_count=len(pool) or 1)
        for time, _score in peaks:
            if not any(abs(time - c) < 3.0 for c in claimed[f]):
                return f, time
    return files[cursor_idx], cursor_time
