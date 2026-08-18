from storyline_editor.guide import parse_guide

SAMPLE = """
============================================================
SECTION 1 — OPENING HOOK
============================================================

TARGET LENGTH
-------------
10–15 seconds

CLIP
----
Yallop 61' sequence: Rabona assist to finish.

VO
--
“This was Mitchell Yallop’s first game for Koanda FC.”

“It went reasonably well.”


============================================================
SECTION 2 — REVEAL
============================================================

TARGET LENGTH
-------------
5–8 seconds

GRAPHIC
-------
Freeze / punch-in.

99 POTENTIAL

Use one restrained impact sound.

EDITING
-------
Optional freeze frame or 115–125% punch-in on the reaction.


============================================================
SECTION 3 — MESSAGE
============================================================

IMPORTANT
---------
Hold the message roughly 4–6 seconds depending on text length.

VO
--
“Afterward, he apologized for the defeat.”


============================================================
NOT A SECTION — SETUP NOTES
============================================================

Just some reference text that should be ignored.
"""


def test_parse_guide_returns_only_numbered_sections_in_order():
    sections = parse_guide(SAMPLE)
    assert [s.number for s in sections] == [1, 2, 3]
    assert [s.title for s in sections] == ["OPENING HOOK", "REVEAL", "MESSAGE"]


def test_parse_guide_extracts_target_length():
    sections = parse_guide(SAMPLE)
    assert sections[0].target_length == (10, 15)
    assert sections[1].target_length == (5, 8)
    assert sections[2].target_length is None


def test_parse_guide_extracts_vo_lines_in_order():
    sections = parse_guide(SAMPLE)
    assert sections[0].vo_lines == [
        "This was Mitchell Yallop’s first game for Koanda FC.",
        "It went reasonably well.",
    ]


def test_parse_guide_extracts_minute_marker_keyword_from_clip_notes():
    sections = parse_guide(SAMPLE)
    assert "61'" in sections[0].keywords


def test_parse_guide_filters_directorial_notes_from_graphic_text():
    sections = parse_guide(SAMPLE)
    # "Freeze / punch-in." and "Use one restrained impact sound." are
    # directorial notes (full sentences, end in punctuation) that happen to
    # sit under the GRAPHIC header — only the literal title-card text
    # ("99 POTENTIAL") should survive as display text / keywords.
    assert sections[1].graphic_text == ["99 POTENTIAL"]
    assert sections[1].keywords == ["99 POTENTIAL"]


def test_parse_guide_freeze_and_zoom_from_editing_notes():
    sections = parse_guide(SAMPLE)
    assert sections[1].freeze_seconds > 0
    assert sections[1].zoom_percent == 120.0


def test_parse_guide_graphic_hold_seconds_from_important_notes():
    sections = parse_guide(SAMPLE)
    assert sections[2].graphic_hold_seconds == 5.0


def test_parse_guide_empty_text_returns_empty_list():
    assert parse_guide("no sections here at all") == []
