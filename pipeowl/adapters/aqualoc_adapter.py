"""AQUALOC adapter placeholder.

AQUALOC should map synchronized ROV camera/IMU/pressure logs into PipeOwl
imu.csv and robot_state.csv. ROS bag extraction is intentionally kept outside
this pure-Python MVP because real bag parsing needs ROS or rosbags tooling.
"""

from pathlib import Path

from .base import AdapterResult, DatasetAdapter


class AqualocAdapter(DatasetAdapter):
    name = "AQUALOC"

    def convert(self, input_dir: Path, output_dir: Path) -> AdapterResult:
        raise NotImplementedError(
            "AQUALOC conversion requires ROS/raw log extraction. "
            "Expected outputs: imu.csv, robot_state.csv, reel.csv with synthetic tether."
        )
