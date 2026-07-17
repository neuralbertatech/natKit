# BLE GATT Spec (v1)

This defines the BLE interface for ESP32 hand-tracking transport.

## Roles
- ESP32: BLE Peripheral (GATT Server)
- Quest app / host tool: BLE Central (GATT Client)

## Service
- Name: `natKit Hand Tracking`
- UUID: `7fce0001-2d4b-4b9c-a0f4-58f5e9e80001`

## Characteristics

### 1) Data Notify
- UUID: `7fce0002-2d4b-4b9c-a0f4-58f5e9e80001`
- Properties: `Notify`
- Purpose: stream packet bytes from device to client.
- Content: framed packets from `docs/packet-format.md`.

### 2) Control Write
- UUID: `7fce0003-2d4b-4b9c-a0f4-58f5e9e80001`
- Properties: `Write`, `Write Without Response`
- Purpose: runtime control commands.

Control payload format:
- `opcode: uint8`
- `arg0: uint8`
- `arg1: uint16`
- `arg2: uint32`

Opcodes (v1):
- `0x01`: `START_STREAM`
- `0x02`: `STOP_STREAM`
- `0x03`: `CALIBRATE_IMU_TARE`
- `0x04`: `CALIBRATE_EMG_BASELINE`
- `0x05`: `SET_SAMPLE_RATE_HZ` (`arg2`)
- `0x06`: `SET_TRANSPORT_MODE` (`arg0`: 0 raw, 1 features, 2 gestures)

### 3) Status Read/Notify
- UUID: `7fce0004-2d4b-4b9c-a0f4-58f5e9e80001`
- Properties: `Read`, `Notify`
- Purpose: report runtime status and error counters.

Status payload (v1):
- `state: uint8` (idle/calibrating/streaming/error)
- `battery_pct: uint8`
- `link_quality: uint8`
- `dropped_packets: uint32`
- `uptime_ms: uint32`

## Connection Targets (v1)
- Preferred MTU: `185` or higher.
- Connection interval target: `15-30 ms`.
- Notification burst pacing handled by firmware transport task.

## Error Handling
- Client should watch `sequence` gaps in packet headers.
- Client should monitor `dropped_packets` from status characteristic.
- On disconnect:
  - ESP32 remains advertising.
  - Central retries connection and re-sends control state.
