"""Canonical PipeOwl mission schema helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence


REQUIRED_FILES = (
    "metadata.json",
    "network.geojson",
    "robot_state.csv",
    "imu.csv",
    "reel.csv",
    "hydrophone.wav",
    "acoustic_features.csv",
    "events.csv",
)

REQUIRED_COLUMNS: Mapping[str, Sequence[str]] = {
    "robot_state.csv": (
        "time_s",
        "distance_m",
        "x_m",
        "y_m",
        "heading_rad",
        "speed_mps",
        "pressure_bar",
        "flow_velocity_mps",
        "pipe_id",
    ),
    "imu.csv": (
        "time_s",
        "distance_m",
        "ax_mps2",
        "ay_mps2",
        "az_mps2",
        "gx_radps",
        "gy_radps",
        "gz_radps",
        "accel_mag",
        "gyro_mag",
        "jerk",
    ),
    "reel.csv": (
        "time_s",
        "distance_m",
        "tether_length_m",
        "payout_speed_mps",
        "tether_tension_N",
    ),
    "acoustic_features.csv": (
        "window_start_s",
        "window_end_s",
        "distance_m",
        "rms",
        "peak",
        "bandpower_100_500",
        "bandpower_500_2000",
        "bandpower_2000_10000",
        "spectral_centroid_hz",
        "leak_score",
    ),
    "events.csv": (
        "event_id",
        "type",
        "time_s",
        "distance_m",
        "x_m",
        "y_m",
        "confidence",
        "source",
        "evidence",
        "notes",
    ),
}

ALLOWED_EVENT_TYPES = {
    "possible_leak",
    "possible_bend",
    "intersection",
    "possible_impact",
    "possible_stuck",
    "tether_artifact",
}


@dataclass(frozen=True)
class MissionPaths:
    """Resolved paths for a canonical PipeOwl mission directory."""

    root: Path

    @property
    def metadata(self) -> Path:
        return self.root / "metadata.json"

    @property
    def network(self) -> Path:
        return self.root / "network.geojson"

    @property
    def robot_state(self) -> Path:
        return self.root / "robot_state.csv"

    @property
    def imu(self) -> Path:
        return self.root / "imu.csv"

    @property
    def reel(self) -> Path:
        return self.root / "reel.csv"

    @property
    def hydrophone(self) -> Path:
        return self.root / "hydrophone.wav"

    @property
    def acoustic_features(self) -> Path:
        return self.root / "acoustic_features.csv"

    @property
    def events(self) -> Path:
        return self.root / "events.csv"


def load_metadata(mission_dir: Path) -> Dict:
    with (mission_dir / "metadata.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def validate_mission(mission_dir: Path) -> List[str]:
    """Return schema validation errors for a mission directory."""

    mission_dir = Path(mission_dir)
    errors: List[str] = []

    for filename in REQUIRED_FILES:
        if not (mission_dir / filename).exists():
            errors.append(f"missing required file: {filename}")

    if (mission_dir / "metadata.json").exists():
        try:
            metadata = load_metadata(mission_dir)
        except json.JSONDecodeError as exc:
            errors.append(f"metadata.json is invalid JSON: {exc}")
        else:
            if not metadata.get("mission_id"):
                errors.append("metadata.json missing mission_id")
            if "data_sources" not in metadata:
                errors.append("metadata.json missing data_sources")
            if "pipe" not in metadata:
                errors.append("metadata.json missing pipe")
            if "sonde" not in metadata:
                errors.append("metadata.json missing sonde")

    if (mission_dir / "network.geojson").exists():
        try:
            with (mission_dir / "network.geojson").open("r", encoding="utf-8") as handle:
                network = json.load(handle)
        except json.JSONDecodeError as exc:
            errors.append(f"network.geojson is invalid JSON: {exc}")
        else:
            if network.get("type") != "FeatureCollection":
                errors.append("network.geojson must be a FeatureCollection")

    for filename, required in REQUIRED_COLUMNS.items():
        path = mission_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            missing = [column for column in required if column not in fieldnames]
            if missing:
                errors.append(f"{filename} missing columns: {', '.join(missing)}")

            if filename == "events.csv":
                for index, row in enumerate(reader, start=2):
                    event_type = row.get("type", "")
                    if event_type and event_type not in ALLOWED_EVENT_TYPES:
                        errors.append(f"events.csv line {index} unknown event type: {event_type}")
                    confidence = row.get("confidence", "")
                    if confidence:
                        try:
                            value = float(confidence)
                        except ValueError:
                            errors.append(f"events.csv line {index} invalid confidence")
                        else:
                            if value < 0.0 or value > 1.0:
                                errors.append(f"events.csv line {index} confidence outside 0..1")

    return errors
