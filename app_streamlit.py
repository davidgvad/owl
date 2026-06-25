"""PipeOwl local pipe-network simulation."""

from __future__ import annotations

import json
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


MISSION_DIR = Path("data/calibrated_mission")


@st.cache_data
def load_json(path: str):
    with Path(path).open("r", encoding="utf-8") as handle:
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


def prepare_robot_state(robot_state: pd.DataFrame, acoustic: pd.DataFrame, reel: pd.DataFrame) -> List[Dict]:
    acoustic_sorted = acoustic.sort_values("window_start_s")
    reel_sorted = reel.sort_values("time_s")
    rows = []
    for _, state in robot_state.sort_values("time_s").iterrows():
        time_s = float(state["time_s"])
        acoustic_index = (acoustic_sorted["window_start_s"] - time_s).abs().idxmin()
        reel_index = (reel_sorted["time_s"] - time_s).abs().idxmin()
        acoustic_row = acoustic_sorted.loc[acoustic_index]
        reel_row = reel_sorted.loc[reel_index]
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
                "tension": float(reel_row["tether_tension_N"]),
            }
        )
    return rows


def simulation_html(network: Dict, robot_state: pd.DataFrame, acoustic: pd.DataFrame,
                    reel: pd.DataFrame, events: pd.DataFrame) -> str:
    pipes = prepare_network(network)
    prepared_events = prepare_events(events)
    prepared_state = prepare_robot_state(robot_state, acoustic, reel)
    max_distance = float(robot_state["distance_m"].max())

    payload = json.dumps(
        {
            "pipes": pipes,
            "events": prepared_events,
            "states": prepared_state,
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
    const state = {{ playing: false, index: 0, speed: 1.0, timer: null }};

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

      root.innerHTML = `
        <style>
          #pipeowl-sim {{
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #17202a;
          }}
          .sim-shell {{
            border: 1px solid #dbe3ea;
            border-radius: 12px;
            overflow: hidden;
            background: #f7fafc;
          }}
          .topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 14px 16px;
            border-bottom: 1px solid #dbe3ea;
            background: #ffffff;
          }}
          .title {{
            font-size: 19px;
            font-weight: 760;
          }}
          .subtitle {{
            margin-top: 2px;
            color: #5f6f7b;
            font-size: 13px;
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
          button.primary {{
            background: #0f766e;
            color: #ffffff;
            border-color: #0f766e;
          }}
          .sim-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 330px;
            min-height: 620px;
          }}
          .map-panel {{
            position: relative;
            min-height: 620px;
            background:
              radial-gradient(circle at 50% 46%, rgba(14, 116, 144, 0.10), transparent 36%),
              linear-gradient(180deg, #edf4f7, #d9e7ec);
          }}
          .pipe-svg {{
            width: 100%;
            height: 620px;
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
            font-size: 12px;
            font-weight: 800;
            paint-order: stroke;
            stroke: #f8fafc;
            stroke-width: 4px;
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
            padding: 16px;
            overflow: hidden;
          }}
          .mode-card {{
            border: 1px solid #dbe3ea;
            border-radius: 10px;
            padding: 13px;
            background: #f8fafc;
            margin-bottom: 12px;
          }}
          .mode-label {{
            color: #64748b;
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
            color: #64748b;
            font-size: 12px;
            font-weight: 750;
          }}
          .metric div:last-child {{
            margin-top: 4px;
            font-size: 19px;
            font-weight: 820;
          }}
          .progress-wrap {{
            margin: 8px 0 16px;
          }}
          .progress-label {{
            display: flex;
            justify-content: space-between;
            color: #64748b;
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
            font-size: 14px;
          }}
          .event-row span {{
            color: #64748b;
            font-size: 13px;
            white-space: nowrap;
          }}
          .event-row p {{
            margin: 5px 0 0;
            color: #475569;
            font-size: 13px;
            line-height: 1.35;
          }}
          .empty {{
            color: #64748b;
            padding-top: 10px;
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
              <button id="startBtn" class="primary">Start</button>
              <button id="pauseBtn">Pause</button>
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
            </div>
          </div>
        </div>
      `;

      document.getElementById("startBtn").onclick = start;
      document.getElementById("pauseBtn").onclick = pause;
      document.getElementById("resetBtn").onclick = reset;
      document.getElementById("speedRange").oninput = (event) => {{
        state.speed = Number(event.target.value);
      }};
    }}

    function step() {{
      if (!state.playing) return;
      state.index = clamp(state.index + Math.max(1, Math.round(state.speed * 2)), 0, mission.states.length - 1);
      if (state.index >= mission.states.length - 1) {{
        pause();
        return;
      }}
      render();
    }}

    function start() {{
      if (state.playing) return;
      state.playing = true;
      if (!state.timer) {{
        state.timer = setInterval(step, 120);
      }}
      render();
    }}

    function pause() {{
      state.playing = false;
      if (state.timer) {{
        clearInterval(state.timer);
        state.timer = null;
      }}
      render();
    }}

    function reset() {{
      pause();
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
          h1 {
            margin-bottom: 0.2rem;
            letter-spacing: 0;
          }
          .intro {
            color: #556370;
            margin-bottom: 1rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not MISSION_DIR.exists():
        from pipeowl import build_calibrated_mission

        build_calibrated_mission(MISSION_DIR)

    network = load_json(str(mission_path("network.geojson")))
    robot_state = load_csv(str(mission_path("robot_state.csv")))
    reel = load_csv(str(mission_path("reel.csv")))
    acoustic = load_csv(str(mission_path("acoustic_features.csv")))
    events = load_csv(str(mission_path("events.csv")))

    st.title("PipeOwl dataset-calibrated pipe robot replay")
    st.markdown(
        '<div class="intro">Start the robot. Sensor patterns are calibrated from public underwater robot and acoustic datasets, then fused with a modeled pipe network.</div>',
        unsafe_allow_html=True,
    )

    components.html(
        simulation_html(network, robot_state, acoustic, reel, events),
        height=760,
        scrolling=False,
    )


if __name__ == "__main__":
    main()
