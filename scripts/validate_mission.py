#!/usr/bin/env python3
"""Validate a canonical PipeOwl mission directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeowl import validate_mission


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mission_dir", help="Mission directory to validate")
    args = parser.parse_args()

    errors = validate_mission(Path(args.mission_dir))
    if errors:
        print("Mission validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Mission validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
