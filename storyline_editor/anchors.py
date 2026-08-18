from __future__ import annotations

import dataclasses
from pathlib import Path

from .ffmpeg_utils import probe_duration
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

    Two passes:
      1. OCR keyword matches (on-screen text: ratings, scores, grades,
         graphic titles) are found independently per section — these are
         real evidence and don't need to respect narrative order.
      2. Sections with no OCR match ("unconfirmed") are filled in via the
         loudness heuristic, but constrained to fall chronologically
         between their nearest confirmed neighbors in guide order, so a
         best-guess pick never lands after a later section's confirmed
         moment (which would make the footage jump backward in time).
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

    results = [None] * len(sections)
    claimed = {f: [] for f in files}

    for i, section in enumerate(sections):
        match = _find_ocr_match(section, files, text_indexes, claimed)
        if match is not None:
            f, time, keyword = match
            results[i] = SectionAnchor(section, f, time, keyword, confirmed=True)
            claimed[f].append(time)
            if verbose:
                print(
                    f"  section {section.number} ({section.title!r}): "
                    f"confirmed via {keyword!r} -> {f.name} @ {time:.1f}s"
                )

    loudness_cache = {}

    def loudness_for(f: Path):
        if f not in loudness_cache:
            loudness_cache[f] = _loudness_curve(f)
        return loudness_cache[f]

    for i, section in enumerate(sections):
        if results[i] is not None:
            continue
        lower = _neighbor_bound(results, i, -1, files, file_order)
        upper = _neighbor_bound(results, i, +1, files, file_order)
        f, time = _fallback_highlight(files, file_order, loudness_for, claimed, lower, upper)
        results[i] = SectionAnchor(section, f, time, "", confirmed=False)
        claimed[f].append(time)
        if verbose:
            print(
                f"  section {section.number} ({section.title!r}): "
                f"UNCONFIRMED (no on-screen match) -> best guess {f.name} @ {time:.1f}s"
            )

    return results


def _find_ocr_match(section: GuideSection, files, text_indexes, claimed):
    for keyword in section.keywords:
        candidates = []
        for f in files:
            for time, score in search_index(text_indexes[f], keyword):
                if any(abs(time - c) < 1.0 for c in claimed[f]):
                    continue
                candidates.append((-score, f, time))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            _, f, time = candidates[0]
            return f, time, keyword
    return None


def _neighbor_bound(results, index, step, files, file_order):
    """Walk outward from `index` to the nearest confirmed anchor, returning
    (file, time) to bound the fallback search, or an open bound (None, None)
    if the search hits the edge of the section list first."""
    i = index + step
    while 0 <= i < len(results):
        if results[i] is not None:
            return results[i].file, results[i].time
        i += step
    return None, None


def _fallback_highlight(files, file_order, loudness_for, claimed, lower, upper):
    lower_file, lower_time = lower
    upper_file, upper_time = upper

    # Prefer the file (and time range) actually bounded by neighboring
    # confirmed anchors, so the pick stays chronologically consistent.
    search_file = lower_file or upper_file
    if search_file is None:
        search_file = files[0]
    lo = lower_time if (lower_file == search_file and lower_time is not None) else 0.0
    hi = upper_time if (upper_file == search_file and upper_time is not None) else None
    if hi is None:
        hi = probe_duration(search_file)

    points = loudness_for(search_file)
    windowed = [(t, s) for t, s in points if lo <= t <= hi]
    pool = windowed if windowed else points
    peaks = _pick_peaks(pool, min_gap=1.0, max_count=len(pool) or 1)
    for time, _score in peaks:
        if not any(abs(time - c) < 3.0 for c in claimed[search_file]):
            return search_file, time

    # Nothing usable found (e.g. silent placeholder footage) — fall back to
    # the midpoint of the bounded window so it still lands in-order.
    return search_file, (lo + hi) / 2
