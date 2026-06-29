"""Dataset notes used by the PipeOwl replay generator."""

from __future__ import annotations

from typing import Dict, List


CALIBRATION_SOURCES: List[Dict[str, str]] = [
    {
        "stream": "motion_imu",
        "source": "SubPipe public underwater pipeline-inspection dataset",
        "use": "navigation vibration, acceleration scale, turn/gyro events, pressure/flow context",
        "url": "https://github.com/remaro-network/SubPipe-dataset",
    },
    {
        "stream": "motion_imu_pressure",
        "source": "AQUALOC public underwater ROV localization dataset",
        "use": "underwater IMU and pressure timing patterns",
        "url": "https://www.lirmm.fr/aqualoc/",
    },
    {
        "stream": "acoustic_leak",
        "source": "GPLA-12 public pipeline acoustic leakage dataset",
        "use": "pipeline-leak broadband/high-frequency acoustic scoring workflow",
        "url": "https://arxiv.org/abs/2106.10277",
    },
    {
        "stream": "acoustic_background",
        "source": "OceanShip public underwater audio dataset",
        "use": "hydrophone-style background and false-positive noise profile",
        "url": "https://arxiv.org/abs/2401.02099",
    },
    {
        "stream": "pipe_network",
        "source": "WNTR/EPANET-style water-network model",
        "use": "pipe graph, intersections, pressure/flow context, leak scenario placement",
        "url": "https://usepa.github.io/WNTR/",
    },
]


PATTERN_LIBRARY: Dict[str, Dict[str, object]] = {
    "steady_travel": {
        "source": "SubPipe/AQUALOC motion calibration",
        "imu": "low-amplitude vibration around gravity with small gyro drift",
        "evidence": "accel_mag stable, gyro_mag low, forward distance increasing",
    },
    "intersection": {
        "source": "WNTR network node + SubPipe/AQUALOC turn calibration",
        "imu": "gyro_z rise and heading change near a mapped branch node",
        "acoustic": "optional short flow disturbance; not treated as proof by itself",
        "evidence": "known pipe graph node plus IMU turn pattern",
    },
    "impact": {
        "source": "SubPipe/AQUALOC acceleration spike calibration",
        "imu": "short acceleration and jerk spike",
        "acoustic": "brief broadband click",
        "evidence": "acceleration spike plus tether tension rise",
    },
    "leak": {
        "source": "GPLA-12 acoustic leakage calibration + WNTR pressure/flow context",
        "acoustic": "raised RMS with stronger high-frequency bandpower and sustained leak score",
        "hydraulic": "local pressure dip and flow increase in the pipe model",
        "evidence": "high acoustic leak score, pressure/flow anomaly, no impact/tether artifact",
    },
    "tether": {
        "source": "PipeOwl MVP reel model",
        "reel": "tether tension and payout speed used to reject false leak positives",
        "evidence": "tension spike without matching sustained acoustic leak signature",
    },
}
