# natKit Hand Tracking

This project adds hand/forearm tracking to natKit using:
- ESP32 sensor node,
- 3-channel EMG (EXG Pills),
- BNO086 IMU,
- Meta Quest 2 runtime integration.

## Current Status
- Phase 0 scaffold complete.
- Protocol and BLE docs initialized in `docs/`.
- Binary packet contract header added: `firmware/include/HandTrackingPacket.hpp`.
- Firmware build system switched to ESP-IDF (`firmware/CMakeLists.txt`, `firmware/main/`).

## Workspace Layout
- `firmware/`: ESP32 sensor + transport runtime.
- `unity/`: Quest/OpenXR avatar runtime.
- `ml/`: dataset tooling, training, and model export.
- `docs/`: protocol, BLE, calibration, and architecture docs.
- `tools/`: bridge/replay/debug tooling.

## Immediate Next Work (Phase 1)
1. Implement 3-channel EMG acquisition task.
2. Integrate BNO086 SPI read path.
3. Emit unified sample packet (raw + timestamps).
4. Add packet logging/replay utility for validation.
