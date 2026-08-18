from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

import yaml


@dataclasses.dataclass
class Scene:
    name: str
    clip: Optional[Path] = None
    start: Optional[str] = None
    end: Optional[str] = None
    vo: Optional[Path] = None
    vo_offset: str = "0"
    vo_volume: float = 1.0
    clip_volume: float = 1.0
    # Guide-driven scenes only (all optional, no effect when unset):
    vo_lines: Optional[list] = None  # multiple VO files spoken in sequence
    vo_pause: float = 0.5            # gap between vo_lines, seconds
    graphic_text: str = ""           # on-screen text overlay, empty = none
    graphic_hold_seconds: float = 2.5
    freeze_seconds: float = 0.0      # freeze the last frame for N extra seconds
    zoom_percent: float = 0.0        # static punch-in crop, 0 = no zoom
    confirmed: bool = True           # False = auto-picked without an OCR match
    guide_number: Optional[int] = None


@dataclasses.dataclass
class Storyline:
    title: str
    output: Path
    scenes: list[Scene]
    clips_dir: Optional[Path] = None
    highlight_duration: float = 12.0
    highlight_min_gap: float = 6.0


def load_storyline(path: Path) -> Storyline:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Storyline file must contain a mapping at the top level: {path}")

    base_dir = path.parent
    scenes_data = data.get("scenes")
    if not scenes_data:
        raise ValueError(f"Storyline file has no scenes: {path}")

    scenes = [_parse_scene(s, base_dir, i) for i, s in enumerate(scenes_data)]

    clips_dir = data.get("clips_dir")
    output = data.get("output", "output.mp4")
    storyline = Storyline(
        title=data.get("title", path.stem),
        output=_resolve(output, base_dir),
        scenes=scenes,
        clips_dir=_resolve(clips_dir, base_dir) if clips_dir else None,
        highlight_duration=float(data.get("highlight_duration", 12.0)),
        highlight_min_gap=float(data.get("highlight_min_gap", 6.0)),
    )

    needs_auto = any(s.clip is None for s in storyline.scenes)
    if needs_auto and storyline.clips_dir is None:
        raise ValueError(
            f"{path}: one or more scenes have no 'clip' set (auto-detect mode), but the "
            "storyline has no top-level 'clips_dir' pointing at your recordings folder."
        )
    return storyline


def _parse_scene(data: dict, base_dir: Path, index: int) -> Scene:
    name = data.get("name", f"scene_{index}")
    clip = data.get("clip")
    start = data.get("start")
    end = data.get("end")

    if clip is not None and (start is None or end is None):
        raise ValueError(
            f"Scene {name!r} (index {index}) sets 'clip' but is missing 'start' and/or 'end' "
            "— either provide all three for a manual scene, or none of them to auto-detect."
        )
    if clip is None and (start is not None or end is not None):
        raise ValueError(
            f"Scene {name!r} (index {index}) sets 'start'/'end' but is missing 'clip'"
        )

    vo = data.get("vo")
    return Scene(
        name=name,
        clip=_resolve(clip, base_dir) if clip else None,
        start=str(start) if start is not None else None,
        end=str(end) if end is not None else None,
        vo=_resolve(vo, base_dir) if vo else None,
        vo_offset=str(data.get("vo_offset", 0)),
        vo_volume=float(data.get("vo_volume", 1.0)),
        clip_volume=float(data.get("clip_volume", 1.0)),
    )


def _resolve(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path
