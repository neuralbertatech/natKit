# ADR 001: natVR EMG to Quest architecture

Date: 2026-06-11

## Status

Accepted for initial implementation.

## Context

The EMG-to-VR hand presence project needs project-local code that builds on
natKit infrastructure without forcing EMG- and Quest-specific assumptions into
shared code too early.

The current repo already provides:

- Kafka, Mosquitto, and NTP services in `docker-compose.yml`
- a `natkit-v0-bridge` service that bridges MQTT and Kafka
- `libnatkit` C++ transport code for Kafka and Mosquitto integration

The plan constrains the MVP in a few important ways:

- the EMG output is a discrete gesture classifier first, not per-finger
  regression
- the Quest client should consume a simple WebSocket feed, not Kafka directly
- time stamps and sequence numbers must be carried end to end from device to
  renderer

## Decisions

### 1. Keep project-specific code under `natVR/`

`natVR/` is the local home for:

- EMG/VR docs and decision records
- payload schemas for the new topics
- Python bridge and classifier services
- later firmware, replay, recording, and Unity support code

Proposed layout:

```text
natVR/
  docs/
  schemas/
  src/natvr/
    bridge/
    classifier/
    tools/
  tests/
```

### 2. Topic naming convention

Use the native natKit Kafka topic format
`Type-StreamId-Serialization-Schema`. One logical stream per device or session,
one Kafka partition per stream unless measured load requires something else.

- `Data-<stable-device-stream-id>-Json-ExgPillEmgDataSchemaV1`
- `Data-<stable-device-stream-id>-Json-NatImuDataSchema`
- `Data-<stable-session-stream-id>-Json-HandStateV1`
- `Meta-<stable-session-stream-id>-Json-BasicMetaInfoSchema`
- `Status-<stable-device-stream-id>-Json-DeviceStatusV1`

### 3. EMG frame contract

The canonical payload name is `exg.pill.emg.data.v1`.

Required fields:

- `device_id`
- `seq_no`
- `device_ts_us`
- `n_channels`
- `samples_per_channel`
- `sample_rate_hz`
- `channel_labels`
- `payload` as signed `int16[ch][n]`

This is the transport contract the firmware, recorder, classifier, and replay
tool will share.

### 4. Hand-state contract

The canonical payload name is `hand.state.v1`.

Required fields:

- `session_id`
- `gesture_id`
- `confidence`
- `curls[5]`
- `source_window_start_us`
- `source_window_end_us`
- `emitted_at_us`
- optional `source_device_id`

Unity should consume curl vectors, not gesture-specific animation names. That
keeps the renderer stable if the classifier later upgrades from gesture classes
to per-finger regression.

### 5. Bridge path

Keep the embedded transport path:

```text
ESP32 -> MQTT -> natkit-v0-bridge -> Kafka
```

The existing root `docker-compose.yml` already includes `natkit-v0-bridge`, so
Phase 0 does not need a second MQTT-to-Kafka bridge implementation.

For the Quest-facing path, add a separate project-local bridge:

```text
Kafka hand.state -> natVR Python bridge -> WebSocket -> Unity
```

That bridge is intentionally narrow and only exposes the classifier output.

## Consequences

- The first usable natVR code can be built and tested before firmware and Unity
  are ready.
- Shared natKit code stays generic while the EMG/VR contracts settle.
- The Python bridge gives the Unity client a simple contract and keeps Kafka
  client complexity off Android.
