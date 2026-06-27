# PipeOwl Hardware Log Format

This is the format for real PipeOwl bench or test-loop recordings.

The current public demo is dataset-calibrated. To run the dashboard from real PipeOwl data, record a raw mission folder with the files below, then import it into the canonical mission format.

## Raw Folder

```text
raw_mission_001/
  metadata.json        optional but recommended
  imu.csv              required
  reel.csv             required
  hydrophone.wav       required, 16-bit PCM WAV
  network.geojson      optional surveyed/test-loop geometry
```

## Required `imu.csv`

```csv
time_s,ax_mps2,ay_mps2,az_mps2,gx_radps,gy_radps,gz_radps
0.00,0.02,-0.01,9.81,0.001,0.002,0.000
0.02,0.03,-0.01,9.80,0.001,0.002,0.001
```

Optional `distance_m` may be included. If it is missing, the importer maps IMU rows to distance using `reel.csv`.

## Required `reel.csv`

```csv
time_s,tether_length_m,tether_tension_N
0.0,0.00,1.2
1.0,0.68,1.4
2.0,1.39,1.5
```

Optional columns:

```text
distance_m
payout_speed_mps
```

If `distance_m` is missing, `tether_length_m` is used as the distance estimate.

## Required `hydrophone.wav`

Use a mono or stereo 16-bit PCM WAV file. The importer reads the file, converts it to mono if needed, and extracts:

```text
RMS
peak amplitude
bandpower
spectral centroid
leak score
```

## Optional `metadata.json`

```json
{
  "mission_id": "bench_test_001",
  "mission_name": "Bench Test 001",
  "pipe_material": "clear_pvc",
  "pipe_diameter_mm": 100,
  "nominal_pressure_bar": 1.2,
  "nominal_flow_velocity_mps": 0.2,
  "sonde_diameter_mm": 60
}
```

## Optional `network.geojson`

If supplied, this should describe the surveyed test-loop route. If missing, the importer creates a straight test pipe from `0 m` to the final reel distance.

## Import Command

```sh
python3 scripts/import_hardware_mission.py \
  --raw data/raw_missions/bench_test_001 \
  --out data/real_mission
```

Run the dashboard on the imported real mission:

```sh
PIPEOWL_MISSION_DIR=data/real_mission ./run_local.sh
```

## What This Proves

The imported mission writes `source_manifest.json` with SHA-256 hashes for the raw IMU, reel, hydrophone, metadata, and geometry files. That proves the dashboard is running from a specific local hardware recording, not from the dataset-calibrated replay.

The remaining scientific claim still depends on ground truth. For leak accuracy, record a controlled test-loop run where the leak location and leak state are known.
