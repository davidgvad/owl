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

Press **Start** in the page to run the pipe robot simulation. The robot moves through the pipe network, and the right-side data panel updates when it reaches intersections, a bump/tether tug, and the leak-signal area.

The current demo story is:

> The demo is constructed from prerecorded public datasets and water-network artifacts. GPLA-12 supports acoustic leak-like features, SubPipe/AQUALOC support underwater robot motion assumptions, and WNTR/EPANET supports pipe-network geometry. Everything is converted into the same canonical PipeOwl mission format.

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
  source_manifest.json
```

## Generate The Dataset-Calibrated Replay

The generator uses only the Python standard library.

```sh
python3 scripts/generate_calibrated_mission.py --out data/calibrated_mission
python3 scripts/validate_mission.py data/calibrated_mission
```

It creates a modeled pipe route with intersections, robot motion, IMU vibration/turn events, tether payout/tension, hydrophone audio calibrated from public acoustic patterns, acoustic features, and fused event cards.

## Run From Real PipeOwl Logs

Once hardware or a bench test loop records real logs, import the raw folder:

```sh
python3 scripts/import_hardware_mission.py \
  --raw data/raw_missions/bench_test_001 \
  --out data/real_mission
```

Then run the same dashboard on the imported real mission:

```sh
PIPEOWL_MISSION_DIR=data/real_mission ./run_local.sh
```

The raw folder must contain `imu.csv`, `reel.csv`, and `hydrophone.wav`. See `docs/hardware_log_format.md` for the exact columns. The importer writes a `source_manifest.json` with SHA-256 hashes for the raw files, so the app can prove it is running from a specific local PipeOwl recording.

## Source Proof Bundle

The repo includes small, auditable public-source artifacts under `data/source_artifacts/`.
The generated mission copies their hashes and evidence summary into:

```text
data/calibrated_mission/source_manifest.json
```

That manifest records source URLs, local file sizes, SHA-256 hashes, and the exact claim each artifact supports. Current proof includes:

- GPLA-12 raw acoustic CSV and labels: real public pipeline acoustic leakage proxy data
- SubPipe README and Zenodo metadata: public underwater pipeline-inspection IMU/navigation archive proof
- WNTR/EPANET `.inp` files: real water-network graph and leak-scenario format proof
- AQUALOC official page and OceanShip arXiv metadata: underwater IMU/pressure and hydrophone-background references

Rebuild the proof bundle with:

```sh
python3 scripts/fetch_source_proof.py --out data/source_artifacts --mission data/calibrated_mission
```

This proves the replay is backed by prerecorded public/proxy artifacts, with hashes, while the route and final mission are a controlled PipeOwl replay built from those dataset-derived patterns.

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
python3 scripts/generate_calibrated_mission.py --out data/calibrated_mission
streamlit run app_streamlit.py
```

The dashboard shows a pipe-network replay, moving robot, live sensor values, and reached events with evidence.

## Dataset Strategy

PipeOwl should not be built around one dataset. Build around the canonical PipeOwl mission format, then add adapters.

- SubPipe: primary public calibration source for robot IMU/navigation-style data
- AQUALOC: backup underwater IMU/pressure/localization source
- GPLA-12: acoustic pipeline leak classifier calibration source
- Water-network acoustic leak literature: methodology reference
- OceanShip: hydrophone-like underwater background noise
- WNTR/EPANET: modeled pipe graph, pressure/flow context, intersections, leak scenarios

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
- `pipeowl/calibration_profiles.py`: public dataset calibration source and pattern assumptions
- `pipeowl/provenance.py`: source artifact hashes, evidence summary, and proof manifest writer
- `pipeowl/hardware_importer.py`: imports real PipeOwl hardware/test-loop logs into the mission format
- `pipeowl/mission_builder.py`: deterministic dataset-calibrated replay generator
- `pipeowl/adapters/`: public dataset adapter skeletons
- `scripts/fetch_source_proof.py`: downloads public proof artifacts and writes `source_manifest.json`
- `scripts/import_hardware_mission.py`: converts raw hardware logs into `data/real_mission`
- `scripts/generate_calibrated_mission.py`: creates `data/calibrated_mission`
- `app_streamlit.py`: mission replay dashboard
- `include/`, `src/`: C++ robot controller prototype
- `docs/`: mission format, dataset plan, design, safety, and walkthrough

## Claim Boundary

The current replay is dataset-calibrated: public robot/acoustic datasets calibrate the sensor behavior, while pipe geometry, tether, and event placement are modeled into a repeatable demo mission. It is strongest when presented as a prerecorded-dataset-backed simulation of the future PipeOwl workflow.

The first milestone should be dry bench testing, then a clear test pipe, then clean-water testing. Real municipal, storm, or wastewater use needs proper sanitation, electrical isolation, retrieval planning, and permission from the pipe owner.
