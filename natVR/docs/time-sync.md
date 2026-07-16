# Time sync note

Date: 2026-06-11

## Device clock policy

- ESP32 nodes sync with SNTP on boot.
- Re-sync periodically during runtime; start with once per hour.
- Every EMG frame carries both `seq_no` and `device_ts_us`.

## Consumer policy

- Broker receive time is recorded separately from device time.
- Drift is evaluated as `broker_receive_ts_us - device_ts_us`.
- Real-time consumers should alarm on sustained drift outside `+/-5 ms` after
  transport jitter is accounted for.

## Failure handling

- Sequence gaps identify frame loss without relying on MQTT QoS retries.
- Short Wi-Fi interruptions should be absorbed by an on-device ring buffer.
- Frames older than the classifier window budget should be dropped instead of
  replayed late into the live path.

## Why this shape

This keeps timing ownership on the device while still letting Kafka-side tools
measure transport and bridge behavior. It also matches the phase plan's need to
compare device time against broker and renderer observations.
