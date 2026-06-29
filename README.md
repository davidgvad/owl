# PipeOwl Pipe Robot Demo

This repo is a local demo for a small water-pipe inspection robot idea.

The demo shows a robot moving through a pipe route. As it moves, the page shows
simple sensor readings and records important points such as intersections, a
bump/tether tug, and a possible leak signal.

## Run The Demo

```sh
./run_local.sh
```

Then open:

```text
http://127.0.0.1:8501
```

Press **Start** on the page.

## What The Demo Uses

The current mission is not from our own robot yet. It is a replay built from:

- GPLA-12 acoustic leak data, used for leak-like sound patterns
- SubPipe and AQUALOC references, used for underwater robot IMU behavior
- WNTR/EPANET files, used for pipe network and intersection structure
- A small modeled route, tether, and robot path so the demo is repeatable

The source files are stored in `data/source_artifacts/`. The replay itself is
stored in `data/calibrated_mission/`.

## Regenerate The Mission

```sh
python3 scripts/generate_calibrated_mission.py --out data/calibrated_mission
python3 scripts/validate_mission.py data/calibrated_mission
```

## Main Files

- `app_streamlit.py`: local dashboard
- `pipeowl/mission_builder.py`: builds the demo mission
- `pipeowl/features.py`: calculates IMU and audio features
- `pipeowl/schemas.py`: checks the mission files
- `pipeowl/provenance.py`: records source file hashes
- `data/calibrated_mission/`: mission files used by the dashboard
- `data/source_artifacts/`: public dataset/source files used for calibration
- `include/` and `src/`: small C++ controller prototype

## Mission Files

The dashboard reads:

```text
metadata.json
network.geojson
robot_state.csv
imu.csv
reel.csv
hydrophone.wav
acoustic_features.csv
events.csv
source_manifest.json
```

`events.csv` includes the event type, distance, and the sensor values that made
the event important. For example, a leak event records leak score, pressure
change, flow change, acceleration check, and tether tension check.

## C++ Prototype

The C++ code is separate from the Streamlit demo.

```sh
cmake -S . -B build
cmake --build build
./build/owl_sim
```

## Current Limit

This is a dataset-backed simulation, not a finished robot product. The next real
step is to collect logs from a bench test or clear test pipe and replace the
modeled streams with our own recorded IMU, reel, and hydrophone data.
