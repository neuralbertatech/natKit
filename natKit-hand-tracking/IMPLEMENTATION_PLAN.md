# natKit Hand Tracking Implementation Plan (ESP32 + EXG Pills + BNO086 + Quest 2)

## 1) Goal
Build a staged hand/forearm tracking system that:
- acquires 3-channel EMG (multiple EXG Pills) + BNO086 IMU on ESP32,
- classifies hand pose from EMG + IMU context,
- renders hand/forearm avatar on Meta Quest 2,
- extends natKit to support BLE transport in addition to IP-based broker paths.

## 2) Key Decisions
- Treat IMU as forearm orientation/motion cue, not absolute world position.
- Use a hybrid avatar model:
  - anchor position from Quest tracking origin,
  - forearm rotation from IMU quaternion,
  - hand pose from EMG classifier.
- Build in phases:
  1. USB/WiFi prototype first,
  2. BLE transport second,
  3. Quest standalone last.

## 3) Current Codebase Reuse
- Existing ESP32 IMU + MQTT path:
  - `natKit-IMU/embeded/src/main.cpp`
  - `natKit-IMU/embeded/include/kafkaTopic.hpp`
  - `natKit-IMU/embeded/include/ConnectionConfig.hpp`
- Existing BNO08x SPI implementation already present:
  - `natKit-IMU/embeded/include/Bno08xDevice2.hpp`
- Existing natKit schema/registry patterns:
  - `libnatkit/lib/libnatkit-core/include/libnatkit-core.hpp`
  - `libnatkit/lib/libnatkit-core/src/Registry.cpp`
- Existing BLE/NimBLE ESP-IDF patterns (reference):
  - `natMuse/main/muse_controller.c`

## 4) Target Architecture

### Device side (ESP32)
- Sensor task(s):
  - EMG sampler (3 ADC channels, fixed-rate timer).
  - IMU reader (BNO086 SPI quaternion + accel + gyro).
- Feature/inference task:
  - windowing + feature extraction (or raw window forwarding in early phases).
- Transport task:
  - publish packet stream through selected transport (`MQTT` or `BLE`).

### Framework side (natKit)
- Add transport abstraction so stream serialization is transport-agnostic.
- Keep existing topic/schema conventions.
- Add BLE transport implementation and host/client adapters.

### Runtime side (Quest)
- Unity OpenXR app:
  - receives gesture + forearm orientation stream,
  - drives rig state machine/blend tree,
  - optional Quest tracking anchor correction.

## 5) Implementation Phases

## Phase 0: Project bootstrap (2-3 days)
Deliverables:
- Create `natKit-hand-tracking` workspace structure:
  - `firmware/`, `unity/`, `ml/`, `docs/`, `tools/`.
- Add protocol/spec docs:
  - packet format,
  - BLE GATT layout,
  - calibration flow.

Exit criteria:
- Repository structure committed and build/readme stubs in place.

## Phase 1: Sensor ingestion prototype (1-2 weeks)
Tasks:
- Add EMG acquisition pipeline on ESP32 (3 EXG channels).
- Reuse `Bno08xDevice2.hpp` SPI path for BNO086.
- Timestamp and emit unified sample struct:
  - `timestamp_us, emg[3], quat[4], accel[3], gyro[3], imu_accuracy`.
- Start with USB serial logging and optional MQTT mirroring.

Exit criteria:
- Stable 10+ minute capture without task starvation/resets.
- Sample continuity/loss metrics logged.

## Phase 2: natKit schema + stream integration (1 week)
Tasks:
- Add new schemas in `libnatkit-core`:
  - `NatHandTrackingDataSchema`,
  - `NatHandTrackingBulkDataSchema`.
- Register both schemas in `Registry::createDefaultInitalizeRegistry()`.
- Add producer integration on ESP32 (analogous to `NatImu*Schema` flow).
- Add backend decoding path and simple stream viewer endpoint for new schema.

Exit criteria:
- End-to-end encode/decode verified with unit tests + one live stream test.

