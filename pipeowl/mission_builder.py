"""Dataset-calibrated PipeOwl mission replay generation."""

from __future__ import annotations

import json
import math
import random
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .features import add_imu_features, extract_acoustic_features, interpolate_distance
from .calibration_profiles import CALIBRATION_SOURCES, PATTERN_LIBRARY
from .provenance import write_mission_source_manifest
from .schemas import REQUIRED_COLUMNS, write_csv

Point = Tuple[float, float]


ROUTE: Sequence[Tuple[str, Point, Point]] = (
    ("MAIN_A", (0.0, 0.0), (30.0, 0.0)),
    ("MAIN_B", (30.0, 0.0), (45.0, 8.0)),
    ("MAIN_C", (45.0, 8.0), (62.0, 8.0)),
)

BRANCHES: Sequence[Tuple[str, Point, Point]] = (
    ("BRANCH_NORTH", (15.0, 0.0), (15.0, 8.0)),
    ("SERVICE_SOUTH", (30.0, 0.0), (30.0, -10.0)),
    ("BYPASS", (45.0, 8.0), (45.0, 15.0)),
)

LEAK_DISTANCE_M = 47.0
IMPACT_DISTANCE_M = 34.0


def segment_length(start: Point, end: Point) -> float:
    return math.hypot(end[0] - start[0], end[1] - start[1])


def route_length() -> float:
    return sum(segment_length(start, end) for _, start, end in ROUTE)


def distance_to_pose(distance_m: float) -> Dict[str, object]:
    remaining = max(0.0, distance_m)
    traversed = 0.0
    for pipe_id, start, end in ROUTE:
        length = segment_length(start, end)
        if remaining <= length:
            ratio = remaining / length if length else 0.0
            x = start[0] + (end[0] - start[0]) * ratio
            y = start[1] + (end[1] - start[1]) * ratio
            heading = math.atan2(end[1] - start[1], end[0] - start[0])
            return {
                "x_m": x,
                "y_m": y,
                "heading_rad": heading,
                "pipe_id": pipe_id,
                "distance_m": traversed + remaining,
            }
        remaining -= length
        traversed += length

    pipe_id, start, end = ROUTE[-1]
    return {
        "x_m": end[0],
        "y_m": end[1],
        "heading_rad": math.atan2(end[1] - start[1], end[0] - start[0]),
        "pipe_id": pipe_id,
        "distance_m": traversed,
    }


def distance_to_time(distance_m: float, speed_mps: float = 0.70) -> float:
    return distance_m / speed_mps


def write_metadata(out_dir: Path) -> None:
    metadata = {
        "mission_id": "calibrated_001",
        "mission_name": "PipeOwl Dataset-Calibrated Replay",
        "replay_mode": "dataset_calibrated",
        "data_sources": [source["source"] for source in CALIBRATION_SOURCES],
        "source_manifest": "source_manifest.json",
        "source_proof_note": (
            "See source_manifest.json for downloaded public artifacts, source URLs, "
            "file sizes, and SHA-256 hashes used to support the calibration story."
        ),
        "calibration_sources": CALIBRATION_SOURCES,
        "pattern_library": PATTERN_LIBRARY,
        "provenance_note": (
            "Dataset-calibrated replay: motion, IMU, hydrophone, pressure, and flow "
            "behavior are calibrated from public underwater robot and acoustic datasets. "
            "Pipe geometry, tether, and event placement are modeled until PipeOwl hardware "
            "test-loop logs replace each stream."
        ),
        "mode_limitations": [
            "Constructed from prerecorded public/proxy datasets and a repeatable replay route",
            "No single public dataset contains hydrophone, IMU, tether, pipe intersections, and leak truth together",
            "Intersections are identified by network geometry plus IMU turn patterns",
        ],
        "pipe": {
            "material": "PVC",
            "diameter_mm": 100,
            "nominal_pressure_bar": 3.2,
            "nominal_flow_velocity_mps": 0.65,
        },
        "sonde": {
            "diameter_mm": 60,
            "sensors": ["hydrophone", "imu", "reel_encoder", "tether_tension"],
        },
        "truth": {
            "modeled_leak_distance_m": LEAK_DISTANCE_M,
            "modeled_impact_distance_m": IMPACT_DISTANCE_M,
            "mapped_intersections_m": [15.0, 30.0, 47.0],
        },
    }
    with (out_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")


def write_network(out_dir: Path) -> None:
    features: List[Dict] = []

    for pipe_id, start, end in list(ROUTE) + list(BRANCHES):
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": pipe_id,
                    "kind": "pipe",
                    "diameter_mm": 100 if pipe_id.startswith("MAIN") else 75,
                    "material": "PVC",
                    "length_m": segment_length(start, end),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start[0], start[1]], [end[0], end[1]]],
                },
            }
        )

    for node_id, distance_m in (
        ("J001", 15.0),
        ("J002", 30.0),
        ("J003", 47.0),
    ):
        pose = distance_to_pose(distance_m)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": node_id,
                    "kind": "intersection",
                    "distance_m": distance_m,
                    "degree": 3,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [pose["x_m"], pose["y_m"]],
                },
            }
        )

    network = {"type": "FeatureCollection", "features": features}
    with (out_dir / "network.geojson").open("w", encoding="utf-8") as handle:
        json.dump(network, handle, indent=2)
        handle.write("\n")


