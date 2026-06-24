# PipeOwl Mission Replay + Analytics Framework

PipeOwl is a mission replay and analytics framework for a water-pipe inspection sonde.

## Run Locally

No deployment is needed. Start the local dashboard with:

```sh
./run_local.sh
```

Or:

```sh
make run
```

Then open:

```text
http://127.0.0.1:8501
```

The honest MVP story is:

> Our robot will produce hydrophone, IMU, tether/reel, and pipe metadata logs. Before the hardware is ready, this repo builds the analysis layer using a canonical mission format, trusted public proxy datasets, and synthetic mission generation.

The framework converts all sources into the same mission directory shape:

```text
mission_001/
  metadata.json
  network.geojson
  robot_state.csv
  imu.csv
  reel.csv
  hydrophone.wav
  acoustic_features.csv
  events.csv
```

## Generate The Sample Mission

The generator uses only the Python standard library.

```sh
python3 scripts/generate_demo_mission.py --out data/demo_mission
python3 scripts/validate_mission.py data/demo_mission
```

It creates a synthetic pipe route with intersections, robot motion, IMU vibration/turn events, tether payout/tension, hydrophone audio with a leak-like event, acoustic features, and fused event cards.

## Run Tests

```sh
PYTHONPYCACHEPREFIX=/private/tmp/owl_pycache python3 -m unittest tests.pipeowl_tests
```

## Run The Dashboard

Install the optional app dependencies, then run Streamlit.

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/generate_demo_mission.py --out data/demo_mission
streamlit run app_streamlit.py
```

The dashboard shows a pipe map, replay position, leak score, acoustic bands, IMU timeline, tether timeline, event list, provenance panel, and downloadable mission JSON.

## Dataset Strategy

PipeOwl should not be built around one dataset. Build around the canonical PipeOwl mission format, then add adapters.

- SubPipe: primary public proxy for robot IMU/navigation-style data
- AQUALOC: backup underwater IMU/pressure/localization source
- GPLA-12: acoustic pipeline leak classifier proxy
- Water-network acoustic leak literature: methodology reference
- OceanShip: hydrophone-like underwater background noise
- WNTR/EPANET: synthetic pipe graph, pressure/flow context, intersections, leak scenarios

Current adapter status:

- `scripts/subpipe_adapter.py`: partial SubPipe CSV converter for IMU, robot state, synthetic reel, metadata, and route trace
- `pipeowl/adapters/*`: extension points for AQUALOC, GPLA-12, OceanShip, and WNTR/EPANET

## C++ Robot Controller Prototype

The repo also includes the original C++ controller prototype for eventual robot behavior logic. It is separate from the Python analytics layer.

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build
```

Run the robot controller simulator:

```sh
./build/owl_sim
```

## Project Layout

- `pipeowl/schemas.py`: canonical mission schema and validator
- `pipeowl/features.py`: IMU and acoustic feature extraction
- `pipeowl/mission_builder.py`: deterministic synthetic sample mission generator
- `pipeowl/adapters/`: public dataset adapter skeletons
- `scripts/generate_demo_mission.py`: creates `data/demo_mission`
- `app_streamlit.py`: mission replay dashboard
- `include/`, `src/`: C++ robot controller prototype
- `docs/`: mission format, dataset plan, design, safety, and walkthrough

## What Not To Claim

Do not claim this is real PipeOwl robot data or real Braila leak detection. The current sample is proxy plus synthetic mission replay. The next milestone is replacing proxy streams with low-pressure test-loop data from the MVP sonde.

The first milestone should be dry bench testing, then a clear test pipe, then clean-water testing. Real municipal, storm, or wastewater use needs proper sanitation, electrical isolation, retrieval planning, and permission from the pipe owner.
