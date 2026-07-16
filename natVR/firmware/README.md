# natVR EMG Firmware

ESP-IDF firmware for the Phase 1 EMG acquisition node described in the
natVR plan.

Current scope:

- 1 to 4 channel ADC1 sampling on classic ESP32
- 1 to 3 channel sampling on ESP32-C3:
  - `GPIO4` on `ADC1_CHANNEL_4`
  - `GPIO3` on `ADC1_CHANNEL_3`
  - `GPIO1` on `ADC1_CHANNEL_1`
- WiFi + SNTP + MQTT bring-up
- `exg.pill.emg.data.v1` JSON publishing at 50 ms/frame
- bounded on-device frame queue with stale-frame dropping
- periodic firmware heartbeat publishing on a separate status topic

This project is intentionally local to `natVR/`. It is the device-side producer
for the existing Python pipeline under `natVR/src/natvr/`.

## Topic mapping

The root bridge subscribes to `natKit/sending/#` and canonicalizes natVR MQTT
messages into the native natKit four-part Kafka topic format
`Type-StreamId-Serialization-Schema`. This firmware publishes:

- MQTT `natKit/sending/emg/raw/emg.raw.<device-id>`
  - becomes Kafka `Data-<stable-stream-id>-Json-ExgPillEmgDataSchemaV1`
- MQTT `natKit/sending/emg/status/device.status.<status-device-id>`
  - becomes Kafka `Heartbeat-<stable-stream-id>-Json-DeviceFirmwareStatusV1`

The status device id defaults to `<device-id>-fw` so firmware heartbeat traffic
does not collide with the classifier's runtime metrics topic.

## Default hardware assumptions

Classic ESP32 target: Adafruit ESP32 Feather V2 using ADC1 channels that remain
usable while WiFi is active:

- `ADC_CHANNEL_6` -> `A2` / GPIO34
- `ADC_CHANNEL_3` -> `A3` / GPIO39
- `ADC_CHANNEL_0` -> `A4` / GPIO36
- `ADC_CHANNEL_1` -> `D37` / GPIO37

The firmware uses the first `NATVR_ADC_CHANNEL_COUNT` entries from that list.
These map to the initial forearm channel labels:

- `flexor_a`
- `flexor_b`
- `extensor_a`
- `extensor_b`

These are all ADC1 pins exposed on the Feather V2 bottom row, which avoids the
ESP32 ADC2 vs WiFi conflict.

ESP32-C3 target: the first EXG Pill stays on `GPIO4`, which maps to
`ADC1_CHANNEL_4`. A second EXG Pill can be placed on `GPIO3`, which maps to
`ADC1_CHANNEL_3`. A third EXG Pill can be placed on `GPIO1`, which maps to
`ADC1_CHANNEL_1`.

This keeps all configured EMG channels on ADC1, which avoids the ESP32-C3 ADC2
continuous-mode caveat entirely.

Adjust the channel map in [`main/main.cpp`](main/main.cpp) before flashing if
your wiring differs.

## Build

```sh
cd /var/home/zach/code/natKit/natVR/firmware
cp main/DevConfig.hpp.example main/DevConfig.hpp
# Classic ESP32 boards:
# idf.py set-target esp32
#
# ESP32-C3 boards:
idf.py set-target esp32c3
idf.py build
idf.py -p <PORT> flash monitor
```

## Config

Set these in `main/DevConfig.hpp`:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `MQTT_BROKER_HOST`
- `MQTT_BROKER_PORT`
- `NATVR_EMG_DEVICE_ID`
- `NATVR_STATUS_DEVICE_ID`
- `NATVR_ADC_CHANNEL_COUNT`
- `NATVR_NTP_SERVER`

For ESP32-C3:

- set `NATVR_ADC_CHANNEL_COUNT 1` for `GPIO4` only
- set `NATVR_ADC_CHANNEL_COUNT 2` for `GPIO4` + `GPIO3`
- set `NATVR_ADC_CHANNEL_COUNT 3` for `GPIO4` + `GPIO3` + `GPIO1`

## Serial backup transport

When WiFi/MQTT is unavailable (e.g. a locked-down convention network), build the
serial-backup image:

```sh
idf.py fullclean
idf.py -DNATVR_TRANSPORT_SERIAL=1 build
idf.py -p <PORT> flash monitor
```

In this mode the firmware brings up **no** WiFi, NTP, or MQTT. It writes the exact
same `exg.pill.emg.data.v1` (and `device.firmware.status.v1`) JSON frames as
newline-delimited lines to the USB serial console instead of publishing them over
MQTT. Logs are quieted to error level so the frame stream stays clean.

On the host, run the companion shim to republish those lines onto the standard
MQTT topics so the bridge -> Kafka path is byte-identical to the WiFi transport:

```sh
natvr-serial-bridge --serial-port /dev/ttyACM0 --mqtt-host <broker>
```

Timestamps in serial mode come from the device's local monotonic clock (no NTP),
which is fine for a single-device capture where alignment is intra-session. If you
need cross-device time correlation, use the WiFi/MQTT transport.

## Current behavior

- ADC runs in continuous mode at `NATVR_ADC_CHANNEL_COUNT * 1000 Hz` total
  conversion rate.
- Samples are grouped into `50` samples/channel frames.
- Each frame is published as canonical `exg.pill.emg.data.v1` JSON matching the Python
  consumer schema.
- When MQTT drops briefly, frames remain queued locally up to the bounded queue
  depth.
- Frames older than `2 s` are discarded on publish so the live path does not
  replay stale EMG after reconnect.

## Limits

- This is a firmware scaffold. It has not been bench-validated on hardware in
  this repo state.
- Signal conditioning, ADC calibration tuning, and quantitative soak-test
  results are still Phase 1 hardware work.
