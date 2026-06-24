"""PipeOwl Mission Replay Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import pandas as pd
    import plotly.graph_objects as go
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by users without deps
    missing = exc.name
    raise SystemExit(
        f"Missing dashboard dependency: {missing}. "
        "Install with `python3 -m pip install -r requirements.txt`."
    ) from exc


MISSION_DIR = Path("data/demo_mission")


@st.cache_data
def load_json(path: str):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def mission_path(filename: str) -> Path:
    return MISSION_DIR / filename


def nearest_row(frame: pd.DataFrame, time_s: float) -> pd.Series:
    index = (frame["time_s"] - time_s).abs().idxmin()
    return frame.loc[index]


def build_map(network, robot_state: pd.DataFrame, events: pd.DataFrame, current_time: float) -> go.Figure:
    fig = go.Figure()

    for feature in network.get("features", []):
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        if geometry.get("type") == "LineString":
            coords = geometry.get("coordinates", [])
            fig.add_trace(
                go.Scatter(
                    x=[coord[0] for coord in coords],
                    y=[coord[1] for coord in coords],
                    mode="lines",
                    line={
                        "width": 8 if properties.get("kind") == "pipe" else 4,
                        "color": "#4f6f7a" if properties.get("id", "").startswith("MAIN") else "#8aa2a8",
                    },
                    name=properties.get("id", "pipe"),
                    hovertemplate="%{text}<extra></extra>",
                    text=[properties.get("id", "pipe")] * len(coords),
                )
            )

    path_before = robot_state[robot_state["time_s"] <= current_time]
    if len(path_before) > 1:
        fig.add_trace(
            go.Scatter(
                x=path_before["x_m"],
                y=path_before["y_m"],
                mode="lines",
                line={"width": 5, "color": "#10b981"},
                name="Replay path",
            )
        )

    current = nearest_row(robot_state, current_time)
    fig.add_trace(
        go.Scatter(
            x=[current["x_m"]],
            y=[current["y_m"]],
            mode="markers",
            marker={"size": 18, "color": "#f59e0b", "symbol": "circle"},
            name="Sonde",
            hovertemplate="distance=%{text:.1f} m<extra></extra>",
            text=[current["distance_m"]],
        )
    )

    if not events.empty:
        event_colors = {
            "possible_leak": "#ef4444",
            "intersection": "#2563eb",
            "possible_bend": "#7c3aed",
            "possible_impact": "#f97316",
            "possible_stuck": "#b91c1c",
            "tether_artifact": "#64748b",
        }
        fig.add_trace(
            go.Scatter(
                x=events["x_m"],
                y=events["y_m"],
                mode="markers+text",
                marker={
                    "size": 13,
                    "color": [event_colors.get(value, "#334155") for value in events["type"]],
                    "line": {"width": 1, "color": "white"},
                },
                text=events["event_id"],
                textposition="top center",
                name="Events",
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    "distance=%{customdata[1]:.1f} m<br>"
                    "confidence=%{customdata[2]:.2f}<br>"
                    "%{customdata[3]}<extra></extra>"
                ),
                customdata=events[["type", "distance_m", "confidence", "notes"]],
            )
        )

    fig.update_layout(
        height=560,
        margin={"l": 10, "r": 10, "t": 20, "b": 10},
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        xaxis={"title": "x_m", "scaleanchor": "y", "scaleratio": 1, "gridcolor": "#e2e8f0"},
        yaxis={"title": "y_m", "gridcolor": "#e2e8f0"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    return fig


def build_acoustic_heatmap(acoustic: pd.DataFrame) -> go.Figure:
    bands = [
        "bandpower_100_500",
        "bandpower_500_2000",
        "bandpower_2000_10000",
    ]
    z = [acoustic[band].tolist() for band in bands]
    fig = go.Figure(
        data=go.Heatmap(
            x=acoustic["distance_m"],
            y=["100-500 Hz", "500-2000 Hz", "2000-10000 Hz"],
            z=z,
            colorscale="Viridis",
            colorbar={"title": "power"},
        )
    )
    fig.update_layout(
        height=260,
        margin={"l": 10, "r": 10, "t": 20, "b": 30},
        xaxis={"title": "distance_m"},
        yaxis={"title": "band"},
    )
    return fig


def build_line_chart(frame: pd.DataFrame, x: str, y_fields, title: str) -> go.Figure:
    fig = go.Figure()
    for field in y_fields:
        fig.add_trace(go.Scatter(x=frame[x], y=frame[field], mode="lines", name=field))
    fig.update_layout(
        title=title,
        height=230,
        margin={"l": 10, "r": 10, "t": 35, "b": 25},
        xaxis={"title": x},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    return fig


def event_panel(events: pd.DataFrame) -> None:
    for _, row in events.sort_values("time_s").iterrows():
        confidence = float(row["confidence"])
        st.markdown(
            f"""
            <div class="event-card">
              <div class="event-title">{row['event_id']} | {row['type']}</div>
              <div class="event-meta">{row['distance_m']:.1f} m | confidence {confidence:.2f} | {row['source']}</div>
              <div class="event-notes">{row['notes']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="PipeOwl Mission Replay", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.25rem; }
        .metric-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; }
        .event-card {
          border: 1px solid #d8dee4;
          border-radius: 8px;
          padding: 0.65rem 0.75rem;
          margin-bottom: 0.55rem;
          background: #ffffff;
        }
        .event-title { font-weight: 700; color: #0f172a; }
        .event-meta { font-size: 0.85rem; color: #475569; margin-top: 0.15rem; }
        .event-notes { font-size: 0.90rem; color: #1f2937; margin-top: 0.35rem; }
        .provenance {
          border-left: 4px solid #2563eb;
          background: #eff6ff;
          padding: 0.75rem;
          border-radius: 6px;
          color: #1e3a8a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("PipeOwl Mission Replay")

    if not MISSION_DIR.exists():
        from pipeowl import build_demo_mission

        build_demo_mission(MISSION_DIR)

    metadata = load_json(str(mission_path("metadata.json")))
    network = load_json(str(mission_path("network.geojson")))
    robot_state = load_csv(str(mission_path("robot_state.csv")))
    imu = load_csv(str(mission_path("imu.csv")))
    reel = load_csv(str(mission_path("reel.csv")))
    acoustic = load_csv(str(mission_path("acoustic_features.csv")))
    events = load_csv(str(mission_path("events.csv")))

    max_time = float(robot_state["time_s"].max())
    current_time = st.slider("Replay time", 0.0, max_time, min(68.0, max_time), 0.5)
    current_state = nearest_row(robot_state, current_time)
    current_reel = nearest_row(reel, current_time)
    current_acoustic_index = (acoustic["window_start_s"] - current_time).abs().idxmin()
    current_acoustic = acoustic.loc[current_acoustic_index]

    left, right = st.columns([0.36, 0.64], gap="large")

    with left:
        st.subheader(metadata.get("mission_name", metadata.get("mission_id", "Mission")))
        st.markdown(
            f"""
            <div class="provenance">{metadata.get('provenance_note', '')}</div>
            """,
            unsafe_allow_html=True,
        )
        metric_left, metric_right = st.columns(2)
        metric_left.metric("Distance", f"{current_state['distance_m']:.1f} m")
        metric_right.metric("Leak score", f"{current_acoustic['leak_score']:.2f}")
        metric_left.metric("Pressure", f"{current_state['pressure_bar']:.2f} bar")
        metric_right.metric("Flow", f"{current_state['flow_velocity_mps']:.2f} m/s")
        metric_left.metric("Tether", f"{current_reel['tether_length_m']:.1f} m")
        metric_right.metric("Tension", f"{current_reel['tether_tension_N']:.1f} N")

        st.subheader("Events")
        event_panel(events)

        with st.expander("Data provenance", expanded=False):
            for source in metadata.get("data_sources", []):
                st.write(source)

    with right:
        st.plotly_chart(build_map(network, robot_state, events, current_time), use_container_width=True)

        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.plotly_chart(build_acoustic_heatmap(acoustic), use_container_width=True)
        with chart_right:
            st.plotly_chart(
                build_line_chart(acoustic, "distance_m", ["leak_score", "rms"], "Hydrophone features"),
                use_container_width=True,
            )

        lower_left, lower_right = st.columns(2)
        imu_sample = imu.iloc[:: max(1, len(imu) // 900)]
        with lower_left:
            st.plotly_chart(
                build_line_chart(imu_sample, "distance_m", ["accel_mag", "gyro_mag"], "IMU timeline"),
                use_container_width=True,
            )
        with lower_right:
            st.plotly_chart(
                build_line_chart(reel, "distance_m", ["tether_tension_N", "payout_speed_mps"], "Tether timeline"),
                use_container_width=True,
            )

        report = {
            "mission_id": metadata.get("mission_id"),
            "events": events.to_dict(orient="records"),
            "data_sources": metadata.get("data_sources", []),
        }
        st.download_button(
            "Download mission JSON",
            json.dumps(report, indent=2),
            file_name=f"{metadata.get('mission_id', 'pipeowl')}_report.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
