from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
import wave
from pathlib import Path

from pipeowl import build_calibrated_mission, build_hardware_mission, validate_mission


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_test_wav(path: Path, duration_s: float = 2.0, sample_rate: int = 8000):
    frames = bytearray()
    for index in range(int(duration_s * sample_rate)):
        time_s = index / sample_rate
        sample = 0.02 * math.sin(2.0 * math.pi * 440.0 * time_s)
        frames.extend(int(sample * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))


class PipeOwlMissionTests(unittest.TestCase):
    def test_calibrated_mission_validates_and_contains_expected_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mission_dir = Path(temp_dir) / "mission"
            build_calibrated_mission(mission_dir)

            errors = validate_mission(mission_dir)
            self.assertEqual(errors, [])

            events = read_csv(mission_dir / "events.csv")
            event_types = {row["type"] for row in events}
            self.assertIn("possible_leak", event_types)
            self.assertIn("intersection", event_types)
            self.assertIn("possible_impact", event_types)
            self.assertTrue(all(row["evidence"] for row in events))

            acoustic = read_csv(mission_dir / "acoustic_features.csv")
            max_leak_score = max(float(row["leak_score"]) for row in acoustic)
            self.assertGreater(max_leak_score, 0.72)

            leak_events = [row for row in events if row["type"] == "possible_leak"]
            self.assertTrue(any(43.0 <= float(row["distance_m"]) <= 50.0 for row in leak_events))
            self.assertTrue(any("Leak score" in row["evidence"] for row in leak_events))

            metadata = (mission_dir / "metadata.json").read_text(encoding="utf-8")
            self.assertIn("dataset_calibrated", metadata)
            self.assertIn("SubPipe", metadata)
            self.assertIn("GPLA-12", metadata)
            self.assertIn("source_manifest.json", metadata)

            source_manifest = json.loads((mission_dir / "source_manifest.json").read_text(encoding="utf-8"))
            artifact_ids = {artifact["id"] for artifact in source_manifest["artifacts"]}
            self.assertIn("GPLA12_DATA_V1", artifact_ids)
            self.assertIn("SUBPIPE_ZENODO", artifact_ids)
            self.assertIn("WNTR_NET3_INP", artifact_ids)
            self.assertEqual(source_manifest["evidence_summary"]["gpla12"]["label_rows"], 684)

    def test_validation_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = validate_mission(Path(temp_dir))
            self.assertIn("missing required file: metadata.json", errors)

    def test_hardware_importer_builds_real_log_mission(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_dir = root / "raw"
            mission_dir = root / "real_mission"
            raw_dir.mkdir()
            (raw_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "mission_id": "bench_test_001",
                        "mission_name": "Bench Test 001",
                        "nominal_pressure_bar": 1.2,
                        "nominal_flow_velocity_mps": 0.2,
                    }
                ),
                encoding="utf-8",
            )
            (raw_dir / "imu.csv").write_text(
                "\n".join(
                    [
                        "time_s,ax_mps2,ay_mps2,az_mps2,gx_radps,gy_radps,gz_radps",
                        "10.0,0.0,0.0,9.81,0.0,0.0,0.0",
                        "11.0,0.1,0.0,9.82,0.0,0.0,0.01",
                        "12.0,0.0,0.1,9.80,0.0,0.0,0.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (raw_dir / "reel.csv").write_text(
                "\n".join(
                    [
                        "time_s,tether_length_m,tether_tension_N",
                        "10.0,0.0,1.1",
                        "11.0,0.6,1.2",
                        "12.0,1.2,1.3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            write_test_wav(raw_dir / "hydrophone.wav")

            build_hardware_mission(raw_dir, mission_dir)

            self.assertEqual(validate_mission(mission_dir), [])
            metadata = json.loads((mission_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["replay_mode"], "hardware_import")
            source_manifest = json.loads((mission_dir / "source_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(source_manifest["evidence_summary"]["hardware"]["imu_rows"], 3)
            self.assertEqual(source_manifest["evidence_summary"]["hardware"]["reel_rows"], 3)
            self.assertTrue(
                all(artifact["sha256"] for artifact in source_manifest["artifacts"])
            )


if __name__ == "__main__":
    unittest.main()
