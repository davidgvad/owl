"""Feature extraction for PipeOwl mission streams.

This module intentionally uses only Python's standard library so calibrated
missions can be generated and validated before optional dashboard dependencies
are installed.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def accel_magnitude(ax: float, ay: float, az: float) -> float:
    return math.sqrt(ax * ax + ay * ay + az * az)


def gyro_magnitude(gx: float, gy: float, gz: float) -> float:
    return math.sqrt(gx * gx + gy * gy + gz * gz)


def add_imu_features(rows: Sequence[Mapping[str, float]]) -> List[Dict[str, float]]:
    featured: List[Dict[str, float]] = []
    previous_time = None
    previous_accel = None

    for row in rows:
        out = dict(row)
        accel = accel_magnitude(out["ax_mps2"], out["ay_mps2"], out["az_mps2"])
        gyro = gyro_magnitude(out["gx_radps"], out["gy_radps"], out["gz_radps"])
        if previous_time is None or previous_accel is None:
            jerk = 0.0
        else:
            dt = max(1e-6, out["time_s"] - previous_time)
            jerk = (accel - previous_accel) / dt

        out["accel_mag"] = accel
        out["gyro_mag"] = gyro
        out["jerk"] = jerk
        featured.append(out)
        previous_time = out["time_s"]
        previous_accel = accel

    return featured


def interpolate_distance(robot_state_rows: Sequence[Mapping[str, float]], time_s: float) -> float:
    if not robot_state_rows:
        return 0.0

    if time_s <= robot_state_rows[0]["time_s"]:
        return robot_state_rows[0]["distance_m"]

    for previous, current in zip(robot_state_rows, robot_state_rows[1:]):
        if previous["time_s"] <= time_s <= current["time_s"]:
            span = max(1e-6, current["time_s"] - previous["time_s"])
            ratio = (time_s - previous["time_s"]) / span
            return previous["distance_m"] + ratio * (
                current["distance_m"] - previous["distance_m"]
            )

    return robot_state_rows[-1]["distance_m"]


def read_wav_mono(path: Path) -> Tuple[int, List[float]]:
    """Read a 16-bit PCM WAV file as mono float samples in -1..1."""

    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())

    if width != 2:
        raise ValueError("only 16-bit PCM WAV files are supported")

    samples: List[float] = []
    step = width * channels
    for index in range(0, len(frames), step):
        channel_values = []
        for channel in range(channels):
            offset = index + channel * width
            value = int.from_bytes(frames[offset : offset + width], "little", signed=True)
            channel_values.append(value / 32768.0)
        samples.append(sum(channel_values) / len(channel_values))

    return sample_rate, samples


def goertzel_power(samples: Sequence[float], sample_rate: int, frequency_hz: float) -> float:
    """Estimate signal power near one frequency using the Goertzel algorithm."""

    if not samples:
        return 0.0

    n = len(samples)
    k = int(0.5 + (n * frequency_hz) / sample_rate)
    omega = (2.0 * math.pi * k) / n
    coeff = 2.0 * math.cos(omega)
    s_prev = 0.0
    s_prev2 = 0.0

    for sample in samples:
        s = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s

    power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
    return power / max(1, n)


def bandpower(samples: Sequence[float],
              sample_rate: int,
              frequencies_hz: Sequence[float]) -> float:
    usable = [freq for freq in frequencies_hz if freq < sample_rate * 0.48]
    if not usable:
        return 0.0
    return sum(goertzel_power(samples, sample_rate, freq) for freq in usable) / len(usable)


def spectral_centroid_sparse(samples: Sequence[float], sample_rate: int) -> float:
    frequencies = (120.0, 250.0, 400.0, 700.0, 1100.0, 1700.0, 2400.0, 3200.0)
    powers = [
        (freq, goertzel_power(samples, sample_rate, freq))
        for freq in frequencies
        if freq < sample_rate * 0.48
    ]
    total = sum(power for _, power in powers)
    if total <= 1e-12:
        return 0.0
    return sum(freq * power for freq, power in powers) / total


def acoustic_leak_score(rms: float,
                        peak: float,
                        low_band: float,
                        mid_band: float,
                        high_band: float,
                        centroid_hz: float) -> float:
    """Simple explainable leak score for demo analytics.

    The score favors steady energy, high-frequency bandpower, and a raised
    spectral centroid while limiting pure impact clicks.
    """

    total_band = low_band + mid_band + high_band + 1e-9
    high_ratio = high_band / total_band
    mid_ratio = mid_band / total_band
    energy_score = clamp((rms - 0.012) / 0.055, 0.0, 1.0)
    peak_score = clamp((peak - 0.05) / 0.35, 0.0, 1.0)
    centroid_score = clamp((centroid_hz - 900.0) / 2200.0, 0.0, 1.0)
    leak_like_band = clamp((high_ratio * 0.65 + mid_ratio * 0.35 - 0.22) / 0.38, 0.0, 1.0)
    absolute_band = clamp(((mid_band + high_band) - 0.0010) / 0.0045, 0.0, 1.0)
    impulse_penalty = clamp((peak - rms * 3.5 - 0.05) / 0.45, 0.0, 0.45)
    raw = (
        0.34 * energy_score
        + 0.12 * peak_score
        + 0.18 * leak_like_band
        + 0.26 * absolute_band
        + 0.10 * centroid_score
    )
    return clamp(raw - impulse_penalty, 0.0, 1.0)


def extract_acoustic_features(wav_path: Path,
                              robot_state_rows: Sequence[Mapping[str, float]],
                              window_seconds: float = 1.0) -> List[Dict[str, float]]:
    sample_rate, samples = read_wav_mono(wav_path)
    window_size = max(1, int(sample_rate * window_seconds))
    rows: List[Dict[str, float]] = []

    for start_index in range(0, len(samples), window_size):
        window = samples[start_index : start_index + window_size]
        if len(window) < window_size * 0.50:
            continue

        start_s = start_index / sample_rate
        end_s = (start_index + len(window)) / sample_rate
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        peak = max(abs(sample) for sample in window)
        low = bandpower(window, sample_rate, (125.0, 250.0, 400.0))
        mid = bandpower(window, sample_rate, (650.0, 1000.0, 1600.0))
        high = bandpower(window, sample_rate, (2200.0, 2800.0, 3400.0))
        centroid = spectral_centroid_sparse(window, sample_rate)
        score = acoustic_leak_score(rms, peak, low, mid, high, centroid)

        rows.append(
            {
                "window_start_s": start_s,
                "window_end_s": end_s,
                "distance_m": interpolate_distance(robot_state_rows, (start_s + end_s) * 0.5),
                "rms": rms,
                "peak": peak,
                "bandpower_100_500": low,
                "bandpower_500_2000": mid,
                "bandpower_2000_10000": high,
                "spectral_centroid_hz": centroid,
                "leak_score": score,
            }
        )

    return rows


def max_in_time_window(rows: Iterable[Mapping[str, float]],
                       field: str,
                       start_s: float,
                       end_s: float) -> float:
    values = [
        float(row[field])
        for row in rows
        if start_s <= float(row["time_s"]) <= end_s and field in row
    ]
    return max(values) if values else 0.0
