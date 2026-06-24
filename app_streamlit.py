"""Simple local PipeOwl visual simulation."""

from __future__ import annotations

import base64
import json
from pathlib import Path

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


MISSION_DIR = Path("data/demo_mission")
SCENE_IMAGE = Path("assets/sewer-robot-scene.png")


@st.cache_data
def load_json(path: str):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_asset_data_uri(path: str) -> str:
    image_path = Path(path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def mission_path(filename: str) -> Path:
    return MISSION_DIR / filename


def nearest_row(frame: pd.DataFrame, column: str, value: float) -> pd.Series:
    index = (frame[column] - value).abs().idxmin()
    return frame.loc[index]


def event_title(event_type: str) -> str:
    titles = {
        "possible_leak": "Possible leak",
        "intersection": "Known intersection",
        "possible_bend": "Bend detected",
        "possible_impact": "Bump or tether tug",
        "possible_stuck": "Possible stuck robot",
        "tether_artifact": "Tether artifact",
    }
    return titles.get(event_type, event_type.replace("_", " ").title())


def current_mode(distance_m: float, leak_score: float, events: pd.DataFrame) -> str:
    nearby = events[(events["distance_m"] - distance_m).abs() < 0.8]
    if leak_score >= 0.70:
        return "Checking leak sound"
    if not nearby.empty:
        return event_title(str(nearby.iloc[0]["type"]))
    return "Moving through pipe"


def event_cards(events: pd.DataFrame, current_distance: float) -> str:
    leak = events[events["type"] == "possible_leak"].iloc[0]
    impact = events[events["type"] == "possible_impact"].iloc[0]
    junctions = events[events["type"] == "intersection"].sort_values("distance_m")

    rows = [
        {
            "name": "Known junctions",
            "distance": ", ".join(f"{value:.0f} m" for value in junctions["distance_m"].tolist()),
            "note": "Blue markers come from the pipe map.",
            "active": bool((junctions["distance_m"] <= current_distance).any()),
        },
        {
            "name": "Bump or tether tug",
            "distance": f"{float(impact['distance_m']):.1f} m",
            "note": "Spike in IMU and tether tension.",
            "active": current_distance >= float(impact["distance_m"]),
        },
        {
            "name": "Possible leak sound",
            "distance": f"{float(leak['distance_m']):.1f} m",
            "note": "Hydrophone score rises without a bump.",
            "active": current_distance >= float(leak["distance_m"]),
        },
    ]

    cards = []
    for row in rows:
        class_name = "event-card active" if row["active"] else "event-card"
        cards.append(
            f"""
            <div class="{class_name}">
              <div class="event-name">{row["name"]}</div>
              <div class="event-distance">{row["distance"]}</div>
              <div class="event-note">{row["note"]}</div>
            </div>
            """
        )
    return "\n".join(cards)


def marker_html(label: str, event_type: str, distance_m: float, total_distance: float) -> str:
    progress = max(0.0, min(1.0, distance_m / total_distance))
    top = 82.0 - progress * 55.0
    left = 50.0 + (progress - 0.5) * 7.0
    return (
        f'<div class="marker {event_type}" style="left:{left:.2f}%; top:{top:.2f}%;">'
        f'<span>{label}</span></div>'
    )


def scene_html(scene_uri: str,
               progress: float,
               current_distance: float,
               total_distance: float,
               mode: str,
               leak_score: float,
               tension_n: float,
               events: pd.DataFrame) -> str:
    progress = max(0.0, min(1.0, progress))
    robot_top = 82.0 - progress * 55.0
    robot_left = 50.0 + (progress - 0.5) * 7.0
    robot_scale = 1.0 - progress * 0.45
    leak_distance = float(events.loc[events["type"] == "possible_leak", "distance_m"].iloc[0])
    impact_distance = float(events.loc[events["type"] == "possible_impact", "distance_m"].iloc[0])
    intersections = events[events["type"] == "intersection"]["distance_m"].tolist()

    markers = [
        marker_html("LEAK", "leak", leak_distance, total_distance),
        marker_html("BUMP", "impact", impact_distance, total_distance),
    ]
    for index, distance_m in enumerate(intersections[:3], start=1):
        markers.append(marker_html(f"J{index}", "junction", float(distance_m), total_distance))

    return f"""
    <style>
      .sim-wrap {{
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #f8fafc;
      }}
      .scene {{
        position: relative;
        min-height: 680px;
        border-radius: 16px;
        overflow: hidden;
        background:
          linear-gradient(180deg, rgba(4, 12, 18, 0.18), rgba(4, 12, 18, 0.72)),
          url("{scene_uri}") center / cover no-repeat;
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.22);
      }}
      .hud {{
        position: absolute;
        left: 24px;
        top: 22px;
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        z-index: 4;
      }}
      .hud-card {{
        min-width: 138px;
        border: 1px solid rgba(255,255,255,0.24);
        border-radius: 10px;
        padding: 12px 14px;
        background: rgba(8, 16, 24, 0.66);
        backdrop-filter: blur(10px);
      }}
      .hud-label {{
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #bdd6df;
      }}
      .hud-value {{
        margin-top: 4px;
        font-size: 24px;
        font-weight: 760;
        line-height: 1;
      }}
      .status {{
        position: absolute;
        right: 24px;
        top: 22px;
        max-width: 280px;
        border-radius: 10px;
        padding: 14px 16px;
        background: rgba(8, 16, 24, 0.72);
        border: 1px solid rgba(255,255,255,0.22);
        z-index: 4;
      }}
      .status-title {{
        font-size: 13px;
        color: #bdd6df;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .status-mode {{
        margin-top: 7px;
        font-size: 22px;
        font-weight: 760;
      }}
      .path {{
        position: absolute;
        left: 50%;
        top: 25%;
        width: 3px;
        height: 59%;
        transform: translateX(-50%);
        border-radius: 999px;
        background: linear-gradient(180deg, rgba(148, 213, 255, 0.10), rgba(56, 189, 248, 0.78));
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.55);
        z-index: 1;
      }}
      .robot-pin {{
        position: absolute;
        z-index: 5;
        left: {robot_left:.2f}%;
        top: {robot_top:.2f}%;
        transform: translate(-50%, -50%) scale({robot_scale:.3f});
        transition: left 260ms ease, top 260ms ease, transform 260ms ease;
      }}
      .robot-body {{
        position: relative;
        width: 102px;
        height: 62px;
        border-radius: 18px;
        background: linear-gradient(145deg, #3a4148, #151b22);
        border: 2px solid rgba(255,255,255,0.34);
        box-shadow: 0 10px 28px rgba(0,0,0,0.55), 0 0 30px rgba(251, 191, 36, 0.35);
      }}
      .robot-body::before,
      .robot-body::after {{
        content: "";
        position: absolute;
        top: 9px;
        width: 16px;
        height: 44px;
        border-radius: 999px;
        background: repeating-linear-gradient(180deg, #10141a 0 5px, #2a3138 5px 9px);
      }}
      .robot-body::before {{ left: -13px; }}
      .robot-body::after {{ right: -13px; }}
      .robot-lens {{
        position: absolute;
        left: 50%;
        top: 50%;
        width: 28px;
        height: 28px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        background: radial-gradient(circle, #ffffff 0 13%, #9fdcff 14% 32%, #1e293b 33% 100%);
        box-shadow: 0 0 18px #dff7ff;
      }}
      .robot-name {{
        position: absolute;
        left: 50%;
        top: 70px;
        transform: translateX(-50%);
        white-space: nowrap;
        border-radius: 999px;
        padding: 5px 9px;
        background: rgba(15, 23, 42, 0.74);
        border: 1px solid rgba(255,255,255,0.25);
        font-size: 12px;
        font-weight: 700;
      }}
      .marker {{
        position: absolute;
        z-index: 3;
        transform: translate(-50%, -50%);
      }}
      .marker::before {{
        content: "";
        display: block;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 0 18px currentColor;
        background: currentColor;
      }}
      .marker span {{
        position: absolute;
        left: 24px;
        top: -5px;
        padding: 4px 7px;
        border-radius: 999px;
        background: rgba(8, 16, 24, 0.76);
        border: 1px solid rgba(255,255,255,0.22);
        font-size: 11px;
        font-weight: 760;
        letter-spacing: 0.03em;
      }}
      .marker.leak {{ color: #ef4444; }}
      .marker.impact {{ color: #f59e0b; }}
      .marker.junction {{ color: #38bdf8; }}
      .bottom-strip {{
        position: absolute;
        left: 24px;
        right: 24px;
        bottom: 22px;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        z-index: 4;
      }}
      .event-card {{
        min-height: 94px;
        border-radius: 10px;
        padding: 12px 13px;
        background: rgba(8, 16, 24, 0.68);
        border: 1px solid rgba(255,255,255,0.18);
      }}
      .event-card.active {{
        border-color: rgba(56, 189, 248, 0.92);
        box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.18), 0 0 24px rgba(56, 189, 248, 0.18);
      }}
      .event-name {{
        font-weight: 780;
        font-size: 15px;
      }}
      .event-distance {{
        margin-top: 3px;
        color: #bae6fd;
        font-size: 13px;
      }}
      .event-note {{
        margin-top: 7px;
        color: #d8e7ee;
        font-size: 12px;
        line-height: 1.3;
      }}
      @media (max-width: 900px) {{
        .scene {{ min-height: 760px; }}
        .status {{
          left: 24px;
          right: 24px;
          top: 132px;
          max-width: none;
        }}
        .bottom-strip {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
    <div class="sim-wrap">
      <div class="scene">
        <div class="path"></div>
        {"".join(markers)}
        <div class="hud">
          <div class="hud-card">
            <div class="hud-label">Distance</div>
            <div class="hud-value">{current_distance:.1f} m</div>
          </div>
          <div class="hud-card">
            <div class="hud-label">Leak score</div>
            <div class="hud-value">{leak_score:.2f}</div>
          </div>
          <div class="hud-card">
            <div class="hud-label">Tether</div>
            <div class="hud-value">{tension_n:.1f} N</div>
          </div>
        </div>
        <div class="status">
          <div class="status-title">Current robot state</div>
          <div class="status-mode">{mode}</div>
        </div>
        <div class="robot-pin">
          <div class="robot-body"><div class="robot-lens"></div></div>
          <div class="robot-name">PIPEOWL</div>
        </div>
        <div class="bottom-strip">
          {event_cards(events, current_distance)}
        </div>
      </div>
    </div>
    """


def main() -> None:
    st.set_page_config(page_title="PipeOwl Local Simulation", layout="wide")
    st.markdown(
        """
        <style>
          .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.5rem;
            max-width: 1280px;
          }
          h1 {
            letter-spacing: 0;
            margin-bottom: 0.2rem;
          }
          .intro {
            color: #46515c;
            font-size: 1.02rem;
            margin-bottom: 1rem;
          }
          .stSlider [data-baseweb="slider"] {
            padding-top: 0.5rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not MISSION_DIR.exists():
        from pipeowl import build_demo_mission

        build_demo_mission(MISSION_DIR)

    metadata = load_json(str(mission_path("metadata.json")))
    robot_state = load_csv(str(mission_path("robot_state.csv")))
    reel = load_csv(str(mission_path("reel.csv")))
    acoustic = load_csv(str(mission_path("acoustic_features.csv")))
    events = load_csv(str(mission_path("events.csv")))
    scene_uri = load_asset_data_uri(str(SCENE_IMAGE))

    max_time = float(robot_state["time_s"].max())
    default_time = min(66.0, max_time)

    st.title("PipeOwl local pipe robot simulation")
    st.markdown(
        '<div class="intro">Move the robot through the pipe. The page shows distance, tether tension, known junctions, bumps, and possible leak sound.</div>',
        unsafe_allow_html=True,
    )

    current_time = st.slider("Move robot", 0.0, max_time, default_time, 0.5)
    current_state = nearest_row(robot_state, "time_s", current_time)
    current_reel = nearest_row(reel, "time_s", current_time)
    current_acoustic = nearest_row(acoustic, "window_start_s", current_time)
    total_distance = float(robot_state["distance_m"].max())
    current_distance = float(current_state["distance_m"])
    leak_score = float(current_acoustic["leak_score"])
    tension_n = float(current_reel["tether_tension_N"])
    mode = current_mode(current_distance, leak_score, events)
    progress = current_distance / total_distance if total_distance else 0.0

    components.html(
        scene_html(
            scene_uri=scene_uri,
            progress=progress,
            current_distance=current_distance,
            total_distance=total_distance,
            mode=mode,
            leak_score=leak_score,
            tension_n=tension_n,
            events=events,
        ),
        height=710,
        scrolling=False,
    )

    with st.expander("What this is using"):
        st.write(metadata.get("provenance_note", "Synthetic sample mission."))
        st.write("Data streams: robot position, IMU, tether reel, hydrophone-derived leak score, and known junctions.")


if __name__ == "__main__":
    main()
