# Booth runbook — wireless-primary EMG with serial backup

Half-page operator card for the convention demo. The device rides WiFi/MQTT and
transparently falls back to a USB cable if the RF floor drops. Goal: the classify
pipeline stays live through an RF outage with no operator action.

## Before the floor (once)

1. **Build & flash the `AUTO` image** (wireless-primary, automatic serial fallback):
   ```sh
   cd natVR/firmware
   idf.py -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.demo" build
   idf.py -p <PORT> flash
   ```
   (Or `idf.py menuconfig` → **natVR Transport** → *Auto (wireless, serial fallback)*.)
2. **Bring up the natKit stack** on the booth laptop (see `ENVIRONMENT.html`).
3. **Leave the USB cable plugged in** from device to laptop. The wired path is the
   safety net; it does nothing until wireless drops.

## At the booth (each session)

1. Plug in / power the device. It boots wireless-first.
2. **Start the serial backup shim** (this is the host-side "serial enabled"
   switch — leave it running the whole session):
   ```sh
   natvr-serial-bridge --serial-port auto --mqtt-host <broker>
   ```
   Add `--stamp-host-time` only if you are running a device with no NTP.
3. Run the EMG quick-start flow in natKit as usual (record → train → live classify).

## Reading the active path

- **In natKit:** each device's status frame carries `transport_mode` (`wireless` /
  `auto` / `serial`) and `serial_active` (true while the wired backup is carrying
  frames). In `auto`, `serial_active` flips true during an RF dropout.
- **On the device console** (`idf.py monitor`, or the shim's logs): you'll see
  `AUTO: MQTT down -> serial fallback engaged` and `AUTO: wireless recovered ->
  serial fallback disengaged` on each transition.
- **In the shim logs:** periodic `published=… skipped_nonjson=… skipped_invalid=…
  skipped_duplicate=…`. `published` climbing = frames flowing over serial.

## What "good" looks like

- Live classify predictions keep updating in natKit throughout — including while
  you deliberately kill the AP or walk the device out of range.
- On an RF dropout, frames reappear over serial within ~2 s (the debounce), with no
  duplicate `seq_no`s reaching Kafka and no operator action.
- When WiFi/MQTT recover, the device returns to the wireless path within ~3 s.
- `skipped_invalid` stays ~0 (corrupt lines) and `skipped_duplicate` is small
  (only at the switchover seam).

## If something's wrong

- **No serial frames when wireless is down:** confirm the shim is running and found
  the port (`--serial-port auto` logs the detected device); check the cable.
- **Bumped cable:** the shim auto-reconnects; no action needed.
- **Want to force the wired path** (known-bad RF for the whole session): flash the
  `SERIAL` image (`menuconfig` → *Serial (USB backup)*) — this is a reflash, not a
  live flip.

---

## Pre-floor bench check (needs the real hardware — plan Phase 6)

Not verifiable off-device; run these on the demo kit before the floor:

- **USB-CDC throughput headroom:** stream at the full frame rate (4 channels ×
  sample rate) in `SERIAL`/fallback and watch `frames_dropped_stale` in the status
  frame. Expected to fit as-is (verbose JSON at 4 channels). *If* it back-pressures,
  the lever is a compact serial frame (small binary/CSV; the shim rebuilds canonical
  JSON so Kafka stays byte-identical) — **not** base64 (inflates ~33%), not per-frame
  deflate. Treat any encoding change as a contingency this check decides.
- **Failure drills:** kill the AP, saturate the 2.4 GHz band, unplug/replug USB,
  power-cycle the device — verify wireless-primary, clean fallback, and recovery each
  time.
- **Timestamp parity:** record a session across a WiFi→serial switch and confirm it
  reconstructs and trains without a time discontinuity that breaks windowing.
