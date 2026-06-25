# Dataset Plan

No single public dataset appears to provide all target PipeOwl streams:

```text
in-pipe drinking-water robot
+ hydrophone leak audio
+ IMU
+ tether payout
+ leak labels
+ pipe intersections
```

The credible approach is to combine public datasets, calibrate the replay from them, and label which streams are still modeled until hardware logs exist.

## Sources

### SubPipe

Primary public calibration source for robot motion and navigation. Target files include acceleration, angular velocity, forward distance, estimated state, pressure, temperature, and water velocity.

Use for:

- IMU acceleration
- IMU gyro
- distance/path calibration
- pressure and flow-like mission context
- underwater robot timestamp patterns

### AQUALOC

Backup underwater localization dataset from ROV runs with camera, MEMS-IMU, and pressure data.

Use for:

- additional underwater IMU examples
- pressure/depth metadata
- synchronization style for real robot datasets

### GPLA-12

Pipeline acoustic leakage calibration source. It is gas-pipeline data, not potable-water in-pipe hydrophone data.

Use for:

- acoustic feature workflow
- leak/no-leak classifier experiments
- RMS, peak, bandpower, centroid, MFCC feature pipelines

### Water-Network Acoustic Leak Literature

Use as a methodology reference for real water-network leak detection. Treat contact-microphone data as method guidance, not as in-pipe hydrophone truth.

### OceanShip

Hydrophone-like underwater background-noise calibration source.

Use for:

- realistic background noise
- non-leak negative examples
- metadata patterns for acoustic datasets

### WNTR / EPANET

Pipe network simulation and map generation.

Use for:

- pipe graph
- intersections
- diameter/material metadata
- pressure and flow context
- modeled leak scenarios and truth

## Adapter Rule

Every adapter emits canonical PipeOwl mission files. The dashboard never reads SubPipe, GPLA-12, OceanShip, or WNTR formats directly.
