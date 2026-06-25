"""SubPipe adapter skeleton.

SubPipe is the first public dataset to target because its structure maps well to
PipeOwl's motion streams: acceleration, angular velocity, forward distance,
estimated state, pressure, temperature, and water velocity. This adapter handles
the canonical CSV side of that mapping and leaves image/sonar assets out of the
MVP mission format.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from pipeowl.features import add_imu_features
from pipeowl.schemas import REQUIRED_COLUMNS, write_csv

from .base import AdapterResult, DatasetAdapter


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def first_existing(input_dir: Path, names: Sequence[str]) -> Optional[Path]:
    for name in names:
        path = input_dir / name
        if path.exists():
            return path
    return None


def get_float(row: Mapping[str, str], candidates: Sequence[str], default: float = 0.0) -> float:
    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:
                continue
    return default


def get_text(row: Mapping[str, str], candidates: Sequence[str], default: str = "") -> str:
    lowered = {key.lower(): value for key, value in row.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value not in (None, ""):
            return value
    return default


class SubPipeAdapter(DatasetAdapter):
    name = "SubPipe"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        warnings: List[str] = []

        acceleration_path = first_existing(input_dir, ("Acceleration.csv", "acceleration.csv"))
        angular_path = first_existing(input_dir, ("AngularVelocity.csv", "angular_velocity.csv"))
        distance_path = first_existing(input_dir, ("ForwardDistance.csv", "forward_distance.csv"))
        state_path = first_existing(input_dir, ("EstimatedState.csv", "estimated_state.csv"))
        pressure_path = first_existing(input_dir, ("Pressure.csv", "pressure.csv"))
        flow_path = first_existing(input_dir, ("WaterVelocity.csv", "water_velocity.csv"))

        if not acceleration_path or not angular_path:
            raise FileNotFoundError("SubPipe input must include Acceleration.csv and AngularVelocity.csv")

        accel_rows = read_csv(acceleration_path)
        gyro_rows = read_csv(angular_path)
        distance_rows = read_csv(distance_path) if distance_path else []
        state_rows = read_csv(state_path) if state_path else []
        pressure_rows = read_csv(pressure_path) if pressure_path else []
        flow_rows = read_csv(flow_path) if flow_path else []

        if len(accel_rows) != len(gyro_rows):
            warnings.append("Acceleration and AngularVelocity row counts differ; rows were paired by index")

        imu_rows = []
        row_count = min(len(accel_rows), len(gyro_rows))
        for index in range(row_count):
            accel = accel_rows[index]
            gyro = gyro_rows[index]
            time_s = get_float(accel, ("time_s", "timestamp", "time", "t"), float(index) * 0.01)
            distance_m = get_float(
                distance_rows[index],
                ("distance_m", "forward_distance", "distance", "value"),
                0.0,
            ) if index < len(distance_rows) else 0.0
            imu_rows.append(
                {
                    "time_s": time_s,
                    "distance_m": distance_m,
                    "ax_mps2": get_float(accel, ("ax_mps2", "ax", "x")),
                    "ay_mps2": get_float(accel, ("ay_mps2", "ay", "y")),
                    "az_mps2": get_float(accel, ("az_mps2", "az", "z"), 9.81),
                    "gx_radps": get_float(gyro, ("gx_radps", "gx", "x")),
                    "gy_radps": get_float(gyro, ("gy_radps", "gy", "y")),
                    "gz_radps": get_float(gyro, ("gz_radps", "gz", "z")),
                }
            )

        imu_rows = add_imu_features(imu_rows)
        robot_rows = self._build_robot_state(state_rows, pressure_rows, flow_rows, imu_rows)
        reel_rows = self._build_synthetic_reel(robot_rows)

        self._write_metadata(output_dir)
        self._write_placeholder_network(output_dir, robot_rows)
        write_csv(output_dir / "imu.csv", self._format_rows(imu_rows), REQUIRED_COLUMNS["imu.csv"])
        write_csv(output_dir / "robot_state.csv", self._format_rows(robot_rows), REQUIRED_COLUMNS["robot_state.csv"])
        write_csv(output_dir / "reel.csv", self._format_rows(reel_rows), REQUIRED_COLUMNS["reel.csv"])

        warnings.append("Hydrophone and acoustic_features are not produced by SubPipe and must be fused separately")
        warnings.append("events.csv is intentionally not synthesized by this adapter")
        return AdapterResult(output_dir=output_dir, warnings=warnings)

    def _build_robot_state(self,
                           state_rows: Sequence[Mapping[str, str]],
                           pressure_rows: Sequence[Mapping[str, str]],
                           flow_rows: Sequence[Mapping[str, str]],
                           imu_rows: Sequence[Mapping[str, float]]) -> List[Dict[str, object]]:
        robot_rows: List[Dict[str, object]] = []
        count = len(state_rows) if state_rows else len(imu_rows)
        for index in range(count):
            source = state_rows[index] if index < len(state_rows) else {}
            imu = imu_rows[min(index, len(imu_rows) - 1)]
            pressure = pressure_rows[index] if index < len(pressure_rows) else {}
            flow = flow_rows[index] if index < len(flow_rows) else {}
            x = get_float(source, ("x_m", "x", "north", "lat"), float(index) * 0.05)
            y = get_float(source, ("y_m", "y", "east", "lon"), 0.0)
            previous = robot_rows[-1] if robot_rows else None
            if previous:
                heading = math.atan2(y - float(previous["y_m"]), x - float(previous["x_m"]))
                dt = max(1e-6, float(imu["time_s"]) - float(previous["time_s"]))
                speed = (float(imu["distance_m"]) - float(previous["distance_m"])) / dt
            else:
                heading = 0.0
                speed = 0.0

            robot_rows.append(
                {
                    "time_s": float(imu["time_s"]),
                    "distance_m": float(imu["distance_m"]),
                    "x_m": x,
                    "y_m": y,
                    "heading_rad": heading,
                    "speed_mps": speed,
                    "pressure_bar": get_float(pressure, ("pressure_bar", "pressure", "value"), 0.0),
                    "flow_velocity_mps": get_float(flow, ("flow_velocity_mps", "velocity", "value"), 0.0),
                    "pipe_id": get_text(source, ("pipe_id", "pipe", "segment"), "SUBPIPE_ROUTE"),
                }
            )
        return robot_rows

    def _build_synthetic_reel(self, robot_rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
        reel_rows: List[Dict[str, object]] = []
        previous_length = 0.0
        previous_time = None
        for row in robot_rows:
            time_s = float(row["time_s"])
            distance_m = float(row["distance_m"])
            tether_length = distance_m * 1.02
            dt = max(1e-6, time_s - previous_time) if previous_time is not None else 0.0
            payout_speed = (tether_length - previous_length) / dt if dt else 0.0
            reel_rows.append(
                {
                    "time_s": time_s,
                    "distance_m": distance_m,
                    "tether_length_m": tether_length,
                    "payout_speed_mps": payout_speed,
                    "tether_tension_N": 1.2 + 0.02 * distance_m,
                }
            )
            previous_length = tether_length
            previous_time = time_s
        return reel_rows

    def _write_metadata(self, output_dir: Path) -> None:
        metadata = {
            "mission_id": "subpipe_converted",
            "data_sources": ["SubPipe public dataset", "PipeOwl synthetic reel mapping"],
            "provenance_note": "Converted public underwater robot calibration data, not real PipeOwl in-pipe mission data.",
            "pipe": {
                "material": "unknown",
                "diameter_mm": 0,
                "nominal_pressure_bar": 0.0,
                "nominal_flow_velocity_mps": 0.0,
            },
            "sonde": {
                "diameter_mm": 60,
                "sensors": ["imu", "pressure", "water_velocity", "synthetic_reel"],
            },
        }
        with (output_dir / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
            handle.write("\n")

    def _write_placeholder_network(self,
                                   output_dir: Path,
                                   robot_rows: Sequence[Mapping[str, object]]) -> None:
        coordinates = [
            [float(row["x_m"]), float(row["y_m"])]
            for row in robot_rows[:: max(1, len(robot_rows) // 300)]
        ]
        network = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "SUBPIPE_ROUTE", "kind": "route_trace"},
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            ],
        }
        with (output_dir / "network.geojson").open("w", encoding="utf-8") as handle:
            json.dump(network, handle, indent=2)
            handle.write("\n")

    def _format_rows(self, rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
        formatted: List[Dict[str, object]] = []
        for row in rows:
            formatted.append(
                {
                    key: f"{value:.6f}".rstrip("0").rstrip(".") if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )
        return formatted
