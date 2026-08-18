from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

import yaml


@dataclasses.dataclass
class Scene:
    name: str
    clip: Path
    start: str
    end: str
    vo: Optional[Path] = None
    vo_offset: str = "0"
    vo_volume: float = 1.0
    clip_volume: float = 1.0


@dataclasses.dataclass
class Storyline:
    title: str
    output: Path
    scenes: list[Scene]


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

    scenes = []
    for i, scene_data in enumerate(scenes_data):
        try:
            scenes.append(_parse_scene(scene_data, base_dir))
        except KeyError as e:
            raise ValueError(f"Scene {i} in {path} is missing required field: {e}") from e

    output = data.get("output", "output.mp4")
    return Storyline(
        title=data.get("title", path.stem),
        output=_resolve(output, base_dir),
        scenes=scenes,
    )


def _parse_scene(data: dict, base_dir: Path) -> Scene:
    name = data.get("name", "scene")
    clip = _resolve(data["clip"], base_dir)
    start = str(data.get("start", 0))
    end = str(data["end"])
    vo = data.get("vo")
    vo_path = _resolve(vo, base_dir) if vo else None
    return Scene(
        name=name,
        clip=clip,
        start=start,
        end=end,
        vo=vo_path,
        vo_offset=str(data.get("vo_offset", 0)),
        vo_volume=float(data.get("vo_volume", 1.0)),
        clip_volume=float(data.get("clip_volume", 1.0)),
    )


def _resolve(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path
