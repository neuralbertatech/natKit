# Hand Tracking Packet Format (v1)

This document defines transport-level binary packets for hand tracking data.
All multi-byte values are little-endian.

## Header (`NatHandPacketHeaderV1`)

| Field | Type | Bytes | Description |
|---|---:|---:|---|
| `version` | `uint8` | 1 | Protocol version (`1`) |
| `payload_type` | `uint8` | 1 | See payload type table |
| `header_bytes` | `uint16` | 2 | Header length in bytes (`20` for v1) |
| `sequence` | `uint32` | 4 | Monotonic packet sequence number |
| `timestamp_us` | `uint64` | 8 | Capture timestamp in microseconds |
| `payload_bytes` | `uint16` | 2 | Payload length in bytes |
| `flags` | `uint16` | 2 | Bitfield flags (reserved for v1) |

Total header size: `20` bytes.

## Payload Types

| Type | Value | Description |
|---|---:|---|
| `RAW_SAMPLE` | `0x01` | Single sensor sample (EMG + IMU) |
| `FEATURE_VECTOR` | `0x02` | Windowed features for inference |
| `GESTURE_OUTPUT` | `0x03` | Classifier output |
| `HEARTBEAT` | `0xF0` | Liveness/status heartbeat |
| `DIAGNOSTIC` | `0xFF` | Debug/telemetry payload |

## `RAW_SAMPLE` Payload (v1)

| Field | Type | Bytes | Description |
|---|---:|---:|---|
| `emg_ch0` | `int16` | 2 | Raw ADC-derived EMG sample |
| `emg_ch1` | `int16` | 2 | Raw ADC-derived EMG sample |
| `emg_ch2` | `int16` | 2 | Raw ADC-derived EMG sample |
| `quat_w` | `float32` | 4 | BNO086 quaternion |
| `quat_x` | `float32` | 4 | BNO086 quaternion |
| `quat_y` | `float32` | 4 | BNO086 quaternion |
| `quat_z` | `float32` | 4 | BNO086 quaternion |
| `accel_x` | `float32` | 4 | m/s^2 |
| `accel_y` | `float32` | 4 | m/s^2 |
| `accel_z` | `float32` | 4 | m/s^2 |
| `gyro_x` | `float32` | 4 | rad/s |
| `gyro_y` | `float32` | 4 | rad/s |
| `gyro_z` | `float32` | 4 | rad/s |
| `imu_accuracy` | `uint8` | 1 | BNO086 report accuracy |
| `emg_saturation_mask` | `uint8` | 1 | 3 LSBs indicate per-channel clipping |
| `reserved` | `uint8[2]` | 2 | Reserved (set to 0) |

Total payload size: `50` bytes.

## `GESTURE_OUTPUT` Payload (v1)

| Field | Type | Bytes | Description |
|---|---:|---:|---|
| `gesture_id` | `uint8` | 1 | Predicted class |
| `confidence` | `float32` | 4 | Confidence/probability |
| `model_version` | `uint16` | 2 | Inference model revision |
| `reserved` | `uint8` | 1 | Reserved |

Total payload size: `8` bytes.

## Transport Notes
- BLE notify packets may fragment/reassemble packet bytes depending on negotiated MTU.
- MQTT payload may carry one full packet per publish.
- Packet integrity and ordering are validated using `sequence`.

## Initial Gesture IDs (v1)

| ID | Gesture |
|---:|---|
| `0` | Rest |
| `1` | Open |
| `2` | Fist |
| `3` | Pinch |
| `4` | Point |
