from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .editor import build_video
from .ffmpeg_utils import FFmpegNotFoundError
from .guide_project import find_guide_file, load_guide_project
from .ocr import TesseractNotFoundError
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
            "A project folder containing clips/, vo/, and story.txt or "
            "guide.txt (zero-config mode) — or a storyline YAML file for "
            "manual control"
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

    anchors = None
    try:
        guide_file = find_guide_file(args.path) if args.path.is_dir() else None
        if guide_file is not None:
            storyline, anchors = load_guide_project(args.path, guide_file, verbose=not args.quiet)
        elif args.path.is_dir():
            storyline = load_project(args.path)
        else:
            storyline = load_storyline(args.path)
        if args.output:
            storyline.output = args.output
        output = build_video(storyline, keep_temp=args.keep_scenes, verbose=not args.quiet)
    except (FFmpegNotFoundError, TesseractNotFoundError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"done: {output}")
        if anchors is not None:
            unconfirmed = [a for a in anchors if not a.confirmed]
            if unconfirmed:
                print(
                    f"\n{len(unconfirmed)} of {len(anchors)} section(s) had no on-screen "
                    "text to confirm the moment — best-guessed instead. Please review:"
                )
                for a in unconfirmed:
                    print(
                        f"  - Section {a.section.number} ({a.section.title}): "
                        f"{a.file.name} @ {a.time:.1f}s"
                    )
            else:
                print(f"\nAll {len(anchors)} section(s) confirmed via on-screen text.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
