# Technical Walkthrough Script

## Short Story

The hardware MVP is a drifting tethered sonde with hydrophone and IMU. The hard mechanical work is insertion and retrieval, but the software layer can be built now. This interface ingests the same data format the robot will produce: acoustic, IMU, reel, and pipe metadata. For this replay, public underwater robot and acoustic datasets calibrate sensor behavior, while the pipe route, tether, and event placement are modeled until hardware test-loop logs exist. The result is a mission replay that turns raw robot-like logs into leak locations, bend/intersection markers, and a maintenance map.

## Show Sequence

1. Robot enters pipe.
2. Distance increases from tether/reel.
3. Network map marks known intersections.
4. IMU detects bend and impact candidates.
5. Hydrophone leak score rises near the modeled leak.
6. Event card shows evidence and confidence.
7. Download mission JSON.

## Say

- The analysis framework is ready before hardware.
- The canonical format matches expected sonde outputs.
- Current replay is dataset-calibrated; some streams remain modeled until hardware logs exist.
- The next milestone is low-pressure test-loop data.

## Do Not Say

- We already detect real Braila leaks.
- We have exact X/Y from IMU alone.
- We can identify all intersections without a map.
- This is real in-pipe hydrophone data from our robot.
