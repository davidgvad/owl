#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating local Python environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, pandas" >/dev/null 2>&1; then
  echo "Installing local dashboard dependencies..."
  .venv/bin/python -m pip install -r requirements.txt
fi

MISSION_DIR="${PIPEOWL_MISSION_DIR:-data/calibrated_mission}"

if [ "$MISSION_DIR" = "data/calibrated_mission" ]; then
  echo "Generating dataset-calibrated replay mission..."
  .venv/bin/python scripts/generate_calibrated_mission.py --out data/calibrated_mission
else
  echo "Using imported mission: $MISSION_DIR"
fi

echo
echo "PipeOwl is starting locally."
echo "Open: http://127.0.0.1:8501"
echo

exec env STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
  PIPEOWL_MISSION_DIR="$MISSION_DIR" \
  .venv/bin/streamlit run app_streamlit.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true