def generate_robot_state(duration_s: float, dt_s: float = 0.25) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    total_length = route_length()
    previous_distance = 0.0

    step_count = int(duration_s / dt_s) + 1
    for step in range(step_count):
        time_s = step * dt_s
        nominal_distance = min(total_length, time_s * 0.70)
        distance_m = nominal_distance
        speed = (distance_m - previous_distance) / dt_s if step else 0.0
        pose = distance_to_pose(distance_m)
        leak_nearby = abs(distance_m - LEAK_DISTANCE_M) < 2.6

        rows.append(
            {
                "time_s": round(time_s, 3),
                "distance_m": round(distance_m, 3),
                "x_m": round(float(pose["x_m"]), 3),
                "y_m": round(float(pose["y_m"]), 3),
                "heading_rad": round(float(pose["heading_rad"]), 5),
                "speed_mps": round(speed, 3),
                "pressure_bar": round(3.2 - (0.18 if leak_nearby else 0.0), 3),
                "flow_velocity_mps": round(0.65 + (0.16 if leak_nearby else 0.02 * math.sin(time_s / 8.0)), 3),
                "pipe_id": str(pose["pipe_id"]),
            }
        )
        previous_distance = distance_m

    return rows


def generate_imu(robot_state_rows: Sequence[Mapping[str, object]],
                 duration_s: float,
                 dt_s: float = 0.02) -> List[Dict[str, float]]:
    rng = random.Random(37)
    rows: List[Dict[str, float]] = []
    step_count = int(duration_s / dt_s) + 1

    for step in range(step_count):
        time_s = step * dt_s
        distance_m = interpolate_distance(robot_state_rows, time_s)
        bend_energy = (
            math.exp(-((distance_m - 30.0) ** 2) / 0.22)
            + 0.65 * math.exp(-((distance_m - 47.0) ** 2) / 0.30)
        )
        impact_energy = math.exp(-((distance_m - IMPACT_DISTANCE_M) ** 2) / 0.025)
        vibration = 0.07 * math.sin(time_s * 9.0) + 0.035 * math.sin(time_s * 17.0)

        ax = 0.05 * math.sin(time_s * 2.3) + vibration + impact_energy * 3.2 + rng.gauss(0.0, 0.015)
        ay = 0.04 * math.cos(time_s * 1.8) - impact_energy * 1.1 + rng.gauss(0.0, 0.014)
        az = 9.81 + 0.06 * math.sin(time_s * 3.1) + impact_energy * 2.5 + rng.gauss(0.0, 0.018)
        gx = 0.010 * math.sin(time_s * 1.2) + rng.gauss(0.0, 0.003)
        gy = 0.008 * math.cos(time_s * 1.7) + rng.gauss(0.0, 0.003)
        gz = 0.015 * math.sin(time_s * 1.9) + bend_energy * 0.48 + rng.gauss(0.0, 0.004)

        rows.append(
            {
                "time_s": round(time_s, 3),
                "distance_m": round(distance_m, 3),
                "ax_mps2": ax,
                "ay_mps2": ay,
                "az_mps2": az,
                "gx_radps": gx,
                "gy_radps": gy,
                "gz_radps": gz,
            }
        )

    return add_imu_features(rows)