## Phase 3: BLE transport support in natKit framework (1-2 weeks)
Tasks:
- Introduce transport abstraction in firmware/framework:
  - `TransportType { MQTT_IP, BLE_GATT }`.
- Refactor current publish path to a common interface:
  - `ITransportPublisher::connect()/publish()/isConnected()/loop()`.
- Keep current MQTT implementation as one adapter.
- Add BLE GATT adapter:
  - ESP32 as Peripheral + Notify characteristic for data,
  - control characteristic for start/stop/calibrate/config.
- Add sequence number + chunking for MTU-safe payloads.
- Add optional host-side BLE bridge tool:
  - BLE receive -> natKit broker publish for analytics recording.

Exit criteria:
- Same payload schema can be sent over MQTT or BLE by config switch only.
- BLE packet loss/jitter observable via diagnostics topic/logs.

## Phase 4: EMG model pipeline (1-2 weeks)
Tasks:
- Data collection protocol (multi-posture, multi-session, labeled gestures).
- Baseline classifier:
  - 150-250 ms windows (start at 200 ms),
  - MAV/RMS/WL/ZC/SSC + IMU orientation features.
- Compare LDA/SVM/RandomForest.
- Export inference artifact:
  - lightweight parameters for ESP32/Quest runtime.

Exit criteria:
- Target gesture set (rest/open/fist/pinch/point) with stable confusion matrix.
- Cross-session validation report documented.

## Phase 5: Quest avatar integration (1-2 weeks)
Tasks:
- Unity app with OpenXR + Quest target.
- Runtime ingestion modes:
  - PC dev mode (Link + local socket/bridge),
  - standalone mode (direct BLE client).
- Avatar logic:
  - wrist/elbow anchor from Quest tracking origin,
  - forearm rotation from IMU quaternion,
  - hand pose from classifier with hysteresis/debounce.

Exit criteria:
- End-to-end live demo on Quest 2 with stable pose transitions.

## Phase 6: Hardening and calibration UX (1 week)
Tasks:
- Calibration flow:
  - neutral pose IMU tare,
  - EMG baseline/noise floor capture.
- Fault handling:
  - BLE reconnect, sensor timeout, dropped-packet smoothing.
- Performance pass:
  - latency budget and profiling (sensor -> avatar).

Exit criteria:
- Repeatable startup/calibration, graceful reconnects, measured latency target met.

## 6) BLE Design (Concrete v1)
- Service UUID: `natKit Hand Tracking Service`
- Characteristics:
  - `data_notify` (Notify): binary stream packets.
  - `control_write` (Write): commands (`START`, `STOP`, `CALIBRATE`, `SET_RATE`).
  - `status_read` (Read/Notify): battery, link, sample rate, dropped packets.
- Packet header:
  - `version, stream_id, seq, timestamp_us, payload_type, payload_len`.
- Payload types:
  - `raw_sample`, `feature_vector`, `gesture_output`.

## 7) Risks and Mitigations
- EMG signal instability:
  - enforce electrode placement checklist + baseline recalibration.
- ESP32 ADC noise:
  - per-channel filtering, grounding discipline, oversampling.
- BLE throughput constraints:
  - compact payloads, MTU negotiation, bulk windows, backpressure handling.
- IMU drift:
  - use orientation only + periodic re-tare + Quest anchor constraints.

## 8) First Sprint Backlog (Recommended)
1. Scaffold `natKit-hand-tracking` project folders and docs.
2. Implement ESP32 EMG 3-channel acquisition task.
3. Integrate BNO086 SPI read path from `Bno08xDevice2`.
4. Define and serialize unified hand sample packet.
5. Add logging/replay tool to inspect packet continuity and timing.

## 9) Definition of Done (MVP)
- ESP32 streams live EMG+IMU samples continuously.
- natKit can decode/store `NatHandTracking*Schema`.
- BLE transport works as a drop-in alternative to MQTT transport.
- Quest app shows forearm orientation + 5 gesture hand poses in real time.
- Calibration + reconnect flow is usable without reflashing firmware.
