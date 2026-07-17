# Calibration Flow (v1)

This document defines the minimum runtime calibration sequence for stable tracking.

## States
1. `BOOT`
2. `IDLE`
3. `IMU_TARE`
4. `EMG_BASELINE`
5. `READY`
6. `STREAMING`
7. `ERROR`

## Required Calibration Sequence

1. Enter `IDLE` after firmware startup.
2. Run IMU tare:
   - client sends `CALIBRATE_IMU_TARE`,
   - user holds neutral forearm pose for ~2 seconds,
   - firmware stores tare quaternion offset.
3. Run EMG baseline:
   - client sends `CALIBRATE_EMG_BASELINE`,
   - user relaxes hand/forearm for ~3 seconds,
   - firmware computes baseline mean/noise floor per channel.
4. Transition to `READY`.
5. Client sends `START_STREAM` to enter `STREAMING`.

## Recalibration Triggers
- User command (manual recalibration).
- IMU quality degraded for sustained period.
- EMG baseline drift detected above threshold.
- Device reboot.

## Minimum Persisted Calibration Data
- `imu_tare_quaternion[4]`
- `emg_baseline_mean[3]`
- `emg_baseline_std[3]`
- `calibration_timestamp_us`
- `calibration_version`

## Runtime Guardrails
- Do not emit gesture outputs until both IMU and EMG calibration complete.
- If calibration invalidates at runtime, downgrade to `READY` and notify client.
- Status characteristic should expose calibration validity bit flags.
