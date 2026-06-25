"""Source-proof helpers for the PipeOwl calibrated replay."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional


PROOF_ARTIFACTS: List[Dict[str, str]] = [
    {
        "id": "GPLA12_README",
        "stream": "acoustic_leak",
        "title": "GPLA-12 dataset README",
        "role": "Public source description for pipeline acoustic leakage samples",
        "source_url": "https://raw.githubusercontent.com/Deep-AI-Application-DAIP/acoustic-leakage-dataset-GPLA-12/main/README.md",
        "local_file": "gpla12_readme.md",
        "claim_supported": "GPLA-12 is a public pipeline acoustic leakage dataset used as leak-audio proxy evidence.",
    },
    {
        "id": "GPLA12_DATA_V1",
        "stream": "acoustic_leak",
        "title": "GPLA-12 raw acoustic data v1 CSV",
        "role": "Real acoustic leakage signal table used to calibrate leak-score patterns",
        "source_url": "https://raw.githubusercontent.com/Deep-AI-Application-DAIP/acoustic-leakage-dataset-GPLA-12/main/data/data_v1/data.csv",
        "local_file": "gpla12_data_v1_data.csv",
        "claim_supported": "Leak-like replay audio uses GPLA-12 acoustic scale and high-frequency scoring workflow as a proxy, not PipeOwl hardware audio.",
    },
    {
        "id": "GPLA12_LABELS_V1",
        "stream": "acoustic_leak",
        "title": "GPLA-12 v1 labels CSV",
        "role": "Real public labels for the GPLA-12 acoustic rows",
        "source_url": "https://raw.githubusercontent.com/Deep-AI-Application-DAIP/acoustic-leakage-dataset-GPLA-12/main/data/data_v1/label.csv",
        "local_file": "gpla12_data_v1_label.csv",
        "claim_supported": "Leak scoring is calibrated against labeled public leakage categories rather than invented labels.",
    },
    {
        "id": "GPLA12_LICENSE",
        "stream": "license",
        "title": "GPLA-12 repository license",
        "role": "License proof for the bundled GPLA-12 source artifacts",
        "source_url": "https://raw.githubusercontent.com/Deep-AI-Application-DAIP/acoustic-leakage-dataset-GPLA-12/main/LICENSE",
        "local_file": "gpla12_license.txt",
        "claim_supported": "The proof bundle records licensing context for the acoustic proxy artifacts.",
    },
    {
        "id": "GPLA12_TREE",
        "stream": "acoustic_leak",
        "title": "GPLA-12 GitHub repository tree",
        "role": "GitHub API index proving the public raw acoustic and label file paths",
        "source_url": "https://api.github.com/repos/Deep-AI-Application-DAIP/acoustic-leakage-dataset-GPLA-12/git/trees/main?recursive=1",
        "local_file": "gpla12_tree.json",
        "claim_supported": "The bundled GPLA-12 raw data and label files come from public repository paths.",
    },
    {
        "id": "SUBPIPE_README",
        "stream": "motion_imu",
        "title": "SubPipe dataset README",
        "role": "Public source description of underwater pipeline inspection IMU/navigation files",
        "source_url": "https://raw.githubusercontent.com/remaro-network/SubPipe-dataset/main/README.md",
        "local_file": "subpipe_readme.md",
        "claim_supported": "IMU, pressure, flow, and forward-distance replay patterns are calibrated from a real underwater pipeline-inspection dataset description.",
    },
    {
        "id": "SUBPIPE_ZENODO",
        "stream": "motion_imu",
        "title": "SubPipe Zenodo record metadata",
        "role": "Official archive metadata and file sizes for the full SubPipe dataset",
        "source_url": "https://zenodo.org/api/records/10053564",
        "local_file": "subpipe_zenodo_record.json",
        "claim_supported": "SubPipe raw archives exist publicly but are multi-GB, so this repo stores metadata proof instead of bundling the full dataset.",
    },
    {
        "id": "SUBPIPE_LICENSE",
        "stream": "license",
        "title": "SubPipe repository license",
        "role": "License proof for the SubPipe source metadata artifact",
        "source_url": "https://raw.githubusercontent.com/remaro-network/SubPipe-dataset/main/LICENSE",
        "local_file": "subpipe_license.txt",
        "claim_supported": "The proof bundle records licensing context for the SubPipe metadata artifact.",
    },
    {
        "id": "AQUALOC_PAGE",
        "stream": "motion_imu_pressure",
        "title": "AQUALOC official dataset page",
        "role": "Underwater ROV IMU/pressure timing reference",
        "source_url": "https://www.lirmm.fr/aqualoc/",
        "local_file": "aqualoc_page.html",
        "claim_supported": "AQUALOC supports the underwater IMU and pressure-timestamping assumptions used by the replay framework.",
    },
    {
        "id": "OCEANSHIP_ARXIV",
        "stream": "acoustic_background",
        "title": "OceanShip arXiv metadata",
        "role": "Hydrophone-style underwater background-noise reference",
        "source_url": "https://export.arxiv.org/api/query?id_list=2401.02099",
        "local_file": "oceanship_arxiv.json",
        "claim_supported": "OceanShip is used only as a public underwater acoustic background reference, not as leak truth.",
    },
    {
        "id": "WNTR_README",
        "stream": "pipe_network",
        "title": "WNTR repository README",
        "role": "Public source description for EPANET-compatible water-network modeling",
        "source_url": "https://raw.githubusercontent.com/USEPA/WNTR/main/README.md",
        "local_file": "wntr_readme.md",
        "claim_supported": "Pipe geometry and hydraulic context use WNTR/EPANET-style network modeling.",
    },
    {
        "id": "WNTR_NET3_INP",
        "stream": "pipe_network",
        "title": "WNTR Net3 EPANET network",
        "role": "Real EPANET input file proving the network/intersection data format",
        "source_url": "https://raw.githubusercontent.com/USEPA/WNTR/main/examples/networks/Net3.inp",
        "local_file": "wntr_net3.inp",
        "claim_supported": "The replay route is shaped like a water-network graph and can map distance to nodes/intersections using EPANET-style data.",
    },
    {
        "id": "WNTR_LEAKS_INP",
        "stream": "pipe_network",
        "title": "WNTR leak test EPANET network",
        "role": "Real EPANET input file with leak-testing context",
        "source_url": "https://raw.githubusercontent.com/USEPA/WNTR/main/wntr/tests/networks_for_testing/leaks.inp",
        "local_file": "wntr_leaks.inp",
        "claim_supported": "Leak placement and hydraulic context are represented as water-network scenarios, not inferred from IMU alone.",
    },
    {
        "id": "WNTR_LICENSE",
        "stream": "license",
        "title": "WNTR repository license",
        "role": "License proof for bundled WNTR source artifacts",
        "source_url": "https://raw.githubusercontent.com/USEPA/WNTR/main/LICENSE.md",
        "local_file": "wntr_license.txt",
        "claim_supported": "The proof bundle records licensing context for WNTR/EPANET artifacts.",
    },
    {
        "id": "WNTR_TREE",
        "stream": "pipe_network",
        "title": "WNTR GitHub repository tree",
        "role": "GitHub API index proving the public EPANET network file paths",
        "source_url": "https://api.github.com/repos/USEPA/WNTR/git/trees/main?recursive=1",
        "local_file": "wntr_tree.json",
        "claim_supported": "The bundled WNTR Net3 and leak-test EPANET files come from public repository paths.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(artifact_dir: Path, spec: Mapping[str, str]) -> Dict[str, object]:
    local_path = artifact_dir / spec["local_file"]
    record: Dict[str, object] = dict(spec)
    record["local_path"] = str(local_path)
    if local_path.exists():
        record["status"] = "available"
        record["size_bytes"] = local_path.stat().st_size
        record["sha256"] = sha256_file(local_path)
    else:
        record["status"] = "missing"
        record["size_bytes"] = 0
        record["sha256"] = ""
    return record


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return sum(1 for _ in csv.reader(handle))


def first_csv_width(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        try:
            return len(next(csv.reader(handle)))
        except StopIteration:
            return 0


def count_epanet_section(path: Path, section_name: str) -> int:
    if not path.exists():
        return 0

    in_section = False
    rows = 0
    section_header = f"[{section_name.upper()}]"
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line.upper() == section_header
            continue
        if in_section:
            rows += 1
    return rows


def subpipe_archive_summary(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    archives = []
    for item in record.get("files", []):
        archives.append({"name": item.get("key"), "size_bytes": item.get("size")})
    return archives


def extract_line_matches(path: Path, patterns: Iterable[str]) -> List[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            matches.append(match.group(0).strip())
    return matches


def evidence_summary(artifact_dir: Path) -> Dict[str, object]:
    gpla_data = artifact_dir / "gpla12_data_v1_data.csv"
    gpla_labels = artifact_dir / "gpla12_data_v1_label.csv"
    subpipe_record = artifact_dir / "subpipe_zenodo_record.json"
    net3 = artifact_dir / "wntr_net3.inp"
    leaks = artifact_dir / "wntr_leaks.inp"

    summary: Dict[str, object] = {
        "gpla12": {
            "label_rows": count_csv_rows(gpla_labels),
            "data_rows": count_csv_rows(gpla_data),
            "samples_per_row": first_csv_width(gpla_data),
            "source_artifacts": ["GPLA12_DATA_V1", "GPLA12_LABELS_V1"],
        },
        "subpipe": {
            "zenodo_archives": subpipe_archive_summary(subpipe_record),
            "source_artifacts": ["SUBPIPE_README", "SUBPIPE_ZENODO"],
        },
        "wntr": {
            "net3_junction_rows": count_epanet_section(net3, "JUNCTIONS"),
            "net3_pipe_rows": count_epanet_section(net3, "PIPES"),
            "leak_test_junction_rows": count_epanet_section(leaks, "JUNCTIONS"),
            "leak_test_pipe_rows": count_epanet_section(leaks, "PIPES"),
            "source_artifacts": ["WNTR_NET3_INP", "WNTR_LEAKS_INP"],
        },
        "aqualoc": {
            "page_matches": extract_line_matches(
                artifact_dir / "aqualoc_page.html",
                [r"MEMS-IMU", r"pressure sensor", r"ROS", r"raw data"],
            ),
            "source_artifacts": ["AQUALOC_PAGE"],
        },
        "oceanship": {
            "source_artifacts": ["OCEANSHIP_ARXIV"],
            "role": "underwater acoustic background reference only",
        },
    }
    return summary


def build_source_manifest(artifact_dir: Path) -> Dict[str, object]:
    artifact_dir = Path(artifact_dir)
    records = [artifact_record(artifact_dir, spec) for spec in PROOF_ARTIFACTS]
    return {
        "manifest_version": "1.0",
        "purpose": "Auditable source-proof bundle for the PipeOwl dataset-calibrated replay.",
        "honest_claim": (
            "The replay is calibrated from public proxy datasets and real source artifacts. "
            "It is not yet PipeOwl hardware data, and no public source combines in-pipe hydrophone, "
            "IMU, tether, pipe intersections, and leak truth in one dataset."
        ),
        "artifacts": records,
        "evidence_summary": evidence_summary(artifact_dir),
        "claim_boundaries": [
            "GPLA-12 is gas-pipeline acoustic leakage data, used as a leak-audio proxy.",
            "SubPipe/AQUALOC support underwater robot motion and IMU/pressure behavior, not drinking-water in-pipe sonde truth.",
            "WNTR/EPANET artifacts support pipe-network geometry and hydraulic context.",
            "Intersections come from network geometry plus IMU turn patterns; hydrophone frequency alone is not treated as intersection proof.",
        ],
    }


def write_source_manifest(artifact_dir: Path, out_path: Optional[Path] = None) -> Path:
    artifact_dir = Path(artifact_dir)
    if out_path is None:
        out_path = artifact_dir / "source_manifest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_source_manifest(artifact_dir)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return out_path


def write_mission_source_manifest(mission_dir: Path,
                                  artifact_dir: Path = Path("data/source_artifacts")) -> Optional[Path]:
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.exists():
        return None
    return write_source_manifest(artifact_dir, Path(mission_dir) / "source_manifest.json")
