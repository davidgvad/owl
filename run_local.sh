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

echo "Generating local sample mission..."
.venv/bin/python scripts/generate_demo_mission.py --out data/demo_mission

echo
echo "PipeOwl is starting locally."
echo "Open: http://127.0.0.1:8501"
echo

exec env STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
  .venv/bin/streamlit run app_streamlit.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true
