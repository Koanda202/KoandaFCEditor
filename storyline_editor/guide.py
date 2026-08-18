from __future__ import annotations

import dataclasses
import re

_BORDER_RE = re.compile(r"^=+$")
_UNDERLINE_RE = re.compile(r"^-+$")
_SECTION_TITLE_RE = re.compile(r"^SECTION\s+(\d+)\s*[—-]\s*(.+)$", re.IGNORECASE)
_QUOTED_RE = re.compile(r"[“\"](.+?)[”\"]")
_MINUTE_RE = re.compile(r"\b\d{1,3}['’]")
_RATING_RE = re.compile(r"\b\d{1,2}\.\d\b")
_OVR_RE = re.compile(r"\b\d{2,3}\s*(?:OVR|POTENTIAL)\b", re.IGNORECASE)
_SCORE_RE = re.compile(r"\b\d{1,2}[–-]\d{1,2}\b")
_GRADE_RE = re.compile(r"\b(?:grade|D grade|A grade|B grade|C grade)\b", re.IGNORECASE)
_HOLD_SENTENCE_RE = re.compile(r"[^.\n]*\bhold\b[^.\n]*\.", re.IGNORECASE)
_HOLD_NUMBER_RE = re.compile(r"(\d+)(?:\s*[–—-]\s*(\d+))?\s*seconds?")
_ZOOM_RE = re.compile(r"\b(\d{2,3})\s*[–-]\s*(\d{2,3})\s*%")
_LENGTH_RE = re.compile(r"(\d+)\s*[–-]\s*(\d+)\s*second")

DEFAULT_GRAPHIC_HOLD_SECONDS = 2.5
DEFAULT_FREEZE_SECONDS = 1.5


@dataclasses.dataclass
class GuideSection:
    number: int
    title: str
    target_length: tuple  # (min_seconds, max_seconds) or None
    vo_lines: list
    graphic_text: list
    graphic_hold_seconds: float  # how long overlay text stays on screen
    keywords: list  # ordered, highest-confidence first
    freeze_seconds: float  # 0 unless a literal video freeze-frame is implied
    zoom_percent: float  # 0 if no punch-in mentioned
    raw_fields: dict  # header -> joined text, for anything not otherwise parsed


def _is_display_text(line: str) -> bool:
    """Heuristic: does this GRAPHIC-block line look like on-screen title-card
    text, as opposed to a directorial note that happens to sit in the same
    block (e.g. "Freeze / punch-in." or "Use one restrained impact sound.")?
    Directorial notes in this guide are full sentences ending in punctuation;
    real title-card text is short and bare.
    """
    text = line.strip()
    if not text or len(text) > 40:
        return False
    if text.endswith((".", ":", ";")):
        return False
    return True


def parse_guide(text: str) -> list:
    """Parse an editing-guide document into ordered GuideSection objects.

    The format is generic on purpose: any block delimited by a line of '='
    characters, a title line, another '=' line, and a body — where the body
    is itself made of HEADER / '-----' / content sub-blocks — is understood.
    Only blocks titled "SECTION N — ..." become timeline sections; every
    other block (setup notes, style rules, reference scripts) is ignored for
    automated assembly.
    """
    blocks = _split_blocks(text)
    sections = []
    for title, body_lines in blocks:
        match = _SECTION_TITLE_RE.match(title.strip())
        if not match:
            continue
        number = int(match.group(1))
        section_title = match.group(2).strip()
        fields = _split_fields(body_lines)
        sections.append(_build_section(number, section_title, fields))
    sections.sort(key=lambda s: s.number)
    return sections


def _split_blocks(text: str):
    lines = text.splitlines()
    borders = [i for i, line in enumerate(lines) if _BORDER_RE.match(line.strip())]

    blocks = []
    i = 0
    while i < len(borders) - 1:
        top, bottom = borders[i], borders[i + 1]
        if bottom - top != 2:
            i += 1
            continue
        title = lines[top + 1]
        body_start = bottom + 1
        body_end = borders[i + 2] if i + 2 < len(borders) else len(lines)
        blocks.append((title, lines[body_start:body_end]))
        i += 2
    return blocks


