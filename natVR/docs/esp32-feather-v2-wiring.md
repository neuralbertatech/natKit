# Adafruit ESP32 Feather V2 Wiring Notes

Date: 2026-06-11

This note locks the initial breadboard wiring target for the natVR EMG firmware
against the actual hardware in hand:

- Board: Adafruit ESP32 Feather V2, product 5400
- MCU family: classic ESP32
- Intended producer path: WiFi + MQTT + `natkit-v0-bridge`

## Why these pins

On the Feather V2, the exposed ADC1-capable pins include:

- `A2` / GPIO34
- `A3` / GPIO39
- `A4` / GPIO36
- `D37` / GPIO37
- `D33` / GPIO33
- `D32` / GPIO32

For this first pass, the firmware can use up to four inputs in this order:

1. `A2` / GPIO34
2. `A3` / GPIO39
3. `A4` / GPIO36
4. `D37` / GPIO37

These are all input/ADC-oriented pins on ADC1, so they avoid the ESP32 rule
that ADC2 cannot be read once WiFi is active.

## Initial EMG wiring map

Assuming one EXG Pill output per muscle channel:

| EMG channel | Feather pin | ESP32 GPIO | Firmware label |
|---|---|---:|---|
| Channel 1 | `A2` | `34` | `flexor_a` |
| Channel 2 | `A3` | `39` | `flexor_b` |
| Channel 3 | `A4` | `36` | `extensor_a` |
| Channel 4 | `D37` | `37` | `extensor_b` |

If you currently have only one EXG Pill, set:

```c
#define NATVR_ADC_CHANNEL_COUNT 1
```

and wire only Channel 1 to `A2`.

## Shared electrical connections

For each EXG Pill channel:

- EXG Pill `VCC` -> Feather `3V`
- EXG Pill `GND` -> Feather `GND`
- EXG Pill analog output -> assigned Feather analog pin above

All EXG Pill grounds must share the same Feather ground.

## Bring-up order

1. Start with one EXG Pill on `A2`.
2. Confirm the board stays stable on USB power with the electrode cable
   attached but not on-body.
3. Flash the firmware and verify MQTT frames arrive on
   `natKit/sending/emg/raw/emg.raw.<device-id>` and the bridge maps them to the
   canonical natKit Kafka topic for that device.
4. Add channels one at a time.
5. Only after transport is clean, move to on-body placement and recording.

## Immediate cautions

- Do not use Feather `A0`, `A1`, or `A5` for live WiFi EMG capture. Those are
  ADC2 pins on this board.
- Keep all EMG analog outputs within the Feather's 3.3 V ADC range.
- The current firmware is a transport scaffold. It does not yet apply any ADC
  calibration curve or hardware validation thresholds.

## First bring-up sequence

Once the board is wired:

1. Start the shared broker stack from the repo root:

```sh
cd /var/home/zach/code/natKit
podman compose up -d natkit-v0-kafka mosquitto natkit-v0-bridge
```

2. Configure firmware credentials:

```sh
cd /var/home/zach/code/natKit/natVR/firmware
cp main/DevConfig.hpp.example main/DevConfig.hpp
```

Set:

- `WIFI_SSID`
- `WIFI_PASSWORD`
- `MQTT_BROKER_HOST`
- `NATVR_EMG_DEVICE_ID`
- `NATVR_STATUS_DEVICE_ID`
- `NATVR_ADC_CHANNEL_COUNT`

3. Build and flash:

```sh
idf.py set-target esp32
idf.py build
idf.py -p <PORT> flash monitor
```

4. In a second shell, prepare the Python toolchain:

```sh
cd /var/home/zach/code/natKit/natVR
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
```

5. Record a short smoke capture:

```sh
natvr-emg-record \
  --broker 127.0.0.1:29092 \
  --device-id emg01 \
  --session-id feather-v2-smoke-01 \
  --max-frames 200
```

If that succeeds, the next step is a real cue-driven session with
`natvr-emg-capture`.