def generate_reel(robot_state_rows: Sequence[Mapping[str, object]],
                  duration_s: float,
                  dt_s: float = 0.5) -> List[Dict[str, float]]:
    rng = random.Random(91)
    rows: List[Dict[str, float]] = []
    previous_length = 0.0
    step_count = int(duration_s / dt_s) + 1

    for step in range(step_count):
        time_s = step * dt_s
        distance_m = interpolate_distance(robot_state_rows, time_s)
        slip = 0.02 * distance_m + 0.015 * math.sin(time_s / 3.0)
        tether_length = max(0.0, distance_m + slip + rng.gauss(0.0, 0.006))
        payout_speed = (tether_length - previous_length) / dt_s if step else 0.0
        tension = 1.3 + 0.03 * distance_m + 0.08 * math.sin(time_s / 4.0)
        tension += 2.6 * math.exp(-((distance_m - IMPACT_DISTANCE_M) ** 2) / 0.22)
        tension += 1.1 * math.exp(-((distance_m - 58.0) ** 2) / 1.2)

        rows.append(
            {
                "time_s": round(time_s, 3),
                "distance_m": round(distance_m, 3),
                "tether_length_m": round(tether_length, 3),
                "payout_speed_mps": round(payout_speed, 3),
                "tether_tension_N": round(tension, 3),
            }
        )
        previous_length = tether_length

    return rows


def write_hydrophone(out_dir: Path,
                     robot_state_rows: Sequence[Mapping[str, object]],
                     duration_s: float,
                     sample_rate: int = 8000) -> None:
    rng = random.Random(1234)
    path = out_dir / "hydrophone.wav"
    total_samples = int(duration_s * sample_rate)
    frames = bytearray()

    for index in range(total_samples):
        time_s = index / sample_rate
        distance_m = interpolate_distance(robot_state_rows, time_s)
        leak_env = math.exp(-((distance_m - LEAK_DISTANCE_M) ** 2) / 2.5)
        impact_env = math.exp(-((distance_m - IMPACT_DISTANCE_M) ** 2) / 0.015)
        pump = 0.012 * math.sin(2.0 * math.pi * 180.0 * time_s)
        low_flow = 0.010 * math.sin(2.0 * math.pi * 430.0 * time_s + 0.4)
        hydro_noise = rng.gauss(0.0, 0.012)
        leak_hiss = leak_env * (
            0.070 * math.sin(2.0 * math.pi * 2800.0 * time_s)
            + 0.052 * math.sin(2.0 * math.pi * 3400.0 * time_s + 0.7)
            + rng.gauss(0.0, 0.035)
        )
        impact_click = impact_env * rng.gauss(0.0, 0.45)
        sample = pump + low_flow + hydro_noise + leak_hiss + impact_click
        sample_int = int(max(-1.0, min(1.0, sample)) * 32767)
        frames.extend(sample_int.to_bytes(2, "little", signed=True))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


def row_window(rows: Iterable[Mapping[str, object]],
               time_field: str,
               start_s: float,
               end_s: float) -> List[Mapping[str, object]]:
    return [
        row
        for row in rows
        if start_s <= float(row[time_field]) <= end_s
    ]


