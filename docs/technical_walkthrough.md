# Technical Walkthrough Script

## Short Story

The demo is a PipeOwl mission replay built from prerecorded public datasets and water-network artifacts. GPLA-12 supports acoustic leak-like features, SubPipe/AQUALOC support underwater robot motion assumptions, and WNTR/EPANET supports pipe-network geometry. The replay converts those dataset-backed patterns into the same canonical files the sonde will produce: acoustic, IMU, reel, and pipe metadata.

## Show Sequence

1. Robot enters pipe.
2. Distance increases from tether/reel.
3. Network map marks known intersections.
4. IMU detects bend and impact candidates.
5. Hydrophone leak score rises near the modeled leak.
6. Event card shows evidence and confidence.
7. Download mission JSON.

## Say

- The demo is backed by prerecorded public datasets, not random synthetic values.
- The canonical format matches expected sonde outputs.
- GPLA-12, SubPipe/AQUALOC, and WNTR/EPANET each support a specific part of the replay.
- The proof manifest records source URLs, file sizes, and hashes.

## Claim Boundary

- Leak, bend, and intersection events are dataset-backed replay outputs.
- Real-world leak accuracy needs a controlled test-loop recording with known leak ground truth.
- Intersections come from network geometry plus IMU turn patterns, not hydrophone frequency alone.
