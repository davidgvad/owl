#!/usr/bin/env python3
"""Convert a SubPipe export into partial PipeOwl canonical files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeowl.adapters.subpipe_adapter import SubPipeAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", help="Directory containing SubPipe CSV files")
    parser.add_argument("--out", required=True, help="Output mission directory")
    args = parser.parse_args()

    result = SubPipeAdapter().convert(Path(args.input_dir), Path(args.out))
    print(f"Converted SubPipe motion streams into {result.output_dir}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
