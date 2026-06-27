"""Import real PipeOwl hardware/test-loop logs into the canonical mission format."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .features import add_imu_features, extract_acoustic_features, interpolate_distance
from .schemas import REQUIRED_COLUMNS, validate_mission, write_csv


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(row: Mapping[str, str], field: str, default: Optional[float] = None) -> float:
    value = row.get(field, "")
    if value == "" or value is None:
        if default is None:
            raise ValueError(f"missing required field {field}")
        return default
    return float(value)


def normalize_time(rows: Sequence[Mapping[str, str]], offset_s: float) -> List[Dict[str, str]]:
    normalized = []
    for row in rows:
        out = dict(row)
        out["time_s"] = f"{as_float(row, 'time_s') - offset_s:.6f}"
        normalized.append(out)
    return normalized


def common_time_offset(*row_sets: Sequence[Mapping[str, str]]) -> float:
    first_times = []
    for rows in row_sets:
        if rows:
            first_times.append(as_float(rows[0], "time_s"))
    return min(first_times) if first_times else 0.0


def prepare_reel(rows: Sequence[Mapping[str, str]]) -> List[Dict[str, float]]:
    prepared: List[Dict[str, float]] = []
    previous_time = None
    previous_length = None

    for row in sorted(rows, key=lambda item: as_float(item, "time_s")):
        time_s = as_float(row, "time_s")
        tether_length = as_float(row, "tether_length_m", as_float(row, "distance_m", 0.0))
        distance = as_float(row, "distance_m", tether_length)
        if "payout_speed_mps" in row and row["payout_speed_mps"] != "":
            payout_speed = as_float(row, "payout_speed_mps")
        elif previous_time is None or previous_length is None:
            payout_speed = 0.0
        else:
            payout_speed = (tether_length - previous_length) / max(1e-6, time_s - previous_time)

        prepared.append(
            {
                "time_s": time_s,
                "distance_m": distance,
                "tether_length_m": tether_length,
                "payout_speed_mps": payout_speed,
                "tether_tension_N": as_float(row, "tether_tension_N", 0.0),
            }
        )
        previous_time = time_s
        previous_length = tether_length

    return prepared


def prepare_imu(rows: Sequence[Mapping[str, str]], reel_rows: Sequence[Mapping[str, float]]) -> List[Dict[str, float]]:
    prepared = []
    for row in sorted(rows, key=lambda item: as_float(item, "time_s")):
        time_s = as_float(row, "time_s")
        distance = as_float(row, "distance_m", interpolate_distance(reel_rows, time_s))
        prepared.append(
            {
                "time_s": time_s,
                "distance_m": distance,
                "ax_mps2": as_float(row, "ax_mps2"),
                "ay_mps2": as_float(row, "ay_mps2"),
                "az_mps2": as_float(row, "az_mps2"),
                "gx_radps": as_float(row, "gx_radps"),
                "gy_radps": as_float(row, "gy_radps"),
                "gz_radps": as_float(row, "gz_radps"),
            }
        )
    return add_imu_features(prepared)


def prepare_robot_state(reel_rows: Sequence[Mapping[str, float]],
                        pressure_bar: float,
                        flow_velocity_mps: float) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    previous_distance = None
    previous_time = None

    for row in reel_rows:
        time_s = float(row["time_s"])
        distance = float(row["distance_m"])
        if previous_time is None or previous_distance is None:
            speed = 0.0
        else:
            speed = (distance - previous_distance) / max(1e-6, time_s - previous_time)

        rows.append(
            {
                "time_s": time_s,
                "distance_m": distance,
                "x_m": distance,
                "y_m": 0.0,
                "heading_rad": 0.0,
                "speed_mps": speed,
                "pressure_bar": pressure_bar,
                "flow_velocity_mps": flow_velocity_mps,
                "pipe_id": "TEST_PIPE",
            }
        )
        previous_time = time_s
        previous_distance = distance

    return rows


def write_default_network(out_dir: Path, max_distance: float) -> None:
    length = max(1.0, max_distance)
    network = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "TEST_PIPE",
                    "kind": "pipe",
                    "diameter_mm": 100,
                    "material": "test_loop",
                    "length_m": length,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[0.0, 0.0], [length, 0.0]],
                },
            }
        ],
    }
    with (out_dir / "network.geojson").open("w", encoding="utf-8") as handle:
        json.dump(network, handle, indent=2)
        handle.write("\n")


def pose_at_distance(robot_state_rows: Sequence[Mapping[str, object]], distance_m: float) -> Dict[str, float]:
    if not robot_state_rows:
        return {"x_m": distance_m, "y_m": 0.0}
    rows = sorted(robot_state_rows, key=lambda row: float(row["distance_m"]))
    if distance_m <= float(rows[0]["distance_m"]):
        return {"x_m": float(rows[0]["x_m"]), "y_m": float(rows[0]["y_m"])}
    for previous, current in zip(rows, rows[1:]):
        prev_distance = float(previous["distance_m"])
        current_distance = float(current["distance_m"])
        if prev_distance <= distance_m <= current_distance:
            span = max(1e-6, current_distance - prev_distance)
            ratio = (distance_m - prev_distance) / span
            return {
                "x_m": float(previous["x_m"]) + ratio * (float(current["x_m"]) - float(previous["x_m"])),
                "y_m": float(previous["y_m"]) + ratio * (float(current["y_m"]) - float(previous["y_m"])),
            }
    return {"x_m": float(rows[-1]["x_m"]), "y_m": float(rows[-1]["y_m"])}


def rows_in_time(rows: Iterable[Mapping[str, object]], start_s: float, end_s: float) -> List[Mapping[str, object]]:
    return [row for row in rows if start_s <= float(row["time_s"]) <= end_s]


def create_detected_events(robot_state_rows: Sequence[Mapping[str, object]],
                           imu_rows: Sequence[Mapping[str, object]],
                           reel_rows: Sequence[Mapping[str, object]],
                           acoustic_rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []

    def add_event(event_id: str,
                  event_type: str,
                  time_s: float,
                  distance_m: float,
                  confidence: float,
                  source: str,
                  notes: str) -> None:
        pose = pose_at_distance(robot_state_rows, distance_m)
        events.append(
            {
                "event_id": event_id,
                "type": event_type,
                "time_s": round(time_s, 2),
                "distance_m": round(distance_m, 2),
                "x_m": round(pose["x_m"], 2),
                "y_m": round(pose["y_m"], 2),
                "confidence": round(max(0.0, min(1.0, confidence)), 2),
                "source": source,
                "notes": notes,
            }
        )

    if imu_rows:
        impact = max(imu_rows, key=lambda row: max(float(row["accel_mag"]) - 9.81, abs(float(row["jerk"])) / 18.0))
        impact_strength = max(float(impact["accel_mag"]) - 9.81, abs(float(impact["jerk"])) / 18.0)
        if impact_strength > 2.7:
            add_event(
                "H001",
                "possible_impact",
                float(impact["time_s"]),
                float(impact["distance_m"]),
                min(0.95, 0.35 + impact_strength / 9.0),
                "hardware_imu",
                "Detected from real IMU acceleration/jerk spike in imported PipeOwl logs.",
            )

        turn = max(imu_rows, key=lambda row: float(row["gyro_mag"]))
        if float(turn["gyro_mag"]) > 0.28:
            add_event(
                "H002",
                "possible_bend",
                float(turn["time_s"]),
                float(turn["distance_m"]),
                min(0.9, 0.35 + float(turn["gyro_mag"])),
                "hardware_imu",
                "Detected from real IMU gyro magnitude rise in imported PipeOwl logs.",
            )

    leak_candidates = sorted(
        [row for row in acoustic_rows if float(row["leak_score"]) > 0.75],
        key=lambda row: float(row["leak_score"]),
        reverse=True,
    )
    for candidate in leak_candidates:
        start_s = float(candidate["window_start_s"])
        end_s = float(candidate["window_end_s"])
        imu_window = rows_in_time(imu_rows, start_s - 0.5, end_s + 0.5)
        reel_window = rows_in_time(reel_rows, start_s - 0.5, end_s + 0.5)
        max_accel = max((float(row["accel_mag"]) for row in imu_window), default=9.81)
        max_tension = max((float(row["tether_tension_N"]) for row in reel_window), default=0.0)
        if max_accel < 13.0 and max_tension < 4.5:
            add_event(
                "H003",
                "possible_leak",
                start_s,
                float(candidate["distance_m"]),
                float(candidate["leak_score"]),
                "hardware_hydrophone",
                "Detected from real hydrophone audio features with no matching IMU impact or tether artifact.",
            )
            break

    return sorted(events, key=lambda row: float(row["time_s"]))


def format_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    formatted = []
    for row in rows:
        out: Dict[str, object] = {}
        for key, value in row.items():
            if isinstance(value, float):
                out[key] = f"{value:.6f}".rstrip("0").rstrip(".")
            else:
                out[key] = value
        formatted.append(out)
    return formatted


def wav_summary(path: Path) -> Dict[str, object]:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "duration_s": frames / max(1, sample_rate),
    }


def write_hardware_manifest(out_dir: Path,
                            raw_dir: Path,
                            raw_files: Sequence[Path],
                            imu_rows: Sequence[Mapping[str, object]],
                            reel_rows: Sequence[Mapping[str, object]],
                            acoustic_rows: Sequence[Mapping[str, object]],
                            event_rows: Sequence[Mapping[str, object]]) -> None:
    artifacts = []
    for path in raw_files:
        artifacts.append(
            {
                "id": f"PIPEOWL_{path.stem.upper()}",
                "stream": "hardware_log",
                "title": path.name,
                "role": "Raw PipeOwl hardware/test-loop source log imported into this mission",
                "source_url": str(path),
                "local_file": str(path.relative_to(raw_dir)),
                "local_path": str(path),
                "status": "available",
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "claim_supported": "This mission contains data imported from a local PipeOwl hardware/test-loop recording.",
            }
        )

    hydrophone_path = raw_dir / "hydrophone.wav"
    manifest = {
        "manifest_version": "1.0",
        "purpose": "Auditable raw-log proof bundle for a PipeOwl hardware/test-loop mission.",
        "honest_claim": (
            "This mission was imported from local PipeOwl hardware/test-loop logs. "
            "Raw file hashes are recorded so the canonical mission can be traced back to the source recording."
        ),
        "artifacts": artifacts,
        "evidence_summary": {
            "hardware": {
                "imu_rows": len(imu_rows),
                "reel_rows": len(reel_rows),
                "acoustic_windows": len(acoustic_rows),
                "event_rows": len(event_rows),
                "hydrophone": wav_summary(hydrophone_path),
            }
        },
        "claim_boundaries": [
            "This proves the dashboard is running from local PipeOwl logs, not from the calibrated public-dataset replay.",
            "Real leak labels still require a controlled test-loop leak location or utility ground truth.",
            "Network intersections are real only when the raw folder includes a surveyed network.geojson or known test-loop geometry.",
        ],
    }
    with (out_dir / "source_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def build_hardware_mission(raw_dir: Path, out_dir: Path) -> None:
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    imu_path = raw_dir / "imu.csv"
    reel_path = raw_dir / "reel.csv"
    hydrophone_path = raw_dir / "hydrophone.wav"
    missing = [path.name for path in (imu_path, reel_path, hydrophone_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing raw hardware logs: {', '.join(missing)}")

    raw_imu = read_csv_rows(imu_path)
    raw_reel = read_csv_rows(reel_path)
    offset = common_time_offset(raw_imu, raw_reel)
    raw_imu = normalize_time(raw_imu, offset)
    raw_reel = normalize_time(raw_reel, offset)

    metadata_path = raw_dir / "metadata.json"
    source_metadata = {}
    if metadata_path.exists():
        source_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    pressure_bar = float(source_metadata.get("nominal_pressure_bar", 0.0))
    flow_velocity_mps = float(source_metadata.get("nominal_flow_velocity_mps", 0.0))
    reel_rows = prepare_reel(raw_reel)
    imu_rows = prepare_imu(raw_imu, reel_rows)
    robot_state_rows = prepare_robot_state(reel_rows, pressure_bar, flow_velocity_mps)

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hydrophone_path, out_dir / "hydrophone.wav")
    network_path = raw_dir / "network.geojson"
    if network_path.exists():
        shutil.copyfile(network_path, out_dir / "network.geojson")
    else:
        max_distance = max((float(row["distance_m"]) for row in robot_state_rows), default=1.0)
        write_default_network(out_dir, max_distance)

    acoustic_rows = extract_acoustic_features(out_dir / "hydrophone.wav", robot_state_rows)
    event_rows = create_detected_events(robot_state_rows, imu_rows, reel_rows, acoustic_rows)

    metadata = {
        "mission_id": source_metadata.get("mission_id", raw_dir.name),
        "mission_name": source_metadata.get("mission_name", "PipeOwl Hardware Mission"),
        "replay_mode": "hardware_import",
        "data_sources": ["PipeOwl hardware/test-loop logs"],
        "source_manifest": "source_manifest.json",
        "provenance_note": "Imported from real local IMU, reel, and hydrophone logs.",
        "pipe": {
            "material": source_metadata.get("pipe_material", "test_loop"),
            "diameter_mm": source_metadata.get("pipe_diameter_mm", 100),
            "nominal_pressure_bar": pressure_bar,
            "nominal_flow_velocity_mps": flow_velocity_mps,
        },
        "sonde": {
            "diameter_mm": source_metadata.get("sonde_diameter_mm", 60),
            "sensors": ["hydrophone", "imu", "reel_encoder", "tether_tension"],
        },
    }
    with (out_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")

    write_csv(out_dir / "robot_state.csv", format_rows(robot_state_rows), REQUIRED_COLUMNS["robot_state.csv"])
    write_csv(out_dir / "imu.csv", format_rows(imu_rows), REQUIRED_COLUMNS["imu.csv"])
    write_csv(out_dir / "reel.csv", format_rows(reel_rows), REQUIRED_COLUMNS["reel.csv"])
    write_csv(
        out_dir / "acoustic_features.csv",
        format_rows(acoustic_rows),
        REQUIRED_COLUMNS["acoustic_features.csv"],
    )
    write_csv(out_dir / "events.csv", format_rows(event_rows), REQUIRED_COLUMNS["events.csv"])

    raw_files = [imu_path, reel_path, hydrophone_path]
    if metadata_path.exists():
        raw_files.append(metadata_path)
    if network_path.exists():
        raw_files.append(network_path)
    write_hardware_manifest(out_dir, raw_dir, raw_files, imu_rows, reel_rows, acoustic_rows, event_rows)

    errors = validate_mission(out_dir)
    if errors:
        raise ValueError("; ".join(errors))
