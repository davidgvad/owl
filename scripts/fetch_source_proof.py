#!/usr/bin/env python3
"""Fetch small public source-proof artifacts for the calibrated replay."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeowl.provenance import PROOF_ARTIFACTS, write_mission_source_manifest, write_source_manifest


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "PipeOwl-source-proof/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        path.write_bytes(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/source_artifacts", help="Artifact directory")
    parser.add_argument("--mission", default="", help="Optional mission directory to receive source_manifest.json")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Keep already downloaded artifacts and only rebuild the manifest",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    for spec in PROOF_ARTIFACTS:
        target = out_dir / spec["local_file"]
        if args.skip_existing and target.exists():
            continue
        print(f"fetch {spec['id']}: {spec['source_url']}")
        download(spec["source_url"], target)

    manifest_path = write_source_manifest(out_dir)
    print(f"wrote {manifest_path}")

    if args.mission:
        mission_manifest = write_mission_source_manifest(Path(args.mission), out_dir)
        print(f"wrote {mission_manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
