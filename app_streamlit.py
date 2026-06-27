"""PipeOwl local pipe-network simulation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

try:
    import pandas as pd
    import streamlit as st
    import streamlit.components.v1 as components
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by users without deps
    missing = exc.name
    raise SystemExit(
        f"Missing dashboard dependency: {missing}. "
        "Install with `python3 -m pip install -r requirements.txt`."
    ) from exc


MISSION_DIR = Path(os.environ.get("PIPEOWL_MISSION_DIR", "data/calibrated_mission"))


@st.cache_data
def load_json(path: str):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_optional_json(path: str):
    target = Path(path)
    if not target.exists():
        return {}
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def mission_path(filename: str) -> Path:
    return MISSION_DIR / filename


def event_label(event_type: str) -> str:
    labels = {
        "intersection": "Intersection",
        "possible_bend": "Bend",
        "possible_impact": "Impact / tether tug",
        "possible_leak": "Possible leak",
        "possible_stuck": "Possible stuck",
        "tether_artifact": "Tether artifact",
    }
    return labels.get(event_type, event_type.replace("_", " ").title())


def event_color(event_type: str) -> str:
    colors = {
        "intersection": "#2563eb",
        "possible_bend": "#7c3aed",
        "possible_impact": "#f59e0b",
        "possible_leak": "#ef4444",
        "possible_stuck": "#b91c1c",
        "tether_artifact": "#64748b",
    }
    return colors.get(event_type, "#334155")


def prepare_network(network: Dict) -> List[Dict]:
    pipes = []
    for feature in network.get("features", []):
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        if geometry.get("type") != "LineString":
            continue
        coordinates = geometry.get("coordinates", [])
        if len(coordinates) < 2:
            continue
        pipes.append(
            {
                "id": properties.get("id", "PIPE"),
                "kind": properties.get("kind", "pipe"),
                "coords": coordinates,
            }
        )
    return pipes


def prepare_events(events: pd.DataFrame) -> List[Dict]:
    prepared = []
    for _, event in events.sort_values("distance_m").iterrows():
        prepared.append(
            {
                "id": str(event["event_id"]),
                "type": str(event["type"]),
                "label": event_label(str(event["type"])),
                "distance": float(event["distance_m"]),
                "x": float(event["x_m"]),
                "y": float(event["y_m"]),
                "confidence": float(event["confidence"]),
                "source": str(event["source"]),
                "notes": str(event["notes"]),
                "color": event_color(str(event["type"])),
            }
        )
    return prepared


def prepare_robot_state(robot_state: pd.DataFrame,
                        acoustic: pd.DataFrame,
                        reel: pd.DataFrame,
                        imu: pd.DataFrame) -> List[Dict]:
    acoustic_sorted = acoustic.sort_values("window_start_s")
    reel_sorted = reel.sort_values("time_s")
    imu_sorted = imu.sort_values("time_s")
    rows = []
    for _, state in robot_state.sort_values("time_s").iterrows():
        time_s = float(state["time_s"])
        acoustic_index = (acoustic_sorted["window_start_s"] - time_s).abs().idxmin()
        reel_index = (reel_sorted["time_s"] - time_s).abs().idxmin()
        imu_index = (imu_sorted["time_s"] - time_s).abs().idxmin()
        acoustic_row = acoustic_sorted.loc[acoustic_index]
        reel_row = reel_sorted.loc[reel_index]
        imu_row = imu_sorted.loc[imu_index]
        rows.append(
            {
                "time": time_s,
                "distance": float(state["distance_m"]),
                "x": float(state["x_m"]),
                "y": float(state["y_m"]),
                "pipe": str(state["pipe_id"]),
                "pressure": float(state["pressure_bar"]),
                "flow": float(state["flow_velocity_mps"]),
                "speed": float(state["speed_mps"]),
                "leakScore": float(acoustic_row["leak_score"]),
                "rms": float(acoustic_row["rms"]),
                "highBand": float(acoustic_row["bandpower_2000_10000"]),
                "centroid": float(acoustic_row["spectral_centroid_hz"]),
                "tension": float(reel_row["tether_tension_N"]),
                "payoutSpeed": float(reel_row["payout_speed_mps"]),
                "accelMag": float(imu_row["accel_mag"]),
                "gyroMag": float(imu_row["gyro_mag"]),
                "gyroZ": float(imu_row["gz_radps"]),
                "jerk": float(imu_row["jerk"]),
            }
        )
    return rows


def prepare_proof(source_manifest: Dict) -> Dict:
    summary = source_manifest.get("evidence_summary", {})
    hardware = summary.get("hardware", {})
    gpla = summary.get("gpla12", {})
    subpipe = summary.get("subpipe", {})
    wntr = summary.get("wntr", {})
    artifacts = []
    for artifact in source_manifest.get("artifacts", []):
        if artifact.get("stream") == "license":
            continue
        artifacts.append(
            {
                "id": artifact.get("id", ""),
                "title": artifact.get("title", ""),
                "role": artifact.get("role", ""),
                "sha": artifact.get("sha256", "")[:12],
                "size": int(artifact.get("size_bytes", 0) or 0),
                "url": artifact.get("source_url", ""),
                "status": artifact.get("status", "missing"),
            }
        )

    if hardware:
        hydrophone = hardware.get("hydrophone", {})
        summary_rows = [
            f"Hardware IMU rows: {hardware.get('imu_rows', 0)}",
            f"Hardware reel rows: {hardware.get('reel_rows', 0)}",
            f"Hydrophone: {hydrophone.get('duration_s', 0):.1f} s at {hydrophone.get('sample_rate_hz', 0)} Hz",
            f"Acoustic windows analyzed: {hardware.get('acoustic_windows', 0)}",
        ]
        modal = {
            "title": "Why this is real PipeOwl data",
            "lede": (
                "This mission was imported from local PipeOwl hardware/test-loop logs. "
                "The raw IMU, reel, hydrophone, and optional geometry files are hashed in source_manifest.json."
            ),
            "realItems": [
                "The IMU stream comes from a recorded imu.csv file.",
                "The tether/reel stream comes from a recorded reel.csv file.",
                "The hydrophone stream comes from a recorded hydrophone.wav file.",
                "Every raw input file has a local path, file size, and SHA-256 hash.",
            ],
            "mappingItems": [
                "Reel distance maps time to distance through the pipe.",
                "IMU samples are synchronized to reel distance and expanded with acceleration magnitude, gyro magnitude, and jerk.",
                "Hydrophone audio is windowed into RMS, peak, bandpower, spectral centroid, and leak score.",
                "If no surveyed network.geojson is supplied, the importer uses a straight test-pipe route.",
            ],
            "fusionText": (
                "A possible leak needs high hydrophone leak score and no matching IMU impact or tether artifact. "
                "Possible impacts and bends come directly from IMU/reel features in the imported recording."
            ),
            "boundaryText": (
                "This proves the dashboard can run from real PipeOwl logs. Real leak accuracy still needs controlled "
                "ground truth, like a known leak position in a test loop."
            ),
        }
        mode = "hardware"
    else:
        summary_rows = [
            f"GPLA-12 acoustic rows: {gpla.get('data_rows', 0)} x {gpla.get('samples_per_row', 0)}",
            f"GPLA-12 label rows: {gpla.get('label_rows', 0)}",
            f"SubPipe archive metadata: {len(subpipe.get('zenodo_archives', []))} public files indexed",
            f"WNTR Net3 network: {wntr.get('net3_junction_rows', 0)} junctions, {wntr.get('net3_pipe_rows', 0)} pipes",
        ]
        modal = {
            "title": "Why this demo is dataset-backed",
            "lede": (
                "This demo is constructed from prerecorded public source artifacts and a repeatable replay layer. "
                "The source URLs, local file sizes, and SHA-256 hashes are recorded in source_manifest.json."
            ),
            "realItems": [
                "GPLA-12 supplies real public acoustic leakage rows and labels.",
                "SubPipe and AQUALOC support underwater robot IMU/pressure assumptions.",
                "WNTR/EPANET supplies real water-network geometry and leak-scenario formats.",
                "Every proof artifact has a source URL, local size, and SHA-256 hash.",
            ],
            "mappingItems": [
                "GPLA-12 acoustic rows calibrate leak-like audio features: RMS, peak, bandpower, centroid, and leak score.",
                "SubPipe and AQUALOC support underwater IMU behavior: steady vibration, gyro turns, pressure timing, and impact-like spikes.",
                "WNTR/EPANET networks provide pipe graph logic: junctions, pipes, leak scenarios, and distance-to-location mapping.",
                "The tether/reel model converts replay time into distance, then distance is mapped onto the pipe route.",
            ],
            "fusionText": (
                "A leak event needs a high acoustic score plus pressure/flow context and no matching IMU impact or "
                "tether jerk. An intersection comes from network geometry and is supported by an IMU turn pattern."
            ),
            "boundaryText": (
                "The trustworthy claim is: prerecorded public/proxy datasets calibrate the acoustic, motion, and "
                "pipe-network behavior used in this repeatable PipeOwl mission replay."
            ),
        }
        mode = "calibrated"

    return {
        "mode": mode,
        "honestClaim": source_manifest.get("honest_claim", "No source manifest bundled."),
        "summary": summary_rows,
        "modal": modal,
        "artifacts": artifacts,
    }


def simulation_html(network: Dict, robot_state: pd.DataFrame, acoustic: pd.DataFrame,
                    reel: pd.DataFrame, imu: pd.DataFrame, events: pd.DataFrame,
                    source_manifest: Dict) -> str:
    pipes = prepare_network(network)
    prepared_events = prepare_events(events)
    prepared_state = prepare_robot_state(robot_state, acoustic, reel, imu)
    prepared_proof = prepare_proof(source_manifest)
    max_distance = float(robot_state["distance_m"].max())

    payload = json.dumps(
        {
            "pipes": pipes,
            "events": prepared_events,
            "states": prepared_state,
            "proof": prepared_proof,
            "maxDistance": max_distance,
        }
    )

    return f"""
    <div id="pipeowl-sim"></div>
    <script>
    const mission = {payload};
    const root = document.getElementById("pipeowl-sim");
    const width = 1100;
    const height = 610;
    const bounds = {{ minX: -3, maxX: 66, minY: -13, maxY: 18 }};
    const state = {{ playing: false, index: 0, speed: 1.0, frame: null, lastTick: null, proofOpen: false }};

    root.addEventListener("pointerdown", (event) => {{
      const target = event.target.closest ? event.target.closest("button") : null;
      if (!target || target.disabled) return;
      if (target.id === "startBtn") {{
        event.preventDefault();
        start();
      }}
      if (target.id === "pauseBtn") {{
        event.preventDefault();
        pause();
      }}
      if (target.id === "resetBtn") {{
        event.preventDefault();
        reset();
      }}
      if (target.id === "proofBtn") {{
        event.preventDefault();
        state.proofOpen = true;
        render();
      }}
      if (target.id === "closeProofBtn") {{
        event.preventDefault();
        state.proofOpen = false;
        render();
      }}
    }});

    root.addEventListener("input", (event) => {{
      if (event.target && event.target.id === "speedRange") {{
        state.speed = Number(event.target.value);
      }}
    }});

    function sx(x) {{
      return 80 + ((x - bounds.minX) / (bounds.maxX - bounds.minX)) * (width - 160);
    }}

    function sy(y) {{
      return height - 85 - ((y - bounds.minY) / (bounds.maxY - bounds.minY)) * (height - 155);
    }}

    function clamp(value, min, max) {{
      return Math.max(min, Math.min(max, value));
    }}

    function currentState() {{
      return mission.states[state.index] || mission.states[0];
    }}

    function activeEvents(distance) {{
      return mission.events.filter((event) => event.distance <= distance);
    }}

    function nextEvent(distance) {{
      return mission.events.find((event) => event.distance > distance);
    }}

    function currentMessage(row) {{
      const nearby = mission.events.find((event) => Math.abs(event.distance - row.distance) <= 0.5);
      if (nearby) return nearby.label;
      if (row.leakScore >= 0.7) return "Listening near leak signal";
      return "Travelling through pipe";
    }}

    function pipePath(pipe) {{
      return pipe.coords.map((coord, index) => {{
        const command = index === 0 ? "M" : "L";
        return `${{command}} ${{sx(coord[0])}} ${{sy(coord[1])}}`;
      }}).join(" ");
    }}

    function render() {{
      const row = currentState();
      const distance = row.distance;
      const progress = mission.maxDistance > 0 ? distance / mission.maxDistance : 0;
      const reached = activeEvents(distance);
      const upcoming = nextEvent(distance);
      const atEnd = state.index >= mission.states.length - 1;
      const startLabel = atEnd ? "Restart" : (state.index > 0 ? "Resume" : "Start");

      const pipeElements = mission.pipes.map((pipe) => {{
        const isMain = pipe.id.startsWith("MAIN");
        return `
          <path d="${{pipePath(pipe)}}"
                class="pipe ${{isMain ? "main-pipe" : "branch-pipe"}}"></path>
        `;
      }}).join("");

      const pipeCores = mission.pipes.map((pipe) => (
        `<path d="${{pipePath(pipe)}}" class="pipe-core"></path>`
      )).join("");

      const travelledPoints = mission.states
        .filter((item) => item.distance <= distance)
        .map((item, index) => `${{index === 0 ? "M" : "L"}} ${{sx(item.x)}} ${{sy(item.y)}}`)
        .join(" ");

      const eventMarkers = mission.events.map((event) => {{
        const isReached = event.distance <= distance;
        return `
          <g class="event-marker ${{isReached ? "reached" : ""}}">
            <circle cx="${{sx(event.x)}}" cy="${{sy(event.y)}}" r="${{isReached ? 12 : 8}}"
                    fill="${{event.color}}"></circle>
            <text x="${{sx(event.x) + 14}}" y="${{sy(event.y) - 12}}">${{event.label}}</text>
          </g>
        `;
      }}).join("");

      const reachedRows = reached.slice(-5).reverse().map((event) => `
        <div class="event-row">
          <div>
            <strong>${{event.label}}</strong>
            <span>${{event.distance.toFixed(1)}} m</span>
          </div>
          <p>${{event.notes}}</p>
        </div>
      `).join("") || `<div class="empty">No events reached yet.</div>`;

      const upcomingText = upcoming
        ? `${{upcoming.label}} at ${{upcoming.distance.toFixed(1)}} m`
        : "End of route";

      const proofFacts = mission.proof.summary.map((fact) => `
        <div class="proof-fact">${{fact}}</div>
      `).join("");

      const proofRows = mission.proof.artifacts.slice(0, 6).map((artifact) => `
        <a class="proof-row" href="${{artifact.url}}" target="_blank" rel="noreferrer">
          <div class="proof-row-head">
            <strong>${{artifact.id}}</strong>
          </div>
          <span>${{artifact.status}} | ${{(artifact.size / 1024).toFixed(1)}} KB | sha ${{artifact.sha}}</span>
          <p>${{artifact.role}}</p>
        </a>
      `).join("") || `<div class="empty">No source manifest bundled.</div>`;

      const modalFacts = mission.proof.summary.map((fact) => `
        <li>${{fact}}</li>
      `).join("");
      const realItems = mission.proof.modal.realItems.map((item) => `
        <li>${{item}}</li>
      `).join("");
      const mappingItems = mission.proof.modal.mappingItems.map((item) => `
        <li>${{item}}</li>
      `).join("");

      const proofModal = state.proofOpen ? `
        <div class="modal-backdrop">
          <section class="proof-modal" role="dialog" aria-modal="true" aria-label="Data validity explanation">
            <div class="modal-head">
              <div>
                <div class="mode-label">Data validity</div>
                <h2>${{mission.proof.modal.title}}</h2>
              </div>
              <button id="closeProofBtn" class="icon-button">Close</button>
            </div>
            <p class="modal-lede">
              ${{mission.proof.modal.lede}}
            </p>
            <div class="proof-grid">
              <div class="proof-explain">
                <h3>What is real</h3>
                <ul>
                  ${{modalFacts}}
                  ${{realItems}}
                </ul>
              </div>
              <div class="proof-explain">
                <h3>How we map it</h3>
                <ul>
                  ${{mappingItems}}
                </ul>
              </div>
              <div class="proof-explain wide">
                <h3>How detections are fused</h3>
                <p>
                  ${{mission.proof.modal.fusionText}}
                </p>
              </div>
              <div class="proof-explain wide boundary">
                <h3>Boundary of the claim</h3>
                <p>
                  ${{mission.proof.modal.boundaryText}}
                </p>
              </div>
            </div>
          </section>
        </div>
      ` : "";

      root.innerHTML = `
        <style>
          #pipeowl-sim {{
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #17202a;
          }}
          .sim-shell {{
            border: 1px solid #cbd9e3;
            border-radius: 10px;
            overflow: hidden;
            background: #f7fafc;
            box-shadow: 0 20px 45px rgba(15, 23, 42, 0.18);
          }}
          .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 16px 18px;
            border-bottom: 1px solid #d8e3eb;
            background: #ffffff;
          }}
          .title {{
            color: #111827;
            font-size: 20px;
            font-weight: 800;
          }}
          .subtitle {{
            margin-top: 4px;
            color: #334155;
            font-size: 14px;
            line-height: 1.35;
          }}
          .controls {{
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
          }}
          button {{
            border: 1px solid #cbd5df;
            background: #ffffff;
            border-radius: 8px;
            padding: 9px 12px;
            font-weight: 700;
            color: #17202a;
            cursor: pointer;
          }}
          button.secondary {{
            background: #eef6f8;
            border-color: #b7cbd4;
            color: #17465a;
          }}
          button.primary {{
            background: #0f766e;
            color: #ffffff;
            border-color: #0f766e;
          }}
          button:disabled {{
            cursor: default;
            opacity: 0.48;
          }}
          .sim-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 380px;
            min-height: 660px;
          }}
          .map-panel {{
            position: relative;
            min-height: 660px;
            background:
              radial-gradient(circle at 50% 46%, rgba(14, 116, 144, 0.10), transparent 36%),
              linear-gradient(180deg, #edf4f7, #d9e7ec);
          }}
          .pipe-svg {{
            width: 100%;
            height: 660px;
            display: block;
          }}
          .pipe {{
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
          }}
          .main-pipe {{
            stroke: #516875;
            stroke-width: 36;
          }}
          .branch-pipe {{
            stroke: #8197a3;
            stroke-width: 25;
          }}
          .pipe-core {{
            fill: none;
            stroke: rgba(255,255,255,0.42);
            stroke-width: 10;
            stroke-linecap: round;
            stroke-linejoin: round;
          }}
          .travelled {{
            fill: none;
            stroke: #22c55e;
            stroke-width: 8;
            stroke-linecap: round;
            stroke-linejoin: round;
            filter: drop-shadow(0 0 7px rgba(34, 197, 94, 0.45));
          }}
          .event-marker circle {{
            opacity: 0.55;
            stroke: white;
            stroke-width: 2;
          }}
          .event-marker.reached circle {{
            opacity: 1;
            filter: drop-shadow(0 0 8px rgba(15, 23, 42, 0.25));
          }}
          .event-marker text {{
            font-size: 11px;
            font-weight: 800;
            paint-order: stroke;
            stroke: #f8fafc;
            stroke-width: 5px;
            fill: #17202a;
          }}
          .robot {{
            filter: drop-shadow(0 10px 14px rgba(15, 23, 42, 0.32));
          }}
          .robot-body {{
            fill: #26323a;
            stroke: #0f172a;
            stroke-width: 2;
          }}
          .track {{
            fill: #0f172a;
          }}
          .camera {{
            fill: #e0f2fe;
            stroke: #0284c7;
            stroke-width: 2;
          }}
          .light {{
            fill: #facc15;
            opacity: 0.92;
          }}
          .side-panel {{
            border-left: 1px solid #dbe3ea;
            background: #ffffff;
            padding: 18px;
            max-height: 660px;
            overflow-y: auto;
          }}
          .mode-card {{
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            padding: 13px;
            background: #f8fafc;
            margin-bottom: 12px;
          }}
          .mode-label {{
            color: #526274;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            font-weight: 800;
          }}
          .mode {{
            margin-top: 5px;
            font-size: 22px;
            font-weight: 820;
          }}
          .metrics {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 14px;
          }}
          .metric {{
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            padding: 10px;
            background: #ffffff;
          }}
          .metric div:first-child {{
            color: #526274;
            font-size: 12px;
            font-weight: 750;
          }}
          .metric div:last-child {{
            margin-top: 4px;
            font-size: 19px;
            font-weight: 820;
          }}
          .evidence-card {{
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            background: #f8fafc;
            padding: 12px;
            margin: 0 0 14px;
          }}
          .evidence-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 9px;
          }}
          .evidence-item {{
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #ffffff;
            padding: 8px;
          }}
          .evidence-item div:first-child {{
            color: #526274;
            font-size: 11px;
            font-weight: 800;
          }}
          .evidence-item div:last-child {{
            margin-top: 3px;
            color: #111827;
            font-size: 15px;
            font-weight: 820;
          }}
          .progress-wrap {{
            margin: 8px 0 16px;
          }}
          .progress-label {{
            display: flex;
            justify-content: space-between;
            color: #475569;
            font-size: 12px;
            font-weight: 750;
            margin-bottom: 6px;
          }}
          .progress-bar {{
            height: 10px;
            border-radius: 999px;
            background: #e2e8f0;
            overflow: hidden;
          }}
          .progress-fill {{
            width: ${{(progress * 100).toFixed(1)}}%;
            height: 100%;
            background: linear-gradient(90deg, #0f766e, #22c55e);
          }}
          .event-row {{
            border-top: 1px solid #e5edf2;
            padding: 10px 0;
          }}
          .event-row div {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
          }}
          .event-row strong {{
            color: #111827;
            font-size: 15px;
          }}
          .event-row span {{
            color: #475569;
            font-size: 13px;
            white-space: nowrap;
          }}
          .event-row p {{
            margin: 5px 0 0;
            color: #263445;
            font-size: 14px;
            line-height: 1.42;
          }}
          .empty {{
            color: #64748b;
            padding-top: 10px;
          }}
          .proof-card {{
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            background: #f8fafc;
            padding: 12px;
            margin-top: 14px;
            max-width: 100%;
            overflow: hidden;
          }}
          .proof-fact {{
            color: #263445;
            font-size: 14px;
            line-height: 1.42;
            padding: 3px 0;
          }}
          .proof-row {{
            display: block;
            text-decoration: none;
            color: inherit;
            border-top: 1px solid #e5edf2;
            padding: 9px 0;
            max-width: 100%;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}
          .proof-row-head {{
            display: flex;
            align-items: baseline;
            justify-content: flex-start;
            gap: 8px;
            min-width: 0;
          }}
          .proof-row strong {{
            display: block;
            min-width: 0;
            max-width: 100%;
            overflow-wrap: anywhere;
            font-size: 13px;
          }}
          .proof-row span {{
            display: block;
            margin-top: 3px;
            max-width: 100%;
            color: #526274;
            font-size: 12px;
            white-space: normal;
            overflow-wrap: anywhere;
          }}
          .proof-row p {{
            margin: 4px 0 0;
            color: #263445;
            font-size: 13px;
            line-height: 1.35;
            max-width: 100%;
            overflow-wrap: anywhere;
          }}
          .modal-backdrop {{
            position: fixed;
            inset: 0;
            z-index: 30;
            display: grid;
            place-items: center;
            padding: 24px;
            background: rgba(6, 16, 24, 0.62);
          }}
          .proof-modal {{
            width: min(880px, 96vw);
            max-height: 86vh;
            overflow-y: auto;
            border-radius: 12px;
            background: #ffffff;
            border: 1px solid #cbd9e3;
            box-shadow: 0 28px 90px rgba(0, 0, 0, 0.35);
            padding: 24px;
          }}
          .modal-head {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            border-bottom: 1px solid #e3edf3;
            padding-bottom: 14px;
            margin-bottom: 16px;
          }}
          .modal-head h2 {{
            margin: 3px 0 0;
            color: #111827;
            font-size: 27px;
            line-height: 1.1;
          }}
          .icon-button {{
            background: #111827;
            color: #ffffff;
            border-color: #111827;
          }}
          .modal-lede {{
            margin: 0 0 18px;
            color: #263445;
            font-size: 16px;
            line-height: 1.5;
          }}
          .proof-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
          }}
          .proof-explain {{
            border: 1px solid #dbe5ec;
            border-radius: 10px;
            padding: 14px;
            background: #f8fafc;
          }}
          .proof-explain.wide {{
            grid-column: 1 / -1;
          }}
          .proof-explain.boundary {{
            background: #fff7ed;
            border-color: #fed7aa;
          }}
          .proof-explain h3 {{
            margin: 0 0 8px;
            color: #111827;
            font-size: 17px;
          }}
          .proof-explain ul {{
            margin: 0;
            padding-left: 18px;
          }}
          .proof-explain li,
          .proof-explain p {{
            color: #263445;
            font-size: 14px;
            line-height: 1.5;
            margin: 0 0 7px;
          }}
          .legend {{
            position: absolute;
            left: 14px;
            bottom: 14px;
            display: flex;
            gap: 9px;
            flex-wrap: wrap;
            background: rgba(255,255,255,0.84);
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 12px;
            color: #334155;
            font-weight: 700;
          }}
          .dot {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 999px;
            margin-right: 5px;
            vertical-align: -1px;
          }}
          .range {{
            width: 180px;
          }}
          @media (max-width: 900px) {{
            .sim-grid {{
              grid-template-columns: 1fr;
            }}
            .side-panel {{
              border-left: 0;
              border-top: 1px solid #dbe3ea;
              max-height: none;
            }}
            .proof-grid {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
        <div class="sim-shell">
          <div class="topbar">
            <div>
              <div class="title">Dataset-calibrated mission replay</div>
              <div class="subtitle">Press Start. The robot moves through the pipe and explains each detected pattern.</div>
            </div>
            <div class="controls">
              <button id="proofBtn" class="secondary">Why trust data?</button>
              <button id="startBtn" class="primary" ${{state.playing ? "disabled" : ""}}>${{startLabel}}</button>
              <button id="pauseBtn" ${{state.playing ? "" : "disabled"}}>Pause</button>
              <button id="resetBtn">Reset</button>
              <label>
                Speed
                <input id="speedRange" class="range" type="range" min="0.5" max="4" step="0.5" value="${{state.speed}}">
              </label>
            </div>
          </div>
          <div class="sim-grid">
            <div class="map-panel">
              <svg class="pipe-svg" viewBox="0 0 ${{width}} ${{height}}" preserveAspectRatio="xMidYMid meet">
                ${{pipeElements}}
                ${{pipeCores}}
                ${{travelledPoints ? `<path d="${{travelledPoints}}" class="travelled"></path>` : ""}}
                ${{eventMarkers}}
                <g class="robot" transform="translate(${{sx(row.x)}} ${{sy(row.y)}})">
                  <rect class="track" x="-27" y="-14" width="14" height="28" rx="5"></rect>
                  <rect class="track" x="13" y="-14" width="14" height="28" rx="5"></rect>
                  <rect class="robot-body" x="-20" y="-16" width="40" height="32" rx="9"></rect>
                  <circle class="camera" cx="0" cy="-2" r="8"></circle>
                  <circle class="light" cx="-12" cy="-9" r="3"></circle>
                  <circle class="light" cx="12" cy="-9" r="3"></circle>
                  <line x1="-31" y1="16" x2="-52" y2="34" stroke="#b7791f" stroke-width="4" stroke-linecap="round"></line>
                </g>
              </svg>
              <div class="legend">
                <span><i class="dot" style="background:#2563eb"></i>intersection</span>
                <span><i class="dot" style="background:#f59e0b"></i>bump</span>
                <span><i class="dot" style="background:#ef4444"></i>leak signal</span>
                <span><i class="dot" style="background:#22c55e"></i>travelled</span>
              </div>
            </div>
            <div class="side-panel">
              <div class="mode-card">
                <div class="mode-label">Robot state</div>
                <div class="mode">${{currentMessage(row)}}</div>
              </div>
              <div class="metrics">
                <div class="metric"><div>Distance</div><div>${{row.distance.toFixed(1)}} m</div></div>
                <div class="metric"><div>Pipe</div><div>${{row.pipe}}</div></div>
                <div class="metric"><div>Leak score</div><div>${{row.leakScore.toFixed(2)}}</div></div>
                <div class="metric"><div>Tether</div><div>${{row.tension.toFixed(1)}} N</div></div>
                <div class="metric"><div>Pressure</div><div>${{row.pressure.toFixed(2)}} bar</div></div>
                <div class="metric"><div>Flow</div><div>${{row.flow.toFixed(2)}} m/s</div></div>
              </div>
              <div class="evidence-card">
                <div class="mode-label">Live IMU evidence</div>
                <div class="evidence-grid">
                  <div class="evidence-item"><div>gyro_z</div><div>${{row.gyroZ.toFixed(3)}} rad/s</div></div>
                  <div class="evidence-item"><div>gyro_mag</div><div>${{row.gyroMag.toFixed(3)}} rad/s</div></div>
                  <div class="evidence-item"><div>accel_mag</div><div>${{row.accelMag.toFixed(2)}} m/s2</div></div>
                  <div class="evidence-item"><div>jerk</div><div>${{row.jerk.toFixed(1)}} m/s3</div></div>
                </div>
              </div>
              <div class="evidence-card">
                <div class="mode-label">Live acoustic / reel evidence</div>
                <div class="evidence-grid">
                  <div class="evidence-item"><div>RMS</div><div>${{row.rms.toFixed(3)}}</div></div>
                  <div class="evidence-item"><div>high band</div><div>${{row.highBand.toExponential(2)}}</div></div>
                  <div class="evidence-item"><div>centroid</div><div>${{Math.round(row.centroid)}} Hz</div></div>
                  <div class="evidence-item"><div>payout speed</div><div>${{row.payoutSpeed.toFixed(2)}} m/s</div></div>
                </div>
              </div>
              <div class="progress-wrap">
                <div class="progress-label"><span>Route progress</span><span>${{Math.round(progress * 100)}}%</span></div>
                <div class="progress-bar"><div class="progress-fill"></div></div>
              </div>
              <div class="mode-card">
                <div class="mode-label">Next important point</div>
                <div class="mode" style="font-size:18px">${{upcomingText}}</div>
              </div>
              <div class="mode-label">Reached data</div>
              ${{reachedRows}}
              <div class="proof-card">
                <div class="mode-label">Proof bundle</div>
                ${{proofFacts}}
                ${{proofRows}}
              </div>
            </div>
          </div>
        </div>
        ${{proofModal}}
      `;

    }}

    function cancelLoop() {{
      if (state.frame !== null) {{
        cancelAnimationFrame(state.frame);
        state.frame = null;
      }}
      state.lastTick = null;
    }}

    function tick(timestamp) {{
      if (!state.playing) {{
        state.frame = null;
        return;
      }}

      if (state.lastTick === null) {{
        state.lastTick = timestamp;
      }}

      const frameMs = 120;
      const elapsed = timestamp - state.lastTick;
      if (elapsed >= frameMs) {{
        const speedStep = Math.max(1, Math.round(state.speed * 2));
        const elapsedSteps = Math.max(1, Math.floor(elapsed / frameMs));
        state.index = clamp(state.index + speedStep * elapsedSteps, 0, mission.states.length - 1);
        state.lastTick = timestamp;
        render();
      }}

      if (state.index >= mission.states.length - 1) {{
        state.playing = false;
        cancelLoop();
        render();
        return;
      }}

      state.frame = requestAnimationFrame(tick);
    }}

    function start() {{
      if (!mission.states.length) return;
      if (state.playing) return;
      if (state.index >= mission.states.length - 1) {{
        state.index = 0;
      }}
      state.playing = true;
      cancelLoop();
      render();
      state.frame = requestAnimationFrame(tick);
    }}

    function pause() {{
      state.playing = false;
      cancelLoop();
      render();
    }}

    function reset() {{
      state.playing = false;
      cancelLoop();
      state.index = 0;
      render();
    }}

    render();
    </script>
    """


def main() -> None:
    st.set_page_config(page_title="PipeOwl Dataset-Calibrated Replay", layout="wide")
    st.markdown(
        """
        <style>
          .block-container {
            padding-top: 1rem;
            max-width: 1240px;
          }
          .stApp {
            background: #0b1017;
          }
          [data-testid="stHeader"],
          [data-testid="stToolbar"],
          [data-testid="stDecoration"],
          [data-testid="stDeployButton"],
          [data-testid="stStatusWidget"],
          [data-testid="stMainMenu"],
          .stDeployButton,
          #MainMenu,
          footer {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
          }
          .stApp {
            padding-top: 0;
          }
          h1 {
            color: #f8fafc;
            margin-bottom: 0.2rem;
            letter-spacing: 0;
          }
          .intro {
            color: #d8e1ea;
            font-size: 16px;
            line-height: 1.45;
            margin-bottom: 1rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not MISSION_DIR.exists():
        from pipeowl import build_calibrated_mission

        build_calibrated_mission(MISSION_DIR)

    metadata = load_json(str(mission_path("metadata.json")))
    network = load_json(str(mission_path("network.geojson")))
    robot_state = load_csv(str(mission_path("robot_state.csv")))
    imu = load_csv(str(mission_path("imu.csv")))
    reel = load_csv(str(mission_path("reel.csv")))
    acoustic = load_csv(str(mission_path("acoustic_features.csv")))
    events = load_csv(str(mission_path("events.csv")))
    source_manifest = load_optional_json(str(mission_path("source_manifest.json")))

    if metadata.get("replay_mode") == "hardware_import":
        title = "PipeOwl hardware mission replay"
        intro = (
            "Start the robot replay. This mission was imported from local PipeOwl IMU, reel, "
            "and hydrophone logs, then converted into the canonical mission format."
        )
    else:
        title = "PipeOwl dataset-calibrated pipe robot replay"
        intro = (
            "Start the robot. Sensor patterns are calibrated from public underwater robot and "
            "acoustic datasets, then fused with a modeled pipe network."
        )

    st.title(title)
    st.markdown(f'<div class="intro">{intro}</div>', unsafe_allow_html=True)

    components.html(
        simulation_html(network, robot_state, acoustic, reel, imu, events, source_manifest),
        height=980,
        scrolling=False,
    )


if __name__ == "__main__":
    main()
