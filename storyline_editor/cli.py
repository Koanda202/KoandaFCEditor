from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .editor import build_video
from .ffmpeg_utils import FFmpegNotFoundError
from .project import load_project
from .storyline import load_storyline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="koanda-editor",
        description=(
            "Assemble an edited video from ROG Ally recording clips, VO lines, "
            "and a story."
        ),
    )
    parser.add_argument(
        "path", type=Path,
        help=(
            "A project folder containing clips/, vo/, and story.txt "
            "(zero-config mode) — or a storyline YAML file for manual control"
        ),
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Override the output path",
    )
    parser.add_argument(
        "--keep-scenes", action="store_true",
        help="Keep the individual rendered scene files alongside the output",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args(argv)

    try:
        if args.path.is_dir():
            storyline = load_project(args.path)
        else:
            storyline = load_storyline(args.path)
        if args.output:
            storyline.output = args.output
        output = build_video(storyline, keep_temp=args.keep_scenes, verbose=not args.quiet)
    except (FFmpegNotFoundError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"done: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
