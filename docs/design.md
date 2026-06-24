# Water Pipe Investigation Robot Design

## Mission

Build a compact tethered robot that can inspect water pipes, report position estimates, identify visible blockage, and flag zones that deserve a human review for leaks or structural damage.

## First Prototype

The first prototype should focus on repeatable testing instead of full autonomy.

- Drive through a straight transparent pipe section
- Stream camera or recorded inspection data
- Detect front obstacles and stop or scan around them
- Flag likely leak zones using acoustic score, pressure/flow changes, or turbidity
- Reverse safely when tether tension, tilt, or low battery is detected

## Mechanical Concept

- Low center of gravity tracked chassis
- Sealed electronics pod above the drive base
- Replaceable wheel or track skins for pipe diameter changes
- Nose bumper with clear camera window
- Rear tether strain relief and retrieval eyelet
- Dimmable LED ring around the camera

## Electronics Concept

- Low voltage battery or tether-fed power
- Motor controller with current sensing
- Wide angle camera module
- IMU for roll and pitch
- Short range distance sensor facing forward
- Optional pressure, flow, turbidity, temperature, and acoustic sensors
- Microcontroller or single-board computer depending on camera needs

## Software Architecture

The current C++ controller is intentionally hardware-agnostic.

```text
operator command      real sensors or simulator
       |                       |
       v                       v
  OperatorIntent          SensorSample
       \                     /
        \                   /
         v                 v
        PipeRobotController
                 |
                 v
            MotorCommand
                 |
                 v
       motor driver or simulator
```

This keeps mission behavior separate from hardware details. Later modules can add:

- Motor driver adapter
- Camera capture and recording
- Sensor fusion and logging
- Telemetry transport over tether, serial, or Wi-Fi in a dry test rig
- Operator UI

## Development Phases

1. Bench simulator: validate controller decisions and mission states
2. Dry chassis: test motors, tracks, command latency, and emergency stop
3. Clear pipe: tune lights, camera angle, obstacle detection, and tether handling
4. Clean water: validate sealing, buoyancy, traction, and retrieval
5. Inspection payload: add recording, leak scoring, and report generation

## Key Engineering Risks

- Waterproofing failure around shafts, ports, and camera windows
- Tether snagging or causing rollovers
- Poor traction in wet or slimy pipe interiors
- Camera glare from LEDs in tight reflective spaces
- Losing position estimate without wheel slip compensation
- Battery safety in sealed enclosures
