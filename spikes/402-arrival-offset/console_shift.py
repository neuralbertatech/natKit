#!/usr/bin/env python3
"""Read the primary's per-node `frame shift applied` from its console (TEC-NATKIT-402).

This is the LEAF-SIDE half of the +38 ms decomposition: the primary already
computes `arrival - sampled` per node and logs it, so the split needs no firmware
change and no growth of UplinkPrimaryStatus (which is exactly 144 bytes with two
reserved, so a new field would break its static_assert and status.py's
PRIMARY_SIZEOF in lockstep).

⚠️ THE PRIMARY'S CONSOLE IS READABLE, contrary to the warning in uplink.hpp that
"the ESP32-S3 resets when its native USB console is opened AND re-enumerates".
Measured 2026-08-20: opened /dev/ttyACM4 four times and the board's uptime ran
continuously 413 -> 511 -> 2100 -> 3800 s. It does not reset. Much of that struct's
design exists to work around a constraint that no longer holds.

⚠️ REFERENCE POINTS DIFFER, and mixing them is a 90 ms error. The console figure is
measured from the FIRST of the frame's samples; arrival_offset.py measures from the
LAST. Subtract the batch span (which arrival_offset.py reports) before comparing.

⚠️ Writes each observation as it is parsed, because the first version buffered
everything and lost the lot when the run was killed a second before its dump.

  python3 console_shift.py --seconds 70 --port /dev/ttyACM4
"""

import argparse
import collections
import json
import os
import re
import statistics
import sys
import termios
import time
import tty

NODE_RE = re.compile(r"natkit-primary: node (\d+) \(")
SHIFT_RE = re.compile(
    r"frame shift applied.*?raw (-?\d+) us -> shifted (?:\(stale\) )?([+-]?\d+) us")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM4")
    ap.add_argument("--seconds", type=float, default=70.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = open(args.out, "w") if args.out else None
    fd = os.open(args.port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    node, pending, rows = None, b"", []
    try:
        attrs = termios.tcgetattr(fd)
        attrs[4] = attrs[5] = termios.B115200
        tty.setraw(fd)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        end = time.time() + args.seconds
        while time.time() < end:
            try:
                chunk = os.read(fd, 8192)
            except BlockingIOError:
                time.sleep(0.05)
                continue
            if not chunk:
                continue
            pending += chunk
            while b"\n" in pending:
                raw, _, pending = pending.partition(b"\n")
                line = raw.decode("utf-8", "replace")
                m = NODE_RE.search(line)
                if m:
                    # The shift line belongs to the node header above it.
                    node = m.group(1)
                    continue
                m = SHIFT_RE.search(line)
                if m and node:
                    row = {"dev": node, "raw_us": int(m.group(1)),
                           "shifted_us": int(m.group(2))}
                    rows.append(row)
                    if out:
                        out.write(json.dumps(row) + "\n")
                        out.flush()
    finally:
        os.close(fd)
        if out:
            out.close()

    if not rows:
        print("no frame-shift lines seen", file=sys.stderr)
        return 1
    per = collections.defaultdict(list)
    for r in rows:
        per[r["dev"]].append(r["shifted_us"] / 1000.0)
    print(f"{'device':>16}  {'n':>4}  {'median':>10}  {'sd':>8}   (ms, from FIRST sample)")
    for dev, vals in sorted(per.items()):
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        print(f"{dev:>16}  {len(vals):4d}  {statistics.median(vals):10.1f}  {sd:8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
