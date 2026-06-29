# How We Built The PipeOwl Demo From Real Datasets

This is the simple explanation of what is going on in the demo.

The main idea is:

```text
we do not have final PipeOwl robot logs yet,
so we built a fake mission that behaves like the robot data we expect,
and we based the behavior on real public datasets.
```

So the demo is not just random numbers on a screen. But also it is not real
PipeOwl robot data yet. It is in the middle: a simulation guided by real data
sources.

## The Problem We Had

For the real robot, we eventually want data like this:

- hydrophone audio, so we can listen for leak-like sounds
- IMU data, so we can see motion, turns, impacts, and bumps
- reel/tether data, so we know how far the robot travelled
- pipe map data, so we know where intersections and branches are
- event logs, so the user can see "leak here", "bend here", "impact here"

But there is no public dataset that has all of this together:

```text
in-pipe water robot
+ hydrophone
+ IMU
+ tether distance
+ leak labels
+ pipe intersections
```

So instead we used different public datasets for different parts of the story.

## The Datasets We Used

### GPLA-12

This is the acoustic leak dataset.

In the repo we have:

```text
data/source_artifacts/gpla12_data_v1_data.csv
data/source_artifacts/gpla12_data_v1_label.csv
data/source_artifacts/gpla12_readme.md
```

What we learned from it:

- it has 684 acoustic rows
- every row has 1460 signal values
- it has 12 labels
- each label appears 57 times

This dataset is gas pipeline leakage, not water pipe leakage. So we should not
pretend it proves our water leak detector works. But it is still useful because
it shows how acoustic leakage data is shaped:

```text
raw signal values -> features -> label / score
```

That is why our demo takes hydrophone audio and calculates things like:

- RMS, which is basically sound energy
- peak, which catches loud spikes
- bandpower, which tells us which frequency ranges are active
- spectral centroid, which tells us if the sound is more low or high frequency
- leak score, which is our simple leak-like score

So GPLA-12 helped us think about the sound processing part.

### SubPipe

SubPipe is the underwater pipeline inspection reference.

In its README, the dataset structure includes files like:

```text
Acceleration.csv
AngularVelocity.csv
EstimatedState.csv
ForwardDistance.csv
Pressure.csv
WaterVelocity.csv
Temperature.csv
```

This is useful because those are close to the kind of streams our robot would
produce.

How we used that idea:

- acceleration becomes our IMU acceleration
- angular velocity becomes our gyro data
- forward distance is similar to our tether/reel distance
- pressure and water velocity are similar to our pressure/flow context

We did not download the full SubPipe dataset into this repo because the archive
is huge. We keep the README and Zenodo metadata as source proof. For the demo,
SubPipe mostly tells us what kind of underwater robot motion files are realistic.

### AQUALOC

AQUALOC is another underwater robot dataset. It is useful because the page says
the robot had a MEMS-IMU and pressure sensor, and that the data is synchronized.

So for our demo this means:

```text
it is normal for underwater robot missions to have synced IMU + pressure style logs
```

We use AQUALOC as a supporting reference for timing and sensor setup. It is not
pipe-specific, but it helps justify the idea of one mission timeline.

### WNTR / EPANET

This one is for the pipe network side.

In the repo we have:

```text
data/source_artifacts/wntr_net3.inp
data/source_artifacts/wntr_leaks.inp
data/source_artifacts/wntr_readme.md
```

WNTR/EPANET is used for water distribution networks. It works with pipes,
junctions, leaks, pressure, and flow.

What we got from it:

- pipes and junctions should be represented as a graph
- intersections should come from the pipe map, not from hydrophone alone
- leak areas should have pressure/flow context

This is why our demo has a `network.geojson` file. The robot moves along that
route, and intersections are attached to route positions.

### OceanShip

OceanShip is only used as background reference for underwater audio. We are not
replaying OceanShip clips directly in the demo.

The use is more like:

```text
underwater audio has background noise, so our hydrophone should not be perfectly clean
```

## How The Demo Mission Is Generated

The main code is here:

```text
pipeowl/mission_builder.py
```

When we run:

```sh
python3 scripts/generate_calibrated_mission.py --out data/calibrated_mission
```

it creates the whole mission folder.

## Step 1: Make A Pipe Route

We create a small pipe route:

```text
MAIN_A: 0 m to 30 m
MAIN_B: turns from 30 m toward 45 m
MAIN_C: continues to about 62 m
```

Then we add branches/intersections at:

```text
15 m
30 m
47 m
```

This route is not copied from a real city map. It is modeled. But the idea of
pipe segments and junctions comes from WNTR/EPANET.

The route goes into:

```text
network.geojson
```

## Step 2: Move The Robot Through The Pipe

The robot moves at around:

```text
0.70 m/s
```

For each time step we save:

- time
- distance
- x/y position
- heading
- speed
- pipe id
- pressure
- flow

This becomes:

```text
robot_state.csv
```

Near the leak area, the code lowers pressure and increases flow a bit:

```text
pressure change: about -0.18 bar
flow change: about +0.16 m/s
```

That is not real measured pressure from our robot. It is modeled context based
on the idea that leaks affect hydraulic behavior.

## Step 3: Generate IMU Data

The IMU file is:

```text
imu.csv
```

It has:

- ax, ay, az
- gx, gy, gz
- accel magnitude
- gyro magnitude
- jerk

Normal movement has small vibration around gravity, around:

```text
9.81 m/s^2
```

