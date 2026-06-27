#!/usr/bin/env python3
"""Import real PipeOwl hardware/test-loop logs into a canonical mission."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeowl import build_hardware_mission, validate_mission


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, help="Raw hardware log folder")
    parser.add_argument("--out", default="data/real_mission", help="Canonical mission output folder")
    args = parser.parse_args()

    try:
        build_hardware_mission(Path(args.raw), Path(args.out))
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = validate_mission(Path(args.out))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Imported PipeOwl hardware mission at {args.out}")
    print("Run with:")
    print(f"  PIPEOWL_MISSION_DIR={args.out} ./run_local.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
