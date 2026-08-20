#!/usr/bin/env python3
"""Decompose `arrival - sample timestamp` for IMU frames (TEC-NATKIT-402).

The rig shows a steady +35..42 ms between a sample's timestamp and its arrival at
the broker. That number is AGE PLUS BIAS and the two have opposite consequences:
if it is transport age it is the live-latency figure and is already fine; if it is
a fixed timestamp bias then every recording is shifted ~38 ms against anything the
rig does not stamp itself.

⚠️ SUBSCRIBES FROM THE HOST, never `podman exec mosquitto`. Two reasons: a
subscriber inside the broker's container dies with it, and -- the point of this
ticket -- `podman exec`'s own startup cost was inside every previously reported
number. mosquitto publishes 1883 on the host, so this measures the same path a
host-side consumer would see.

⚠️ It reports a DISTRIBUTION, not a mean. A single figure cannot distinguish "every
frame is late by the same amount" (bias) from "frames are late by varying amounts"
(queueing), and that distinction is the whole question. Watch the spread and the
per-device split: a bias should be tight and identical across devices, while age
should vary with batching.

  python3 arrival_offset.py --seconds 60
"""

import argparse
import collections
import json
import struct
import subprocess
import statistics
import sys
import time

HEADER = 24
HEADER_FMT = "<HHIQQ"          # version, count, sample_rate_hz, seqNo, deviceTsUs


def sample_size(version: int):
    floats = {1: 10, 2: 13}.get(version)
    return None if floats is None else 8 + 4 * floats + 2


def subscriber():
    return subprocess.Popen(
        ["mosquitto_sub", "-h", "127.0.0.1", "-p", "1883",
         "-t", "natKit/sending/+", "-F", "%t %x"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default=None, help="write per-frame JSONL here")
    args = ap.parse_args()

    proc = subscriber()
    per_dev = collections.defaultdict(list)
    skipped = collections.Counter()
    out = open(args.out, "w") if args.out else None
    end = time.time() + args.seconds
    try:
        for line in proc.stdout:
            if time.time() > end:
                break
            # Arrival is stamped as soon as the line is read. Anything after this
            # point (hex decode, parsing) is OUR cost and must not be in the number.
            arrival_ms = time.time() * 1000.0
            topic, _, payload = line.strip().partition(" ")
            if "NatImuBulkDataSchema" not in topic:
                skipped["not-imu"] += 1
                continue
            b = bytes.fromhex(payload)
            if len(b) < HEADER:
                skipped["short"] += 1
                continue
            version, count, rate, seq, dev_ts = struct.unpack_from(HEADER_FMT, b, 0)
            ss = sample_size(version)
            if ss is None or count == 0 or len(b) != HEADER + ss * count:
                # ⚠️ Refuse rather than guess: a frame whose length disagrees with
                # its own header is exactly the case that silently produced garbage
                # before (a hardcoded sample size outliving a schema change).
                skipped[f"len-mismatch-v{version}"] += 1
                continue
            device = topic.split("-")[1]
            # ⚠️ MILLISECONDS. `ImuSample.time_ms` is documented in imu_frame.hpp as
            # "milliseconds, matching the schema's own unit" -- the envelope's
            # deviceTsUs is micros, the per-sample field is not. Reading it as micros
            # produced offsets of 1.79e12 ms and a 0.1 ms batch span for 100 Hz
            # frames: obvious nonsense, but only because the magnitudes were absurd.
            # A subtler unit error here would have looked like a plausible answer.
            #
            # The LAST sample is the newest thing in the frame, so it is the fairest
            # comparison against arrival (the first is older by the whole batch).
            last_ms, = struct.unpack_from("<Q", b, HEADER + ss * (count - 1))
            first_ms, = struct.unpack_from("<Q", b, HEADER)
            offset_ms = arrival_ms - last_ms
            batch_ms = last_ms - first_ms
            per_dev[device].append((offset_ms, batch_ms, count, rate))
            if out:
                out.write(json.dumps({"t": arrival_ms / 1000.0, "dev": device,
                                      "seq": seq, "n": count,
                                      "offset_ms": round(offset_ms, 3),
                                      "batch_ms": round(batch_ms, 3)}) + "\n")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if out:
            out.close()

    if not per_dev:
        print("no IMU frames seen", file=sys.stderr)
        print("skipped:", dict(skipped), file=sys.stderr)
        return 1

    print(f"{'device':>16}  {'n':>5}  {'median':>8}  {'mean':>8}  {'sd':>7}  "
          f"{'p05':>8}  {'p95':>8}  {'batch':>7}  {'rate':>5}")
    all_offsets = []
    for dev, rows in sorted(per_dev.items()):
        offs = [r[0] for r in rows]
        all_offsets += offs
        batch = statistics.median(r[1] for r in rows)
        rate = rows[-1][3]
        sd = statistics.pstdev(offs) if len(offs) > 1 else 0.0
        q = sorted(offs)
        p05 = q[int(0.05 * (len(q) - 1))]
        p95 = q[int(0.95 * (len(q) - 1))]
        print(f"{dev:>16}  {len(offs):5d}  {statistics.median(offs):8.1f}  "
              f"{statistics.mean(offs):8.1f}  {sd:7.1f}  {p05:8.1f}  {p95:8.1f}  "
              f"{batch:7.1f}  {rate:5d}")
    sd_all = statistics.pstdev(all_offsets) if len(all_offsets) > 1 else 0.0
    print(f"\nall devices: n={len(all_offsets)} median={statistics.median(all_offsets):.1f} ms "
          f"mean={statistics.mean(all_offsets):.1f} ms sd={sd_all:.1f} ms")
    print("⚠️ read the sd and the per-device spread, not the mean: a tight sd that is "
          "identical across devices is a BIAS; a wide one is queueing/age.")
    if skipped:
        print("skipped frames:", dict(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
