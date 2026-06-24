from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from pipeowl import build_demo_mission, validate_mission


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class PipeOwlMissionTests(unittest.TestCase):
    def test_demo_mission_validates_and_contains_expected_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            mission_dir = Path(temp_dir) / "mission"
            build_demo_mission(mission_dir)

            errors = validate_mission(mission_dir)
            self.assertEqual(errors, [])

            events = read_csv(mission_dir / "events.csv")
            event_types = {row["type"] for row in events}
            self.assertIn("possible_leak", event_types)
            self.assertIn("intersection", event_types)
            self.assertIn("possible_impact", event_types)

            acoustic = read_csv(mission_dir / "acoustic_features.csv")
            max_leak_score = max(float(row["leak_score"]) for row in acoustic)
            self.assertGreater(max_leak_score, 0.72)

            leak_events = [row for row in events if row["type"] == "possible_leak"]
            self.assertTrue(any(43.0 <= float(row["distance_m"]) <= 50.0 for row in leak_events))

    def test_validation_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = validate_mission(Path(temp_dir))
            self.assertIn("missing required file: metadata.json", errors)


if __name__ == "__main__":
    unittest.main()
