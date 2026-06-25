#!/usr/bin/env python3
"""Generate the PipeOwl dataset-calibrated replay mission."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeowl import build_calibrated_mission, validate_mission


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/calibrated_mission", help="Output mission directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    build_calibrated_mission(out_dir)
    errors = validate_mission(out_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Generated PipeOwl dataset-calibrated replay at {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
