"""CLI entrypoint for force-delete-win."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .windows import force_delete_file_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="force-delete-win",
        description="Force delete files/folders on Windows 10/11 (Python 3.10+).",
    )
    parser.add_argument("path", type=Path, help="Path to file or folder to delete")
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of process-kill retry cycles (default: 3)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        deleted = force_delete_file_folder(args.path, retries=max(0, args.retries))
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if deleted:
        print(f"Deleted: {args.path}")
        return 0

    print(f"Could not delete: {args.path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
