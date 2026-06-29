# PipeOwl Mission Format

The demo uses one simple mission folder. The dashboard reads these files directly.

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

## Required Files

### metadata.json

Stores mission identity, data provenance, pipe metadata, sonde metadata, calibration sources, and optional modeled truth.

Required top-level keys:

- `mission_id`
- `data_sources`
- `pipe`
- `sonde`

### network.geojson

GeoJSON `FeatureCollection` containing pipe routes and known intersections. For the current calibrated replay, intersections come from the WNTR/EPANET-style pipe graph. IMU can suggest a bend or branch candidate, but it cannot reliably recover the network map alone.

### robot_state.csv

Required columns:

```csv
time_s,distance_m,x_m,y_m,heading_rad,speed_mps,pressure_bar,flow_velocity_mps,pipe_id
```

### imu.csv

Required columns:

```csv
time_s,distance_m,ax_mps2,ay_mps2,az_mps2,gx_radps,gy_radps,gz_radps,accel_mag,gyro_mag,jerk
```

### reel.csv

Required columns:

```csv
time_s,distance_m,tether_length_m,payout_speed_mps,tether_tension_N
```

### acoustic_features.csv

Required columns:

```csv
window_start_s,window_end_s,distance_m,rms,peak,bandpower_100_500,bandpower_500_2000,bandpower_2000_10000,spectral_centroid_hz,leak_score
```

### events.csv

Required columns:

```csv
event_id,type,time_s,distance_m,x_m,y_m,confidence,source,evidence,notes
```

`evidence` is a pipe-separated list of the characterizing parameters recorded
for that event, such as `Leak score 0.91 | Pressure change -0.18 bar |
Accel check max 9.92 m/s^2`.

Current event types:

- `possible_leak`
- `possible_bend`
- `intersection`
- `possible_impact`
- `possible_stuck`
- `tether_artifact`

## Fusion Rule V0

The first leak event detector uses an explainable rule:

```text
possible leak =
  high acoustic leak score
  and no large IMU impact
  and no tether tension spike
```

That rule prevents the replay from treating every loud sound as a leak.