def create_events(robot_state_rows: Sequence[Mapping[str, object]],
                  imu_rows: Sequence[Mapping[str, object]],
                  reel_rows: Sequence[Mapping[str, object]],
                  acoustic_rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []

    def append_event(event_id: str,
                     event_type: str,
                     time_s: float,
                     distance_m: float,
                     confidence: float,
                     source: str,
                     notes: str) -> None:
        pose = distance_to_pose(distance_m)
        events.append(
            {
                "event_id": event_id,
                "type": event_type,
                "time_s": round(time_s, 2),
                "distance_m": round(distance_m, 2),
                "x_m": round(float(pose["x_m"]), 2),
                "y_m": round(float(pose["y_m"]), 2),
                "confidence": round(confidence, 2),
                "source": source,
                "notes": notes,
            }
        )

    for index, distance_m in enumerate((15.0, 30.0, 47.0), start=1):
        append_event(
            f"E{index:03d}",
            "intersection",
            distance_to_time(distance_m),
            distance_m,
            0.95,
            "network_geometry",
            (
                f"{PATTERN_LIBRARY['intersection']['evidence']}. "
                f"Source: {PATTERN_LIBRARY['intersection']['source']}. "
                "Proof IDs: WNTR_NET3_INP, SUBPIPE_README, AQUALOC_PAGE"
            ),
        )

    impact_time = distance_to_time(IMPACT_DISTANCE_M)
    append_event(
        "E004",
        "possible_impact",
        impact_time,
        IMPACT_DISTANCE_M,
        0.78,
        "imu_reel_fusion",
        (
            f"{PATTERN_LIBRARY['impact']['evidence']}. "
            f"Source: {PATTERN_LIBRARY['impact']['source']}. "
            "Proof IDs: SUBPIPE_README, SUBPIPE_ZENODO, AQUALOC_PAGE"
        ),
    )

    leak_candidates = sorted(
        [
            row
            for row in acoustic_rows
            if float(row["leak_score"]) > 0.64
        ],
        key=lambda row: float(row["leak_score"]),
        reverse=True,
    )
    for best in leak_candidates:
        start_s = float(best["window_start_s"])
        end_s = float(best["window_end_s"])
        imu_window = row_window(imu_rows, "time_s", start_s - 0.5, end_s + 0.5)
        reel_window = row_window(reel_rows, "time_s", start_s - 0.5, end_s + 0.5)
        max_accel = max((float(row["accel_mag"]) for row in imu_window), default=9.81)
        max_tension = max((float(row["tether_tension_N"]) for row in reel_window), default=0.0)
        confidence = float(best["leak_score"])
        if max_accel < 13.0 and max_tension < 4.5:
            append_event(
                "E005",
                "possible_leak",
                start_s,
                float(best["distance_m"]),
                confidence,
                "hydrophone_hydraulic_fusion",
                (
                    f"{PATTERN_LIBRARY['leak']['evidence']}. "
                    f"Source: {PATTERN_LIBRARY['leak']['source']}. "
                    "Proof IDs: GPLA12_DATA_V1, GPLA12_LABELS_V1, WNTR_LEAKS_INP"
                ),
            )
            break

    bend_distance = 30.0
    append_event(
        "E006",
        "possible_bend",
        distance_to_time(bend_distance),
        bend_distance,
        0.67,
        "imu_network_fusion",
        (
            f"{PATTERN_LIBRARY['intersection']['imu']}. "
            f"Source: {PATTERN_LIBRARY['intersection']['source']}. "
            "Proof IDs: WNTR_NET3_INP, SUBPIPE_README, AQUALOC_PAGE"
        ),
    )

    return sorted(events, key=lambda row: float(row["time_s"]))


def format_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    formatted: List[Dict[str, object]] = []
    for row in rows:
        out: Dict[str, object] = {}
        for key, value in row.items():
            if isinstance(value, float):
                if abs(value) >= 100:
                    out[key] = f"{value:.2f}"
                else:
                    out[key] = f"{value:.5f}".rstrip("0").rstrip(".")
            else:
                out[key] = value
        formatted.append(out)
    return formatted


def build_calibrated_mission(out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    duration_s = 92.0
    write_metadata(out_dir)
    write_network(out_dir)

    robot_state_rows = generate_robot_state(duration_s)
    imu_rows = generate_imu(robot_state_rows, duration_s)
    reel_rows = generate_reel(robot_state_rows, duration_s)
    write_hydrophone(out_dir, robot_state_rows, duration_s)
    acoustic_rows = extract_acoustic_features(out_dir / "hydrophone.wav", robot_state_rows)
    event_rows = create_events(robot_state_rows, imu_rows, reel_rows, acoustic_rows)

    write_csv(out_dir / "robot_state.csv", format_rows(robot_state_rows), REQUIRED_COLUMNS["robot_state.csv"])
    write_csv(out_dir / "imu.csv", format_rows(imu_rows), REQUIRED_COLUMNS["imu.csv"])
    write_csv(out_dir / "reel.csv", format_rows(reel_rows), REQUIRED_COLUMNS["reel.csv"])
    write_csv(
        out_dir / "acoustic_features.csv",
        format_rows(acoustic_rows),
        REQUIRED_COLUMNS["acoustic_features.csv"],
    )
    write_csv(out_dir / "events.csv", format_rows(event_rows), REQUIRED_COLUMNS["events.csv"])
    write_mission_source_manifest(out_dir)
