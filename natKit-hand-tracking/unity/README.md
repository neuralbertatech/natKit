# Unity Workspace

Quest/OpenXR runtime for hand/forearm avatar rendering.

## Responsibilities
- Connect to data source (dev bridge or direct BLE).
- Decode hand tracking packets.
- Apply:
  - forearm rotation from IMU quaternion,
  - discrete hand pose from gesture output.
- Maintain smoothing/hysteresis to reduce pose flicker.

## First Runtime Target
- Support 5 gestures (`rest/open/fist/pinch/point`).
- Render stable forearm orientation and pose transitions in real time.
