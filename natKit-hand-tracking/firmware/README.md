# Firmware Workspace (ESP-IDF)

ESP32 firmware for:
- 3-channel EMG capture (EXG Pills),
- BNO086 SPI IMU capture,
- packetization,
- transport publish (MQTT or BLE).

## Project Layout
- `main/main.cpp`: app entrypoint (`app_main`) and task orchestration.
- `main/Bno08xProvider.cpp`: BNO086 SPI + SH2 integration layer.
- `main/TransportPublisher.*`: transport abstraction + current logging adapter.
- `main/CMakeLists.txt`: component registration.
- `components/bno08x_sh2/`: SH2/SHTP stack used by BNO08x.
- `include/HandTrackingPacket.hpp`: shared packet contract.

## Build/Flash (ESP-IDF)
```bash
cd /home/zach/code/natKit/natKit-hand-tracking/firmware
idf.py set-target esp32
idf.py build
idf.py -p <PORT> flash monitor
```

## Current Bootstrap
- `SampleTask`:
  - reads EMG from ADC1 channels (GPIO36, GPIO39, GPIO34),
  - services BNO086 SH2 transport,
  - fills `RawSamplePayloadV1` with live quaternion/accel/gyro when IMU is available.
- `PublishTask`:
  - wraps payload in `PacketHeaderV1`,
  - routes packets through `ITransportPublisher`.
- Transport:
  - `LOG_ONLY` is implemented,
  - `MQTT_IP` is implemented using ESP-IDF `esp-mqtt`,
  - `BLE_GATT` is implemented with NimBLE GATT service/characteristics.

## Default BNO086 SPI Pin Map
- `SCK`: GPIO5
- `MISO`: GPIO21
- `MOSI`: GPIO19
- `CS`: GPIO15
- `INT`: GPIO32
- `RST`: GPIO14

## IMU Configuration
- BNO086 pin/rate config is now passed via `Bno08xConfig` into `imu::init(...)`.
- Defaults are in `main/Bno08xProvider.hpp` (`kDefaultConfig`).
- Board-specific overrides are centralized in `make_imu_config()` in `main/main.cpp`.

## Transport Configuration
- Transport selection is set by `kTransportType` in `main/main.cpp`.
- Transport parameters are centralized in `make_transport_config()` in `main/main.cpp`.
- `MQTT_IP` requires:
  - valid `broker_uri` (for example `mqtt://192.168.1.10:1883`),
  - topic/client ID configured in `make_transport_config()`,
  - active network connectivity (Wi-Fi/Ethernet bring-up is not yet included in this firmware).
- `BLE_GATT` requires:
  - enabling Bluetooth + NimBLE in `sdkconfig` (for example via `idf.py menuconfig`),
  - a BLE central client that subscribes to data/status notifications and writes control commands (`START_STREAM` required before data notifications are emitted).
  - implemented command effects:
    - `START_STREAM` / `STOP_STREAM`: gates publish loop output,
    - `SET_SAMPLE_RATE_HZ`: updates runtime EMG/IMU sampling loop rate,
    - `CALIBRATE_IMU_TARE`: runs a timed quaternion tare capture and applies offset to outgoing IMU quaternion,
    - `CALIBRATE_EMG_BASELINE`: runs a timed baseline capture and computes per-channel mean/std,
    - completed calibration values persist to NVS and reload at startup,
    - BLE status `state` packs calibration-valid flags (`0x10` IMU tare valid, `0x20` EMG baseline valid),
    - `SET_TRANSPORT_MODE`: runtime mode state updates (raw packet pipeline currently remains active).

## Next Steps
1. Add feature-vector / gesture payload pipelines for non-raw transport modes.
2. Add network bring-up path for standalone `MQTT_IP` mode.
3. Wire IMU tare command to BNO08x tare facilities (beyond software quaternion offset).