Near bends/intersections, the code increases gyro_z. That makes sense because
if the robot turns, the gyro should react.

Near the impact/tether tug event, the code adds a short acceleration and jerk
spike. That makes sense because if the robot bumps a wall or the tether pulls,
IMU should jump.

This is based on the kind of files SubPipe and AQUALOC describe:

```text
acceleration + angular velocity + timestamp
```

## Step 4: Generate Reel / Tether Data

The reel file is:

```text
reel.csv
```

It has:

- tether length
- payout speed
- tether tension

The tether length mostly follows robot distance, but with a little slip/noise.
That is more realistic than making distance perfectly clean.

Tether tension also slowly rises with distance, and it spikes near the
impact/tether tug event.

This matters a lot because otherwise every loud event might look like a leak.
In real life, the tether can cause weird events too.

## Step 5: Generate Hydrophone Audio

The hydrophone file is:

```text
hydrophone.wav
```

It is 92 seconds long at 8000 Hz.

The audio is made from a few parts:

- low pump/flow-like tones
- background noise
- leak-like hiss near the leak distance
- short click near the impact distance

The leak-like part uses higher frequencies around:

```text
2800 Hz
3400 Hz
```

Important: we are not saying every real leak is exactly those frequencies. The
point is just to create a leak-like high-frequency sound so our feature pipeline
can be tested.

## Step 6: Turn Audio Into Features

The code splits audio into 1-second windows.

Each window becomes one row in:

```text
acoustic_features.csv
```

For each second we calculate:

- RMS
- peak
- low bandpower
- mid bandpower
- high bandpower
- spectral centroid
- leak score

This is the part inspired by GPLA-12. GPLA-12 is basically acoustic signal rows
and labels, so we copied that general idea:

```text
signal -> features -> score
```

Our leak score is simple. It goes up when:

- sound energy goes up
- high/mid frequency content goes up
- spectral centroid goes up

And it gets lowered if the sound looks like one big impact click.

## Step 7: Record Events

Events are stored in:

```text
events.csv
```

Right now the demo records 6 events:

| Event | Distance | Why it appears |
| --- | ---: | --- |
| Intersection | 15 m | pipe route has a mapped branch |
| Intersection | 30 m | mapped branch plus turn behavior |
| Bend | 30 m | gyro_z and heading change |
| Impact/tether tug | 34 m | accel jump, jerk spike, tension rise |
| Possible leak | 46.55 m | leak score high, pressure drops, flow rises |
| Intersection | 47 m | mapped branch plus turn behavior |

The leak is important because it is not only audio.

The rule is more like:

```text
possible leak =
  high acoustic leak score
  + pressure/flow change
  + no big IMU impact
  + no big tether tension spike
```

For the leak event the recorded parameters are:

```text
Leak score 0.85
RMS 0.066
High band 4.18e+00
Pressure change -0.18 bar
Flow change +0.16 m/s
Accel check max 9.92 m/s^2
Tether check max 2.63 N
```

That is why the dashboard can say not just "leak", but also show why it thinks
that event matters.

## What Part Is Real And What Part Is Simulated

This is the most important bit.

Real/source-backed:

- GPLA-12 acoustic data files are real public files
- GPLA-12 labels are real public labels
- SubPipe README/metadata is real public underwater pipeline robot dataset info
- AQUALOC page is real public underwater IMU/pressure dataset info
- WNTR/EPANET files are real water-network files
- source file hashes are saved in `source_manifest.json`

Simulated/modeled:

- our exact pipe route
- robot travel path
- hydrophone wav
- IMU values
- tether values
- leak location
- event positions

So the honest explanation is:

```text
we used real datasets to understand what the streams should look like,
then generated a controlled fake mission in the same format our robot should produce.
```

## Why This Is Still Useful

This demo is useful because it lets us build the data pipeline before the
hardware is finished.

It shows:

- what files the robot should produce
- how sensor streams can be synchronized by time and distance
- how hydrophone audio can become features
- how IMU and tether data can reject false leaks
- how pipe intersections should come from the map
- how the dashboard can show event evidence clearly

So it is not proof that the robot already works in a real pipe.

But it is a pretty good illustration of the workflow:

```text
robot moves -> sensors log data -> features are calculated -> events are shown on map
```

## How I Would Explain It To Someone

I would say:

```text
We don't have our own full robot dataset yet, so we made a demo mission.
The mission is simulated, but the behavior is based on public datasets.
GPLA-12 helped us with leak-like acoustic data.
SubPipe and AQUALOC helped us understand underwater robot IMU/pressure logs.
WNTR helped us model pipe networks and intersections.
Then we put those ideas into one replay format, so the dashboard acts like it is reading future PipeOwl logs.
```

Short version:

```text
real datasets guide the patterns,
our code generates the mission,
the dashboard replays it like robot data.
```

## What We Should Not Claim

We should not say:

- this is real PipeOwl robot data
- we already proved leak detection in city pipes
- every leak has these exact frequencies
- hydrophone alone can detect intersections
- the robot is ready for real municipal use

Better claim:

```text
This is a dataset-backed simulation of the data pipeline.
It shows how PipeOwl data could be collected, processed, and displayed.
The next step is replacing the simulated streams with bench-test robot logs.
```

## Next Real Step

The next step should be simple:

```text
build a clear test pipe,
move the robot/sonde through it,
record IMU + tether + hydrophone,
make one known leak/no-leak case,
convert those logs into the same mission files.
```

If we can do that, then the same dashboard can run on our own real data instead
of the generated mission.