def _split_fields(lines: list) -> dict:
    """Split a block's body into HEADER -> content, where each header is a
    line immediately followed by a '----' underline of any length."""
    fields: dict = {}
    current_header = None
    current_lines: list = []
    i = 0
    while i < len(lines):
        line = lines[i]
        is_header = (
            i + 1 < len(lines)
            and line.strip()
            and _UNDERLINE_RE.match(lines[i + 1].strip())
            and len(lines[i + 1].strip()) > 0
        )
        if is_header:
            if current_header is not None:
                fields.setdefault(current_header, []).extend(current_lines)
            current_header = line.strip().upper()
            current_lines = []
            i += 2
            continue
        current_lines.append(line)
        i += 1
    if current_header is not None:
        fields.setdefault(current_header, []).extend(current_lines)
    return fields


def _build_section(number: int, title: str, fields: dict) -> GuideSection:
    def joined(*header_names) -> str:
        parts = []
        for name in header_names:
            for key, lines in fields.items():
                if key == name or key.startswith(name):
                    parts.extend(lines)
        return "\n".join(parts)

    length_text = joined("TARGET LENGTH")
    target_length = None
    length_match = _LENGTH_RE.search(length_text)
    if length_match:
        target_length = (int(length_match.group(1)), int(length_match.group(2)))

    vo_text = joined("VO")
    vo_lines = _QUOTED_RE.findall(vo_text)

    graphic_text = [
        line.strip() for line in joined("GRAPHIC").splitlines() if _is_display_text(line)
    ]

    clip_text = joined("CLIP", "CLIPS")
    editing_text = joined("EDITING")
    important_text = joined("IMPORTANT")
    all_text = "\n".join([clip_text, vo_text, graphic_text and "\n".join(graphic_text) or ""])

    keywords = _extract_keywords(all_text, graphic_text)

    # "hold N seconds" describes how long a graphic/title-card stays on
    # screen. A literal video freeze-frame is only implied when "freeze" is
    # explicitly mentioned (usually alongside a punch-in), and separately
    # may borrow a nearby hold duration if one is given.
    hold_seconds = _find_hold_seconds(important_text) or _find_hold_seconds(editing_text)
    graphic_hold_seconds = hold_seconds if hold_seconds else DEFAULT_GRAPHIC_HOLD_SECONDS

    has_freeze_word = "freeze" in editing_text.lower() or "freeze" in important_text.lower()
    freeze_seconds = 0.0
    if has_freeze_word:
        freeze_seconds = hold_seconds if hold_seconds else DEFAULT_FREEZE_SECONDS

    zoom_percent = 0.0
    zoom_match = _ZOOM_RE.search(editing_text)
    if zoom_match:
        zoom_percent = (int(zoom_match.group(1)) + int(zoom_match.group(2))) / 2

    raw_fields = {k: "\n".join(v) for k, v in fields.items()}

    return GuideSection(
        number=number,
        title=title,
        target_length=target_length,
        vo_lines=vo_lines,
        graphic_text=graphic_text,
        graphic_hold_seconds=graphic_hold_seconds,
        keywords=keywords,
        freeze_seconds=freeze_seconds,
        zoom_percent=zoom_percent,
        raw_fields=raw_fields,
    )


def _find_hold_seconds(text: str):
    for sentence in _HOLD_SENTENCE_RE.findall(text):
        number_match = _HOLD_NUMBER_RE.search(sentence)
        if number_match:
            lo = int(number_match.group(1))
            hi = int(number_match.group(2)) if number_match.group(2) else lo
            return (lo + hi) / 2
    return None


def _extract_keywords(text: str, graphic_text: list) -> list:
    keywords = []

    # Highest confidence: literal graphic overlay text mirrors on-screen UI.
    for g in graphic_text:
        cleaned = g.strip()
        if cleaned and len(cleaned) <= 40:
            keywords.append(cleaned)

    for pattern in (_OVR_RE, _RATING_RE, _GRADE_RE, _SCORE_RE, _MINUTE_RE):
        for m in pattern.findall(text):
            token = m if isinstance(m, str) else m[0]
            if token not in keywords:
                keywords.append(token)

    return keywords
