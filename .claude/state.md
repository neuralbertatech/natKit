# Current Work State

> This file is maintained by Claude Code. Read on session start, update before session end.

**Last updated:** 2026-08-12

## Current — ⚠️ RIG IS NOT DELIVERING. Leaf healthy, primary publishes nothing.

**`f458a98` (pin bumped).** Survey **OFF by default**, channel **pinned to 3**.

**⚠️⚠️ THE ESP32-S3 RESETS EVERY TIME ITS USB CONSOLE IS OPENED.** Proven: two
opens 3 s apart both report uptime ~3.3 s. It is the **native USB Serial/JTAG**,
so leaving DTR/RTS alone (what `monitor.py` does, enough on a classic ESP32) does
NOT help. **Every "no nodes yet" / "0 samples/s" reading taken WHILE monitoring
the S3 was self-inflicted** — freshly booted, mid-survey, NTP unsynced, leaf not
re-found. **Observe the S3 through what it PUBLISHES, not its console.**
➡️ It currently publishes only kData; making it publish its status frames would
give a way to watch it without rebooting it. **That is the next thing to build.**

**✅ FIXED: the survey queued IN FRONT of the NTP window** instead of overlapping
it (first publish ~33 s → ~60 s). SNTP/MQTT now start **before** the radio:
survey 0.4–26.4 s, clock synced **32.5 s**. Genuinely free now.

**⚠️ SURVEY NOW DEFAULT OFF — IT SCORES THE WRONG SIGNAL.** It measures other
networks' 802.11 traffic; the interference that matters here is **non-802.11**
(the Thread BR board's clocks) and is invisible to a promiscuous receiver.
**Observed: it picked a channel quiet by its own table on which the leaf could not
be heard at all** (leaf: beacons at −29 dBm, clock locked; hub: "no nodes yet").
**Measuring the ACTUAL LINK works** — sweeping hub-RSSI-of-a-real-leaf gave −22 dBm
and full rate on **3 and 10**, vs −61..−83 and nothing on 9/11/13. **That is what
the survey should become.** Kept in-tree (its table correctly found Zach's two AP
clusters); the sweep is right, the scoring is wrong.

**➡️ STATE AS COMMITTED: NOT DELIVERING.** Leaf is healthy — `primary known`,
9 frames/s built, hub heard at −24 dBm — while the primary publishes **nothing at
all** (no natKit MQTT traffic on any topic). Diagnosing needs S3 visibility that
does not reboot it.

**`740ee0a` (pin bumped).** The ~33 s NTP window was dead time anyway (frames are
refused, not published with 1970 stamps), so the primary spends it surveying:
**13 channels x 2 s = 26 s**, promiscuous, scoring **ENERGY** (10^(rssi/10)) not
frame count — one loud neighbour ruins a channel that a hundred distant beacons
would not. **Leaves need no config: they already hop until they find a hub.**

**VALIDATED:** the table matches Zach's UniFi scan (its AP clusters on 6 and 11
are the scan's two clusters), and its pick (**ch 10**) measured **96 samples/s**
into Kafka.

**⚠️ FLAW FOUND BY READING THE FIRST TABLE: it was scoring OUR OWN NODES.** A
searching leaf hops, spraying ~−20 dBm across the band from centimetres away —
louder than any AP. Ch 12/13 scored **560M and 1.2B** vs a real AP's 4M, purely
from where the hop landed, so the choice would have been **effectively random**.
Now ignores frames whose transmitter is on the registry; those fell to ~900K.

**⚠️ LIMIT: it finds CROWDED channels, not NOISY ones.** Non-802.11 interference
is invisible to a promiscuous receiver — which is exactly what ruins ch 1 on this
board (its own clocks). **It complements the reciprocity check (compare the two
directions' RSSI), which found three RF faults this session.**

**Channel history on this bench:** 1 = board-jammed (−82); 6, 11 = the house APs;
3 and 10 both good (−22/−23 dBm, ~10 frames/s). `NATKIT_CHANNEL_SURVEY=y` by
default; pin `NATKIT_ESPNOW_CHANNEL` and turn the survey off to override.

**➡️ REMAINING: ~24% lost AFTER the radio** — dupes (MAC retransmission, ACKs not
returning) and the NTP boot window. **The radio is no longer the limit.**

**`3f6caf7` (pin bumped).** Rig: leaf …0644 (ttyACM0), S3 primary (ttyACM2),
…1244 powered OFF.

**⚠️⚠️ CHANNEL 3, AND THIS IS THE HEADLINE.** Zach's UniFi survey showed **APs
centred on 6 and 11**, only a weak wide signal on 1–5. Swept the hub's own RSSI:

| ch | hub hears leaf | delivered |
|---|---|---|
| **3** | **−22 dBm** | **10 frames/s** ✅ |
| 6 | −21..−57 | varies |
| 9 | −61 | 0 |
| 11 | −83 | 0 |
| 13 | nothing | 0 |
| 1 | −82 | jammed by the Thread BR board |

**1 is unusable for a BOARD reason, 6 and 11 for a SITE reason.** None of this is
a firmware property — **re-survey and re-sweep on a new site.**

**⚠️ `NATKIT_PRIMARY_ETH_UPLINK` NOW DEFAULTS ON FOR ESP32-S3.** Losing it is
SILENT: the primary comes up with **no uplink at all**, no Ethernet/MQTT console
lines, while uplink counters report frames "sent" down a UART nobody reads. Cost a
cycle **twice**, both times after `rm`-ing a generated sdkconfig.

**✅ Also fixed this round:** the leaf's main loop was a **busy spin** (orphaned
`next_sample_us` after sampling moved to its own task) — cost **81% of beacons**;
now 10%. And the broadcast-fallback theory is **dead** (49 unicast, 0 broadcast).

**➡️ REMAINING: hub receives the full 10 frames/s at −23 dBm; Kafka gets 76
samples/s.** So ~24% is lost AFTER the radio. Visible contributors: **dupes 63 of
180** (MAC retransmission — ACKs still not returning reliably) and the **NTP boot
window** (`no wall clock` 114, cumulative). **The radio is no longer the limit.**

**`7352169` (pin bumped).** Rig: **leaf …0644 on ttyACM0**, S3 primary on ttyACM2,
…1244 powered off.

**✅ FIXED — THE LEAF'S MAIN LOOP WAS A BUSY SPIN (mine).** When sampling moved to
its own task, the loop kept a deadline-aware delay computed from
`next_sample_us`, which nothing advances any more → `remaining` always 0 →
`imu.service()` called as fast as the CPU allowed, hammering SPI. **Cost 81% of
received beacons at −22 dBm** — read as a radio fault, wasn't one. **81% → 10%.**

**✅ FIXED — ESP-NOW WAS ON THE HOUSE AP'S CHANNEL.** Ch 1 is jammed by the Thread
BR board; we moved to **11, which IS the AP's channel** (measured in #373, then
forgotten). **11 → 6 took the hub's view of a leaf from −83 dBm to −21 dBm.**
Default is now **6**, with both exclusions in the Kconfig help.

**❌ REJECTED:** delivery is NOT a broadcast fallback — **49 unicast, 0 broadcast**
via `des_addr`.

**⚠️⚠️ UNRESOLVED — THE S3's RECEIVE SENSITIVITY FLUCTUATES BY TENS OF dB.** Same
leaf, same bench, steady 19.5 dBm TX, measured at the hub at **−16, −21, −57 and
−83 dBm** across one session, while the leaf's view of the hub stays a steady
**−21..−28**. **Reciprocity says a passive path cannot do that** — so it is the
S3's receive chain, or something intermittently jamming it.

**Delivery tracks it directly:** 97–101 samples/s when the hub reads −16..−21;
single digits at −57 or worse. **The firmware is not the limit at that point.**
**Diagnostic of choice: compare the two directions' RSSI** — it has now found
three separate RF faults this session.

**`3bbe775` (pin bumped).** Zach powered one leaf down to focus on a single node —
but the one still running is the impaired board.

**❌ REJECTED: the broadcast-fallback theory.** Added unicast/broadcast counting
via `des_addr` (the only place ESP-NOW preserves the distinction — both go to one
callback). **Measured 49 unicast, 0 broadcast.** Delivery is NOT riding a
fallback. Cheap to re-check now rather than argue about.

**⚠️ THE REMAINING LEAF `0c:8b:95:96:bc:4c` (…1244) HAS A ~50 dB TRANSMIT
DEFICIT.** It hears the primary at **−28 dBm** while the primary hears it at
**−78 dBm**, same distance, same instant, with its own radio reporting a full
**19.5 dBm (query ESP_OK** — a real reading, not an uninitialised counter).
**A passive RF path is RECIPROCAL**, so this is not distance, orientation or the
hub — the hub hears the OTHER leaf at **−21 dBm** from the same bench.

That also explains what looked like a state-machine bug: it latches, cannot get
unicasts acknowledged because they arrive 50 dB weak, and falls back to searching
— **three latch-and-lose cycles in 35 s**.

**➡️ USE `0c:8b:95:96:b9:f4` (…0644, ttyACM0) as the single leaf** — the one the
hub hears at −21 dBm. Treat …1244 as suspect hardware until its transmit path is
explained. **This is the second time reciprocity has identified a bad RF path**
(the first was channel 1 jamming the S3) — it is the reliable tool here.

**`a91f943` (pin bumped).** Delivery holds at **97–101 samples/s at Kafka**.

**✅ FIXED: the leaf abandoned a primary it was successfully feeding.** Rescan
triggered on consecutive SEND FAILURES — but a "failure" is just no MAC ACK, and
that happens constantly **while frames arrive** (399 failures against a hub
forwarding ~10/s to Kafka). The leaf gave up its channel and hopped for up to
**17 s**, which IS the 3–11 frames/s swing. **Now rescans on BEACON SILENCE**
(15 s), the authoritative signal — broadcasts need no ACK, so hearing them proves
the hub is there.

**❌ REJECTED (do not re-run): the weak −78 dBm second leaf is NOT stealing
airtime.** Held it in reset: **97 samples/s either way.**

**⚠️⚠️ THE REAL FAULT — THE LEAF'S LINK VIEW IS DISCONNECTED FROM REALITY.**
Over 65 s it reported **`primary known` ZERO times** (48 PRESUMED GONE, 15
SEARCHING), **52% beacons missed, 610 tx failures**, while **Kafka got a steady
97 samples/s the whole time**. Both RSSIs healthy (−21 hub, −24..−32 leaf), so
NOT path loss.

**➡️ Isolated to the UNICAST ACK PATH from the S3.** Broadcasts get through, and
when the leaf gives up on unicast it falls back to broadcast — which is very
likely why delivery survives at all. **The system works by accident.**

**NEXT STEP (two lines):** have the primary log whether each data frame arrived
**unicast or broadcast** — `des_addr` in `esp_now_recv_info_t` distinguishes them.
That settles whether delivery is riding the broadcast fallback.

**`3e6a5d5` (pin bumped).** Measured at the REAL consumer: 305 records in 30 s on
the Kafka topic the backend reads.

| stage | delivered |
|---|---|
| 50 Hz baseline | ~42 samples/s |
| 100 Hz first attempt | 30 (regression) |
| after dedupe fix | 78 |
| after deadline fix | 92 |
| **after the sampling task** | **101 samples/s** |

**⚠️ THE DOMINANT LOSS WAS THE LEAF'S SAMPLE LOOP — NOT THE RADIO.** Sampling
shared a loop with `imu.service()`; an overrunning service call cost a sample.
**15.2% of slots lost (592 of 3903) WHILE THE PRIMARY REPORTED ZERO GAPS** — the
shape of loss that gets blamed on a radio. A deadline-aware delay did NOT help
(the overrun is inside `service()`). **Sampling now has its own task** at prio 6
paced by `xTaskDelayUntil`, snapshotting already-decoded readings — no SPI, no
blocking. **Missed slots 15.2% → 0.7%.** The snapshot races service() on purpose:
a torn read mixes report axes, which is what a merged snapshot already is, and a
lock would put SPI latency back into the cadence.

**⚠️ THREE MEASUREMENT FAULTS, ALL MINE:**
1. The missed-slot counter only fired when TWO periods behind → reported **1.0%
   against an actual 15.2%**.
2. **`mosquitto_sub` UNDERSTATES delivery** — QoS 0 subscriber, broker drops for
   a slow one: showed 7.3% loss where Kafka showed 4.4%. **Measure at Kafka.**
3. **`capture.py` RESETS THE BOARD on open**, so any rate measured beside it
   starts at t=0 — inside the ~33 s NTP window where frames are refused. Most of
   the 3.3/6.8/7.8/9.2 readings were that. **Use
   `~/natkit-verification/monitor.py`** (no DTR/RTS) to watch a running board.

**Remaining:** NTP ~33 s after a primary reset (Zach: nice-to-have); the leaf↔S3
link still flaps occasionally but recovers; **`../embeded`'s own 50 Hz is #381
(TEC-NATKIT-36), explicitly only if we roll back.**

**`f11e4d3` (pin bumped).** Measured by decoding broker frames and counting
**DISTINCT seqNo** (a duplicate otherwise looks like extra data):

| stage | delivered |
|---|---|
| 50 Hz baseline | ~42 samples/s |
| after the 100 Hz change | **30** (regression) |
| after the dedupe fix | 78 |
| **after the deadline fix** | **92 samples/s** |

Leaf produces **10.1 frames/s = 101 samples/s**; broker gets **9.2/s, 0 dupes**.

**⚠️ TWO BUGS, BOTH MINE, BOTH BETWEEN SENSOR AND BROKER:**
1. **The dedupe was DECORATIVE** — the seq-tracking block sat AFTER the
   shift-and-publish, so its `return` fired once the frame had already gone to
   MQTT. Exposed by the broker showing the same seqNo **2–4× ADJACENTLY** (159 of
   362). Moved ahead of the publish → **159 → 0 duplicates**.
2. **The sample deadline drifted slow.** `next_sample_us = now + interval` folds
   overshoot into the next period, so it runs at (interval + pass time). ~22% at
   10 ms → 78 samples/s **with ZERO packet loss to explain it** — the shortfall
   that gets blamed on the radio. Now advances by a fixed interval with a
   resync-not-sprint guard. Spacing after: mean ~9.4 ms, spread 3–18 ms.

**⚠️ MEASURE THE LINK BEFORE TRUSTING A RATE.** The leaf↔S3 link was marginal for
part of this (tx failures, PRESUMED GONE, 50% beacons missed) then healed to
**0 gaps / 0 dupes / 0 retries at −23 dBm**. Source duplicates were the 802.11 MAC
retransmitting because ACKs were not returning — not a frame-path bug.

**➡️ STILL OPEN:** ~9% of frames never reach the broker (27 of 304); **NTP takes
~33 s after a primary reset and every frame in that window is REFUSED** (correct
— better than a 1970 stamp — but ~33 s of data lost per restart, worth buffering
or shortening); and **`../embeded` still samples 50 Hz while declaring 100** —
decide whether to fix it there too (affects #350's bench).

**`4d79918` (pin bumped).** Zach: "we should be hitting 100 samples per second".
He is right, and the header always said so.

**⚠️ BOTH FIRMWARES DECLARED 100 Hz WHILE SAMPLING AT 50.**
`embeded/include/BoardConfig.hpp:31` `DELAY_BETWEEN_SAMPLES 20000` vs
`kafkaTopic.hpp:32` `IMU_SAMPLE_RATE_HZ 100`. The fork copied BOTH as
"compatibility" — which was preserving a bug. **Every natKit IMU recording ever
made is 50 Hz with a header claiming 100.**

**✅ FIXED AT THE SOURCE:** sample interval **20000 → 10000 µs**, hub report
interval **18000 → 10000** with it. Hub honours it: **412 reports/s (~103 Hz
each)**; leaf builds **8–9 frames/s = 80–90 samples/s**.

**⚠️ END TO END IT IS WORSE.** Measured by decoding broker frames and counting
**DISTINCT seqNo** (a duplicate looks like extra data otherwise):

| | 50 Hz | 100 Hz |
|---|---|---|
| unique frames/s at broker | 4.2 | **3.0** |
| samples/s delivered | ~42 | **30** |

**Two faults, neither the sample rate:**
1. **DUPLICATES ~50%.** Primary receives ~18/s from a leaf building ~9. The leaf
   reports `tx failures` / `PRESUMED GONE` **while its frames plainly arrive** —
   ACKs are not getting back and **the 802.11 MAC is retransmitting BELOW
   ESP-NOW**, invisible to the leaf. Primary now DROPS `seq == last_seq` dupes,
   but **duplicates still reach the broker**, so that test is too narrow —
   **needs a WINDOW of recent seqNos**, not one value.
2. **LOSS primary → broker**: ~9 unique/s in, 3.0 published. `NOT PUBLISHED`
   counters show **`rewrite refused` climbing** = `syncStateToPrimary` declining
   frames while a leaf's fit is momentarily unsynced.

**➡️ NEXT, in order:** widen the dedupe window; **chase the fit instability**
(leaves report **+36..+39 ppm** against this S3 hub vs **−2.5 ppm** between two
ESP32s, windows refilling from ~7 pts — every reset refuses frames); then
re-measure distinct-seqNo rate. **Target 10 unique frames/s = 100 samples/s.**

## Superseded — frontend frame rate at 50 Hz: 4.2/s was correct then

**`1626c42` (pin bumped).** Zach saw 1.7–4.7 frames/s and thought it low.

**⚠️ FRAMES ARE NOT SAMPLES.** 10 samples per frame at a 20 ms interval, so
**5 frames/s = 50 samples/s IS THE DESIGN**, and the current firmware does the
same. Measured warm: **126 frames in 30 s = 4.2/s** at the broker. The frontend
reports FRAMES; "600 samples buffered" is the honest number.

**⚠️ FRAMES WERE BEING DROPPED WITH NO COUNTER AT ALL** between reception and the
uplink queue — a branch that did nothing when its preconditions failed. Now
counted three ways: `publish_no_sync`, `publish_no_time`, `publish_no_shift`.
**The wired uplink also had NO console output** (that block was gated on the WiFi
flag), so the Ethernet path was invisible.

**What it showed:** no-leaf-fit 1/5 FROZEN (startup); no-wall-clock 21/17 FROZEN
(**NTP synced only at t=33 s**, and frames before that are refused rather than
published with 1970 stamps); **rewrite-refused STILL CLIMBING ~2/s**.

**➡️ NEXT: the leaves' fits keep resetting on this hub.** They report **+36..+39
ppm** skew against **−2.5 ppm** measured between two classic ESP32s, and their
windows keep refilling from ~7 points. While a fit is unsynced,
`syncStateToPrimary` refuses the frame. That is the residual loss.

## ✅ SOLVED — CHANNEL 1 WAS JAMMING THE S3. THE ONE-CHIP WIRED RIG WORKS.

**`204a62f` (pin `2ea9ab0`).** Evidence in `~/natkit-verification/0b5f303-ethernet/`,
8 logs on #373 (95%).

**⚠️⚠️ THE ESP-NOW DEFAULT CHANNEL IS NOW 11, NOT 1, AND IT IS WORTH 66 dB.**
Same boards, cm apart, only the channel changed:

| | ch 1 | ch 11 |
|---|---|---|
| RSSI at the hub | −82 dBm | **−16 dBm** |
| data frames | 4–8 | **285 @ full 5/s** |
| seq gaps | hundreds | **12** |

Channel 1 = 2401–2423 MHz, where a 25 MHz crystal's 96th/97th harmonics land.

**✅ ONE CHIP DOES IT ALL:** ESP32-S3 = ESP-NOW hub + timing master + W5500 wired
uplink, both leaves publishing on the existing MQTT contract. No serial bridge,
no second ESP32, no radio contention.

**⚠️ THE DIAGNOSTIC LESSON, worth more than the fix.** The symptom was
ASYMMETRIC — leaves heard the hub at −25 dBm, the hub heard them at −82. **An
antenna cannot do that: a passive path is RECIPROCAL.** That is what proved it
was not the antenna. Then both TX powers were MEASURED (19.5 / 20.0 dBm, both
`ESP_OK`), leaving only "the receiver is being jammed". **MOVE CHANNEL BEFORE
SUSPECTING THE RADIO.**

Ruled out by test, not argument: W5500 (disabled it — no change), H2
co-processor (held in reset on GPIO 7 — no change; also unpowered), stale PHY
calibration (full flash erase — no change), antenna (reciprocity + Zach checked).

**⚠️ TWO BUGS THIS EXPOSED, both fixed:**
1. **A leaf that found a hub could NEVER rescan.** Moving the primary's channel
   stranded both leaves forever. Now a long failure run returns the channel to
   the search (threshold far above the retry-policy one).
2. **`esp_wifi_get_max_tx_power`'s return was ignored**, printing **"0.0 dBm"** —
   reads as a dead radio, was a failed query. Nearly derailed the diagnosis.

**#373's question is answered twice:** one chip + associated WiFi = ~85% loss;
one chip + wired Ethernet = full rate. **#348/#349 are NOT wasted** — they proved
the frame format, registry, backpressure and topic contract, and are the fallback
where there is no Ethernet. **#350 now has THREE options**, not two.

## Superseded — earlier note: BLOCKED ON THE S3's ANTENNA

**`0b5f303` (pin `bff967f`).** Evidence in `~/natkit-verification/0b5f303-ethernet/`,
5 logs attached to #373 (85%).

**✅ THE WIRED UPLINK WORKS.** One chip = ESP-NOW hub + timing master + W5500.
**Link up 2.3 s after boot, DHCP `10.26.0.31` at 3.3 s, ESP-NOW on channel 1 —
OURS**, no association to inherit one from, clean boot, heap 309 KB. New
`main/ethernet_net.{hpp,cpp}`; SNTP/MQTT/timestamp-rewrite reused UNCHANGED
because #349 split `gatewayWifiStart` from `gatewayServicesStart`.

**Pins are KNOWN-GOOD, not derived** — from Espressif's own
`basic_thread_border_router` in **`~/code/esp-thread-br`**, which Zach confirmed
working on this board: **W5500, spi host 2, sclk 21, mosi 45, miso 38, cs 41,
int 39, rst 40, 36 MHz**. Same file gives the pins to AVOID: **7/8 = H2 reset and
boot, 17/18 = H2 UART**, 19/20 = native USB, 26–32 = flash/PSRAM.

**⚠️ THE S3 BARELY RECEIVES, AND IT IS NOT ETHERNET.** 4–8 data frames against
seq in the hundreds. Three hypotheses, two KILLED BY TEST:
| hypothesis | test | result |
|---|---|---|
| W5500 / SPI | disabled the Ethernet uplink | **no change** |
| ESP32-H2 co-processor (802.15.4, mm away) | held in reset on GPIO 7 | **no change** |
| the RF path | **measured RSSI** | **−77..−87 dBm** |

**−77..−87 dBm from leaves on the same bench** (healthy close range is −30..−50),
so the receiver is **~40 dB down**. Explains the asymmetry: the S3 is HEARD fine
(leaf clocks lock, 25 µs residual) while leaf unicasts are unacknowledged
(`sent 9, tx failures 220`) — a loud transmitter and a deaf receiver.

**➡️ ASK ZACH TO CHECK THE S3's WiFi ANTENNA** (the board has two radios; the H2's
802.15.4 antenna is a different one). Everything else is ready to stream.

**⚠️ FOUR TRAPS:** `esp_event_loop_create_default()` → `ESP_ERR_INVALID_STATE` is
NORMAL once an uplink made the netif (ESP_ERROR_CHECK on it = reboot loop);
**W5500 needs `gpio_install_isr_service()` first or the link never comes up
without failing loudly**; **the W5500 has NO MAC of its own** (derived from
`ESP_MAC_ETH`); SPI-Ethernet Kconfig must live in the **shared** defaults, since
every source compiles into every image.

## Superseded — earlier note: BLOCKED on hardware details.

**Zach replaced a node with an ESP32-S3 + Ethernet daughterboard.** This is a
better answer than either architecture measured so far: **Ethernet is OFF THE
RADIO ENTIRELY**, so ESP-NOW keeps a channel we choose on a radio nobody else is
using, with no second chip bridged over serial.

**Bench is now:** ttyACM0 = ESP32 leaf **with BNO08x**; ttyACM1 = ESP32 (was the
primary, no sensor); **ttyACM2 = ESP32-S3, MAC `b8:f8:62:62:f7:3c`, device id
`203376942053180`, rev 0.2, 2 MB PSRAM**.

**Done — `5fc5fe9` (pin `9e1cbfd`): the S3 target builds and boots** as an
ESP-NOW primary/timing master on channel 1, heap flat at 321 KB, no panics.

**⚠️ THREE S3 TRAPS, each a build or boot failure rather than a note:**
1. **NO INTERNAL ETHERNET MAC.** The epic's "which PHY?" question does not apply
   — an S3 with Ethernet is necessarily an **SPI module** (W5500 / DM9051 /
   ENC28J60). Do not reach for LAN8720 on this board.
2. **Console is the native USB Serial/JTAG**, so
   **`CONFIG_ESP_CONSOLE_UART_BAUDRATE` DOES NOT EXIST** — it broke uplink.cpp
   and uplink_reader.cpp. An absent Kconfig symbol is a compile error, not a 0.
3. **The uplink pin defaults were FATAL.** The S3 has **no GPIO 22–25**, so
   `uart_set_pin` aborted with `rx_io_num error` in a reboot loop — and **GPIO
   26–32 are SPI flash/PSRAM there**, so the working half of the 26/25 pair
   would have been worse than the failing half. Now per-target: **17/18** on S3,
   clear of the native USB pins (19/20).

**⚠️ BLOCKED: need the daughterboard's chip and pinout.** Cannot be guessed —
wrong SPI pins either do nothing or drive flash lines. Need: chip
(W5500/DM9051/ENC28J60), MOSI/MISO/SCLK/CS, INT, RST.

**The remaining work is small once that lands**, because the hard parts exist:
`gatewayServicesStart()` (SNTP + MQTT) and `rewriteFrameTimestamps` are
netif-agnostic and already proven. Only `gatewayWifiStart()` needs an Ethernet
sibling.

**⚠️ ALSO FOUND: the esp32c3 target has not built since `b42d763`** (BNO08x port)
— `board_config.hpp` pins GPIO_NUM_32, which a C3 does not have. So the epic's
"all six images build" claim has been false for five slices. Filed as **#379
(TEC-NATKIT-34)**; not fixable without a C3's real wiring. **Sweep targets on
handoff:** `for t in esp32 esp32c3 esp32s3; do for r in leaf primary gateway; ...`

## Prior Task — #373 (TEC-NATKIT-30) ONE CHIP, BOTH RADIOS: 75%, answer is "use two"

**`b681fec` on natKit-IMU trunk, pin bumped (`1d65a5e`).** Evidence in
`~/natkit-verification/b681fec-onechip/`, 2 logs attached to #373.
`CONFIG_NATKIT_PRIMARY_WIFI_UPLINK=y` = primary associates + publishes itself.

**⚠️ THIS AP IS ON CHANNEL 11.** Associating drags the hub off channel 1, exactly
as predicted. So: the primary no longer calls `esp_wifi_set_channel` when the
uplink is on, **peers are now ALWAYS added on channel 0** ("follow the
interface") and **a leaf that has no hub HOPS channels** until it finds one. A
peer pinned to a channel the interface is not on is a SILENT failure — sends
succeed locally, nothing is received. The hunt works: both leaves found ch 11
unaided.

**THE RESULT — same bench, same leaves:**

| | seq gaps | per-leaf rate |
|---|---|---|
| two boards | **0** | 5.0/s |
| **one board** | **216 vs 39 received** | 0–2/s, silent 1–3.5 s |

**The leaves stay HEALTHY** (`built 213 @ 5.0/s, sent 364, dropped 0, tx
failures 0`), and unicast ESP-NOW success means a **MAC-layer ACK** — so the
primary's radio received the frames and dropped them **above the MAC**, on a WiFi
task busy servicing the association.

**⚠️ CONFOUND NOT ELIMINATED: rssi −79..−87.** A weak association means retries
and low rates, which could itself starve the receive path. **NTP never synced at
this signal, so `published 0`** — the publish half is built but unproven.
**RETEST NEAR THE AP before calling one chip impossible.** (The gateway board ran
−72..−75 and published fine — but it was only doing WiFi.)

**Either way the one-chip design inherits the site's channel, signal and
airtime**, which the two-board split does not. That is now a measured argument
for #350 rather than a design instinct. Keep it behind the Kconfig flag
regardless — it is a useful no-wire bench mode.

## ✅ CHOPPY LIVE VIEW DIAGNOSED AND FIXED — `0fb6d57` (pin `0f1f773`)

Zach reported the frontend choppier than the current firmware and guessed radio
multiplexing. **NOTHING MULTIPLEXES** — leaf and primary are ESP-NOW only and
never associate, the gateway is WiFi only and never inits ESP-NOW, and the
primary→gateway hop is a **host relay over USB** (both boards are on this
laptop; `relay.py` IS the wire). It was two defects in the gateway, both mine:

1. **WiFi power save left at the `WIFI_PS_MIN_MODEM` default**, so the gateway
   slept between AP beacons and publishes went out in bursts at beacon
   boundaries. Leaf/primary already set `WIFI_PS_NONE` (from #340) — which is
   exactly why they measured clean and it did not.
2. **`uart_read_bytes` with a 50 ms timeout in the reader.** `room` is most of
   the scan buffer so it never fills — **the timeout IS the batching interval**.
   Now 5 ms.

**Frame inter-arrival sd (200 ms nominal), before → after:**
primary 33 → 33 | relay input 88 → 89 | **broker 253 → 116 ms**.
Bursts <50 ms **34 → 0** (min gap 3 → 87 ms); stalls >400 ms **28 → 5**.

**⚠️ EVERY COUNTER SAID HEALTHY THROUGHOUT.** Reconciled frames, ~zero drops,
0 CRC failures, 0 uplink gaps. **The fault was LATENCY, never loss** — no drop
counter could have found it. Took timestamping arrivals at three points.
Tools: `~/natkit-verification/cea0421-gateway/{jitter_probe,relay_timed}.py`.

**Dominant remaining contributor is the HOST RELAY** (33 → 89 ms; loop period
median 46 ms, p90 123 ms). **Two jumper wires on GPIO 26/25 + common ground**
remove it and close the untested-UART gap on #348 AND #349.

**Filed #377 (TEC-NATKIT-33)** — expose LOGGING_LOG as a stream + frontend health
view. No such ticket existed. ⚠️ Its stated purpose was drop detection; **drops
are already ~zero and counted at every hop**, so if it is meant to explain
choppiness it must carry **per-hop timing**, not counts.

## ✅ THE FORK'S LIVE STREAM RENDERS IN THE FRONTEND (2026-08-12)

7 screenshots + manifest attached to #349 (`~/natkit-verification/cea0421-gateway/shots/`).
Stream Viewer shows `IMU / LIVE / 600 samples buffered / 4.7 per s`, a Rolling Trace of
three live accel traces, `ACCEL -0.26, 5.70, 7.86` (**|a| 9.71 m/s²**), and the
Orientation tab rendering the BNO08x fusion quaternion (`ROLL 36.2 PITCH 1.7 YAW
126.8`). **No server-side or frontend change.** No console errors, no dialogs.

**TO SEE IT LIVE YOURSELF:** the host relay must be running (there is no wire
between primary and gateway) —
`python ~/natkit-verification/cea0421-gateway/relay.py 600` — then localhost:8080
→ Stream Viewer → tick `Stream 13793649670644` → **click the `+` to expand the
card**.

**⚠️ THE CARD RENDERS COLLAPSED.** It reports `LIVE, N samples buffered, 4.7/s`
with NO trace drawn until expanded. The text alone is misleading evidence — this
is the [[feedback_verify_ui_visually]] lesson landing again, and both shots are
attached so the difference is visible.

**⚠️ Schema Inspector reads `Unavailable` for all 9 fields** while the traces
work. NOT firmware-related: the descriptor path is `accel_x.{index}` and the
resolver in `frontend/src/StreamViewer/schemaDescriptor.ts` (~line 123) handles
only numeric indices or object keys, so the `{index}` placeholder is never
expanded. Filed as **#376 (TEC-NATKIT-32)**.

## ✅ #365 RESOLVED — IT WAS THE BRIDGE, NOT THE BACKEND (2026-08-12)

Re-ran #365's exact API sequence after restarting `natkit-v0-bridge`:
**`sample_count` 340 then 350 where it saw 0**, and `get_accuracies` populated
where it was `null`. Nothing in `NatKitBackend.cpp` was touched —
`recording_thread_func` was consuming an empty Kafka topic and reporting it
honestly. #365 is at 90% in Verification.

**⚠️ THE UNDERLYING DEFECT IS NOT FIXED, only restarted. Filed as #375
(TEC-NATKIT-31).** The bridge stops forwarding with no log, no error, and a
healthy container. Seen twice today.

**THE ONE-MINUTE DIAGNOSTIC, worth reaching for before reading backend source:**
`kafka-get-offsets --bootstrap-server localhost:9092 --topic <topic>` twice,
20 s apart, against `mosquitto_sub` on the same topic. That separates "device not
sending" / "bridge not forwarding" / "backend not consuming".

**So the FORK is verified end to end**: leaf → ESP-NOW → primary → serial →
gateway → MQTT → bridge → Kafka → **the backend's own recording API**. Still
unverified for either firmware: **Parquet export** (#350's bar), the **viewer**,
two streams at once, and the physical UART wire.

**⚠️ The CURRENT firmware (`embeded`) has NOT been re-tested since the bridge
restart** — it is on no board (all three run the fork). Its #365 blocker was
infrastructure rather than firmware, so it should work, but that is untested.

## Prior Task — #349 (TEC-NATKIT-26) GATEWAY: SHIPPED, 85%, Verification

**`cea0421` on natKit-IMU trunk, pin bumped (`eac4b1e`).** Evidence in
`~/natkit-verification/cea0421-gateway/`, 5 files attached to #349.

**✅ THE FORK'S DATA REACHES KAFKA.** leaf → ESP-NOW → primary → framed serial →
gateway → MQTT → bridge → Kafka, on the existing topic contract, **no server-side
change**. Decoded OFF THE BROKER: 524 B, schemaVersion 1, sampleCount 10,
sampleRateHz 100, timestamps **2026-08-12 21:08:23** (real wall clock), samples
20 ms apart, |accel| 9.72 m/s². Steady state **139 frames in / 135 Kafka records
per 30 s** (~4.6/s), 0 CRC failures over 838 frames, heap flat ~109 KB.

**New files:** `main/gateway_net.{hpp,cpp}` (WiFi+SNTP+MQTT), `main/uplink_reader.{hpp,cpp}`
(framed serial in with resync), `gateway.cpp` rewritten, `main/DevConfig.hpp.example`.
**`main/DevConfig.hpp` is GITIGNORED and holds real credentials** — only the
gateway reads it.

**⚠️ TESTED WITH A HOST RELAY, NOT A WIRE.** No USB-to-TTL adapter and no jumper
between boards, so `/tmp/relay.py` (copy in the evidence dir) carries bytes from
the primary's USB serial into the gateway's. Everything downstream is real. **The
physical UART1 link (GPIO 26/25 @ 921600) is UNTESTED** — same gap as #348, and
two jumper wires would close both.
**Only 3 boards, so leaf B was repurposed as the gateway.** Two streams through a
gateway is untested.

**⚠️ `esp_mqtt_client_enqueue` LOSES ~78% OF THE STREAM.** It caps at ~ONE MESSAGE
PER MQTT POLL CYCLE (the outbox is drained by the client's task loop). The gateway
reported ~5/s "refused 0" while mosquitto got **1.07/s**. **Use
`esp_mqtt_client_publish`** — QoS 0 has nothing to acknowledge. Fifth counter in
this epic to measure one step off its name; caught only by checking the rate at
mosquitto AND Kafka.

**⚠️ THE BRIDGE SILENTLY STOPS FORWARDING — likely #365's cause.** Mosquitto was
receiving frames while the Kafka offset stayed FROZEN; the bridge had logged
nothing for ~3 hours. `podman restart natkit-v0-bridge` fixed it instantly.
**Check the Kafka offset is climbing before blaming the backend's recording path.**
Cross-posted to #365.

**Design:** a frame that cannot be corrected is **REFUSED, not published raw** (an
uncorrected frame is indistinguishable downstream and poisons the time axis);
timestamps patched **in place** (a decode/re-encode would be a THIRD implementation
of the encoding); ⚠️ header `deviceTsUs` is **µs** while sample time is **ms**.

**Left open:** Ethernet PHY; **the downward command path is NOT built**, so VP
calibration buttons do not reach a fork node; Parquet export is #350 and depends
on #365.

## ✅ #340, #315 and #348 ARE CLOSED — Zach approved all three 2026-08-12

All at 100% in Done. **Do not re-verify them**; the evidence is attached to each
ticket and summarised below. Epic #343 is at 70%: five of seven slices done
(#344-#348), leaving **#349 gateway** and **#350 bench-and-decide**, plus the
optional **#373** WiFi-direct stopgap.

**#349 is now DONE too (see above), so the next slice is #350 — bench the fork
against the current firmware and decide.**

**⚠️ #350's verification depends on the backend recording path, and #365 says that
path returns 0 samples while frames are on the wire.** Resolve #365 before #350
rather than during it. It is in the Ice Box and arguably mis-filed.

## Prior Task — #348 (TEC-NATKIT-25) PRIMARY UPLINK: DONE, 100%

**`d660556` on natKit-IMU trunk, pin bumped (`ef4e114`).** Evidence + manifest in
`~/natkit-verification/d660556-uplink/`, 5 files attached to #348.

**New files:** `main/uplink.{hpp,cpp}` (framed serial protocol, queue, drain task),
`main/registry.{hpp,cpp}` (NVS roster + seal), `tools/read_uplink.py` (the
host-side reader, committed).

**Measured, three boards, 3-minute soak:** 2004 frames, **0 uplink seq gaps, 0
radio seq gaps on both streams**, 339 KB of interleaved console text resynced past
with no false frames. Reconcile over an agreed window: sent 1992 / parsed 1997.
Backpressure: **22 drops at startup then FROZEN at 22 across 4318 more queued**,
0 write timeouts, heap flat. Node outage: leaf B in reset 20 s, **leaf A kept 453
frames with 0 gaps**. Registry: persists across reboot, sealed-with-empty-roster
rejects both known-good leaves by MAC, reopened it re-learns both.

**⚠️ THE PHYSICAL SECOND UART IS UNTESTED.** No USB-to-TTL adapter on the bench, so
everything ran in bring-up mode (`CONFIG_NATKIT_UPLINK_UART_NUM=0`: frames
interleaved into the USB console, host resyncs past log text). That exercises
framing/CRC/resync/registry/backpressure but **NOT** `uart_write_bytes` on UART1,
GPIO 26/25, or 921600 baud. Committed default is UART1. #349 closes this for free.

**⚠️ CONSOLE-SHARED MODE CORRUPTS BINARY WITHOUT THE LINE-ENDING FIX.**
`CONFIG_LIBC_STDOUT_LINE_ENDING_CRLF` expands every `0x0A` written to stdout into
`0x0D 0x0A`. Symptom was **"only the small frames work"** (0 data, 134 status) —
reads like a length bug, is a translation bug. Fixed with
`uart_vfs_dev_port_set_tx_line_endings(..., ESP_LINE_ENDINGS_LF)`.

**⚠️ AN UNSET `bool` KCONFIG EMITS NO SYMBOL** — cannot be read as a value; breaks
the build when off. Same shape as the `CONFIG_NATKIT_ESPNOW_CHANNEL` break. Use
`#ifdef` into a `constexpr`.

**⚠️ FOURTH COUNTER IN THIS EPIC TO MEASURE THE WRONG THING:** the reader first
compared the primary's CUMULATIVE counters against a windowed parse count, making
a healthy link look like it lost 3/4 of its traffic. Now reconciles between two
status frames. **Treat "read what the counter counts" as a standing check.**

**Design decisions:** two sequence numbers per frame (uplink's own vs the radio's
— they answer different questions); data frames forwarded **VERBATIM** with the
clock fit travelling separately in the node-status frame; registry open by default
(self-configuring), sealed to freeze a rig.

**Reassembly is DELETED, not deferred** — #346's one-frame-one-packet decision
means there is no fragment buffer to time out.

## Prior Task — #315 (TEC-NATKIT-4) COHERENCE METRIC: DONE, 100%

**`87a6830` on natKit-IMU trunk, pin bumped (`aaa5eec`).** Evidence + manifest in
`~/natkit-verification/87a6830-coherence/`, 6 files attached to #315.

**⚠️ THERE ARE THREE BOARDS NOW.** Zach added one this session; it is on
`/dev/ttyACM2`, MAC `4c:75:25:a4:45:3c` = device `84066026407228`, and **it HAS a
BNO08x** (it reads a real gravity vector). So the bench is **two full sensor
leaves + one primary**. Its MAC is a different OUI from the other two — relevant
to #343's open "is the fleet uniformly V3-02?" question.

**⚠️ BUCKETS ARE EXPOSED AS OF assistant v0.11.0.** `assistant task <id>` prints a
`bucket` line and `task update <id> -bucket "Verification"` moves one. The old
"the CLI has no bucket info" note is STALE. (Not in the list view.) #340 and #315
are both in Verification now.

**The measurement:** the primary broadcasts a `SyncMarker` every 5th beacon; both
leaves receive the SAME wavefront, each converts its own rx time with its own fit,
and the difference between their answers is the node-to-node error. **The marker
is HELD OUT of every fit** — a leaf scored on packets it estimated its clock from
would be marking its own exam.

**Result, 5.5-minute soak, 57 paired markers:**

| | A vs primary | B vs primary | **A vs B** |
|---|---|---|---|
| bias | −139 µs | −133 µs | **+0 µs** |
| sd | 35 µs | 32 µs | **16 µs** |
| excursions | 1 | 4 | **0** |

Metric: **typical 17 µs, bound 50 µs, worst 37 µs**, locked, MEASURED.

**Both of #340's predictions held, and two are worth remembering:**
1. **The bias IS common-mode and cancels** (+0 µs between leaves). Was a modelled
   claim; now an observation.
2. **Node-to-node is BETTER than either node vs the primary** (16 vs 32/35 µs),
   which combining two measurements normally would not be — the marker path never
   touches the primary's rx callback or a leaf's tx callback, only the two leaves'
   rx callbacks, same code on same silicon at the same instant.
3. **The excursions localise to the PROBE path, not the clocks** (1 and 4 there,
   0 in 57 markers). That closes #340's open thread about where they live.

**⚠️ THIS MEASURES RELATIVE AGREEMENT ONLY.** An error common to BOTH leaves is
invisible to it — correct for node-to-node, wrong for server-to-node. There is no
wall clock anywhere on this rig; #349's gateway is the only device that will ever
have NTP, and `TimeBeacon.wall_us` (0 today) is the seam. So two of #315's three
relationships are not merely unmeasured, they are not yet definable.

**⚠️ QEMU CAN NO LONGER BOOT ANY ROLE THAT STARTS THE RADIO.** `esp_phy_enable`
asserts (`phy_module_has_clock_bits`) — no PHY — and it reboots in a loop. **Not a
regression:** the primary, which has no sensor code, fails identically (control log
attached). It went unnoticed at TEC-NATKIT-21 because every role was then a stub
that never touched the radio. **state.md's old "all six images booted under QEMU"
is STALE.** QEMU is still good up to `espNowLinkStart()`.

**Side change, standing on its own: a leaf whose sensor failed now JOINS THE
RADIO** instead of idling forever, so the failure is visible to the primary rather
than only over USB. Written expecting board 3 to be sensorless; it isn't, so this
path is exercised only under QEMU and **has not run on silicon**.

## Prior Task — #340 (TEC-NATKIT-17) TIMING BROADCAST: DONE, 100%

**`6c60cec` on natKit-IMU trunk, pin bumped (`9667d9a`).** The primary is the
clock master; a leaf fits its clock to the primary's and the shift is applied by
the consumer. Evidence + manifest in `~/natkit-verification/6c60cec-timing/`,
3 files attached to #340. Moved to Verification.

**New files:** `main/time_sync.{hpp,cpp}` (the rolling least-squares fit).
`espnow_link.{hpp,cpp}` gained the wire types and both roles' halves of the
protocol; the fork's README gained a Timing section and a corrected status table.

**Measured, two boards, 5.5-minute soak:** 327 beacons, **0 missed, 0 orphaned,
0 outliers**; fit residual **25 µs rms**; locked **10.4 s** after boot; heap flat.
Sync error, measured BY THE PRIMARY: **bias −168 µs, sd 32 µs, p5–p95 spanning
98 µs**, 3 excursions of ~2 ms in ~302.

**⚠️ THE TICKET'S FIRST RECOMMENDED APPROACH IS DEAD, and this was checked before
any code was written.** `esp_wifi_get_tsf_time()` returns **0** on a station that
is not associated (documented in `esp_wifi.h`, then confirmed on hardware), and no
node in this architecture ever associates. TSF would need the primary to be a
SoftAP, which re-introduces the association the epic exists to remove.

**⚠️ THE MAC RECEIVE STAMP IS REAL BUT UNUSABLE — the opposite of what was
expected.** `rx_ctrl->timestamp` IS a hardware stamp taken below FreeRTOS, but
against `esp_timer` it scatters by **20–57 ms**, three orders of magnitude WORSE
than simply reading `esp_timer` in the receive callback (25 µs). It is kept as a
logged diagnostic; the estimator uses the software read. Do not "fix" this by
switching to the MAC stamp without re-measuring.

**The transmit side is solved by protocol, not hardware — two-step, as PTP does.**
Beacon goes out; the primary reads its clock INSIDE the send callback for that
packet; a follow-up carries that stamp. The queue delay this removes measured
**1.4–13.8 ms**, varying packet to packet — 40× to 400× the scatter we ended up
with. Reading the clock before `esp_now_send` measures the transmit queue.

**Protocol version is now 2.** `kPrimaryHere` is RETIRED (its number left burnt);
`kTimeBeacon` carries discovery too, so there is one 1 Hz broadcast, not two.
Both boards must be reflashed together.

**The leaf does NOT rewrite its timestamps.** It sends a `SyncState`; frames stay
in raw device-monotonic time and the consumer shifts. A correction baked into
stored samples cannot be undone or improved; a leaf that steps its clock emits
non-monotonic sample times mid-frame; and #318 needs the quality to travel
alongside the stream. Chain of custody: leaf time → primary time (#340) → wall
clock (#349). `TimeBeacon.wall_us` is **0 today** and is the seam #349 fills.

**⚠️ TWO INSTRUMENTS WERE WRONG FIRST, again.**
1. **The first soak's RMS read 240 µs for data whose every percentile said ~50 µs**
   — two millisecond excursions in 301 samples dominated a sum of squares. Now the
   tail is counted separately and the scatter is an **sd about the measured bias**,
   not an RMS about zero. Bias and scatter are different animals: the bias is
   common-mode and cancels between two leaves; the scatter does not.
2. **The "done when" I proposed (raw frame delta walks, corrected stays flat) DOES
   NOT WORK and cannot.** The leaf batches 10 samples spanning 200 ms and that span
   jitters, putting a **~74 ms range** on both columns, while the actual drift over
   the window is ~1 ms — three orders of magnitude too coarse for its own
   hypothesis. The frame timestamp is ms-quantised by the encoder as well. That
   line is now labelled "NOT an accuracy figure"; **the probe path replaced it.**

**Cross-check, because one number is not a measurement:** the primary also scores
each probe against a naive "sync once at startup" model. That error reached
**−745 µs over 329 s**, implying **−2.26 ppm** of crystal skew against the
regression's **−2.56 ppm** — two independent estimates agreeing to ~12%.

**⚠️ ONE HYPOTHESIS RAISED AND NOT CONFIRMED.** The excursions were expected to be
`ESP_LOGI` blocking the receive callback. The primary now measures its own console:
**it blocks its task ~87 ms every second, 111 ms worst.** At 1 probe/s that predicts
~26 collisions in 300; **3 were seen** — so the higher-priority WiFi task is largely
protecting the callback and the cause is NOT established. The 87 ms is a real
constraint on #348's serial mux regardless.

**Next, and it needs hardware we do not have: a THIRD board.** Node-to-node
coherence — what #315 actually wants — is currently *inferred* from one
leaf-to-primary figure plus the argument that the bias cancels. Two leaves on one
primary would measure it. Also untested by time: the MAC stamp's 32-bit
microsecond counter wraps at ~72 minutes.

## Prior Task — #345 (TEC-NATKIT-22) BNO08x port: STREAMING at 85%

**FIXED. `ceb8150` on natKit-IMU trunk, pin bumped (`2a00ce3`).** The port now
streams; what was left of the ticket needs hands on the board rather than more
debugging.

**Two differences from `embeded`'s Adafruit stack — found by READING it, not by
guessing — and both had to go:**
1. **MOSI was not driven at all.** `Adafruit_SPIDevice::read` memsets the buffer
   to its sendvalue (0x00) and does a FULL-DUPLEX transfer, so MOSI carries zeros
   for every clock of every read. The HAL passed `tx_buffer = nullptr`, which in
   `spi_master` means "no MOSI phase" — the pin is undriven. The BNO08x is full
   duplex, so whatever sits on MOSI while we clock a read is shifted into the
   hub's own SHTP receiver: we were feeding it garbage writes. That is what
   explains real `SH2_RESET` events with ZERO INT timeouts of ours.
2. **CS was peripheral-driven, not hand-driven.** Adafruit asserts it with
   `digitalWrite` before its transfers and releases it after (microseconds of
   setup and hold); `spics_io_num` gives a fraction of a bit-time. Now a plain
   GPIO around each whole SHTP packet.

Also, because we now do our own transfers: SPI stages through **our own
word-aligned buffers**, since sh2's rx/tx buffers are library statics with no DMA
guarantees, and the ESP32's SPI DMA writes whole 32-bit words — so a read whose
length is not a multiple of 4 can scribble up to 3 bytes past the end, which now
lands in our slack instead of sh2's state.

**Hypothesis 1 from the last session is DISPROVEN and needed no hardware.** The
working Arduino path is NOT software SPI: `main.cpp` calls `imuReader.start2()`
→ `Bno08xDevice2` → `spiClass.begin(5, 21, 19)` + `begin_SPI(cs, int, &spiClass)`,
and `begin_SPI` builds the HARDWARE-SPI `Adafruit_SPIDevice` on HSPI/SPI2 at 1 MHz
mode 3. `ImuReader::start()`, with its commented-out `spiClass.begin`, is dead
code. Do not re-open that line of enquiry.

**Measured, at rest, board undisturbed** (`~/natkit-verification/ceb8150/`,
3 files attached to #345):
- **300s soak: 106,475 reports at 357 Hz**, holding from second 3 to the end.
- **`resets 1`, `INT timeouts 2`, `spi fail 0/0`, `empty 0`, `oversize 1`** —
  every error counter still at its bring-up value five minutes in.
- **Heap flat at 290,584 B (min 290,404)**, which is the ticket's soak bar.
- Gyro calibration reaches **high** at second 8; the deferred `setCalConfig(0x07)`
  returns 0 with a 0x07 read-back, so that earlier fix carries over intact.
- Accel `-1.250 +0.797 +9.715` m/s², **magnitude 9.83** — a real gravity vector.
- Bring-up reads as a real SHTP sequence now: 276-byte advertisement on channel 0,
  control on 2, the 5-byte executable reset-complete on 1, four hub part numbers,
  then channel-3 reports with a monotonic sequence. Contrast the previous capture:
  every packet 15 bytes on channel 0, sequence jumping 198/74/208/88.

**Per-sensor rates are NOT a fork difference.** accel ~64 Hz, gyro/mag/rotation
~98 Hz against the 18000 us asked for — but `embeded`'s live path enables the same
four reports at the same `NAT_BNO08X_DELAY_BETWEEN_SAMPLES_US` of 18000, so this is
the hub's own behaviour and both firmwares get it.

**Zach ran the six-side routine (2026-08-12) and EVERY accuracy the ticket asks for
is reached:** gyro `high` at 8s, mag `low`→`medium`→**`high`** at 64s, accel
**`high`** at 71s, rotation **`medium` at 52s and `high` at 61s`**. 199s of handling,
peak gyro 5.857 rad/s (336 °/s), and the transport counters NEVER moved off their
bring-up values (`resets 1`, `INT timeouts 2`, `spi fail 0/0`, `empty 0`,
`oversize 1`), rate holding ~358 Hz.

**ROTATION ACCURACY IS NOT A DEAD FIELD — that year-old question is settled.** The
standing hypothesis was that the rotation vector's 2-bit status is never populated
on this hub, so "Rotation: Unreliable" was never a measurement. Disproven: it reads
`medium` and `high`, its float error estimate tracks it (2.86 rad unconverged →
0.109 rad calibrated), and it decays back toward `medium` when the board sits still.
It read `unreliable` because the FUSION had not converged.

**At-rest values match the current firmware exactly.** Board reflashed with
`embeded` WITHOUT being moved, so it is the same physical orientation:

| | accel (m/s²) | gyro | \|accel\| | quat |
|---|---|---|---|---|
| fork | `+0.625 -1.078 +9.727` | `0.000` | 9.806 | `+0.930 -0.040 -0.050 +0.363` |
| `embeded` | `+0.625 -1.078 +9.727` | `0.000` | 9.806 | `+0.876 -0.032 -0.055 +0.478` |

Accel and gyro identical to three decimals on every axis. The quaternion differs
only in **heading** — rotation about gravity, which depends on fusion convergence
and resets when the hub is reflashed; both are unit quaternions and both agree on
the gravity direction.

**Side effect worth knowing: `embeded` now reports rotation accuracy `medium`, where
it has historically read 0.** The fork's deferred `sh2_setDcdAutoSave(true)`
persisted the six-side calibration into the hub's own FLASH, so the shipped
firmware inherited it with no change to `embeded`.

**#345 is at 95% in Verification.** The only residual is a genuinely *simultaneous*
under-motion comparison, which one board cannot give (two firmwares cannot run at
once, and two different motion windows are not the same measurement).

**✅ THE BOARD IS BACK ON THE CURRENT FIRMWARE AND STREAMING AS FOUND** — verified
after the rollback: 524-byte frames to
`natKit/sending/Data-13793649670644-Binary-NatImuBulkDataSchema`, `seqNo` advancing.
Reflash the fork with `./build-role.sh leaf esp32 -p /dev/ttyACM0 flash`; roll back
with `cd natKit-IMU/embeded && pio run -e release -t upload --upload-port /dev/ttyACM0`
(~29s incremental; do NOT `fullclean` first, that forces a 25-minute network
re-fetch). A byte-exact 4 MB pre-flash dump is at `~/natkit-verification/598a800/`.

**⚠️ `--upload-port` is now REQUIRED — two boards are connected.** PlatformIO
auto-picked `/dev/ttyACM1` (the second node) for the rollback upload. It failed to
connect rather than flashing the wrong board, but do not rely on that.

**⚠️ NEW DEFECT FILED: #365 (TEC-NATKIT-28).** The backend's own route for reading
decoded samples — `set_streams` → `start_recording` → `get_session_data` — returns
**0 samples while frames are visibly flowing on the wire**, and `stop_recording`
reports `"sample_count":0` with `"status":"success"`. `/api/get_accuracies` was
`null` throughout, consistent with the same cause. **So do not use that path to
verify IMU values**; decode off MQTT instead
(`~/natkit-verification/ceb8150/decode_frame.py`, written from
`NatImuBulkDataSchema::encodeToBytes`, not guesswork).

**Two hardware-handling traps:**
- **Handling the board re-enumerates the USB device** and killed a capture outright
  (the same hazard that wedged `/dev/ttyACM0` in an earlier session). `capture.py`
  now reopens the port WITHOUT pulsing reset and marks the gap in the log.
- **A rate measured over serial is only meaningful while the host is draining the
  UART.** In the aborted run the reported rate fell 360 Hz → flat 63.9 Hz eight
  seconds before the USB dropped, with every transport counter clean: the console is
  in the sample loop's critical path, so once the host stops reading, `ESP_LOGI`
  blocks on a full FIFO and throttles the loop. Not a sensor regression.

**Capture harness:** `~/natkit-verification/ceb8150/capture.py <seconds> [port]`
resets the board and streams its console in ONE process — two readers splice the
byte stream into plausible-looking interleaved lines and cost three captures last
session.

## Also done 2026-08-12 — #347 (TEC-NATKIT-24) LEAF NODE: shipped, 95%, Verification

**`9643900`.** Evidence + manifest in `~/natkit-verification/9643900-leaf/`, 6 files
attached to #347. Two boards: leaf (with the BNO08x) on `/dev/ttyACM0`, primary on
`/dev/ttyACM1`.

**New files:** `main/imu_frame.{hpp,cpp}` (canonical frame encoder),
`main/espnow_link.{hpp,cpp}` (the whole networking surface), `main/leaf.cpp`
rewritten, `main/primary.cpp` now a working receiver.

**Measured:** sensor ~360 reports/s with `resets 1` and heap flat at 210108 B;
**5.0 frames/s** of 524 B (10 samples, 100 Hz declared) = **2.6 KB/s** on air
against #346's 2.5 KB/s budget; primary sees `gaps 0`, `dupes 5`, `restarts 1`
(a reflash) over 347 frames.

**Primary-outage test passes.** `outage.py` holds the primary's EN low for 30s
(its power switch is not reachable; the radio cannot tell the difference). Frames
built kept climbing at 5.0/s, the sensor held ~360 reports/s, sends froze, and the
link **recovered unaided**.

**⚠️ Design changed BY that measurement:** three-attempt retry burned **322 retries**
in a 30s outage (~16s of radio time on a peer known to be gone — airtime other nodes
need). After 5 consecutive failures the leaf now presumes the hub absent and sends
once per frame: **322 → 10 retries**.

**⚠️ `dropped 0` in an outage is NOT evidence the queue works.** At 5 frames/s the TX
task keeps up even while every send fails, so the queue never fills. Proven instead
with a throwaway build (2000 us interval, 1 sample/frame, depth 2, deleted after):
`built 6013 @ 221.8/s, sent 5984, dropped 47` — overflowed, dropped the oldest, loop
undisturbed. Also shows ~222 small frames/s ≈ 17 KB/s.

**⚠️ TWO COUNTER BUGS, one self-inflicted, both the probe's shape again.** (1) The
primary reported `restarts 315` against 320 frames because splitting "duplicate" out
of `else if (seq <= last)` left the ordinary `seq == last + 1` falling into the final
else — the expected case is now spelled out first and does nothing. (2) Leaf link
counters were named `frames_*` while counting packets of every type, so "frames built
271, sent 307" read as sending more than were built; renamed `packets_*`.
**Before quoting a counter, check what it counts.**

**⚠️ THREE THINGS THE NEXT SLICES MUST NOT GET WRONG:**
- **Leaf timestamps are MONOTONIC SINCE BOOT, not wall clock** (no NTP by design).
  A gateway publishing them unmodified would advertise 1970-era timestamps. #340's
  job; the frames are honest about carrying device-relative time.
- **`imu_frame.cpp` is a SECOND implementation of libnatkit-core's Binary encoding**
  (a leaf linking a C++ schema library is not the lean node being tested). Pinned by
  static_asserts and verified on the wire, but it CAN drift — if libnatkit-core's
  encoding changes, this changes with it and the frame version moves.
- **`dupes 5` of 347 (~1.4%) are real** — the retry path re-sends a frame whose send
  callback was late but which had landed. The primary counts and does NOT dedupe;
  dedupe by seqNo belongs on #348 where the sequence is already tracked.

`primary.cpp` is a working receiver but explicitly NOT #348: no persistence, no
MAC-to-stream-id mapping, no serial mux, no backpressure. Its 1s beacon is what
#340's timing broadcast should REPLACE rather than sit alongside.

## Also done 2026-08-12 — #346 (TEC-NATKIT-23) loss run: ZERO LOSS, 95%, Verification

Zach connected a **second board** (its power switch had been off — that is why it
enumerated a USB-serial bridge while the ESP32 behind it never answered esptool).
`6a2c123`; evidence + manifest in `~/natkit-verification/6a2c123-espnow/`, 3 files
attached to #346.

**⚠️ THE INSTRUMENT WAS WRONG FIRST, and this is the part worth not re-learning.**
The first run reported **3051 sequence gaps from 243 packets**, which reads as
catastrophic loss. It was not loss — it was three defects in the probe:
1. `measureSendRate` used the loop index as the sequence, so each run restarted at
   0 and the runs were indistinguishable to the receiver.
2. **That index advanced even when `esp_now_send` REJECTED the frame.** Flat out,
   340 of 500 are refused at the API, so the receiver saw seq jump 12 → 393 and
   counted ~380 "gaps" for frames never transmitted — **back-pressure reported as
   packet loss**, in the one run where loss is the question.
3. The sweep wrote the payload SIZE into the sequence slot ("harmless here" — it is
   not, once a receiver is listening).
Fixed: one monotonic sequence per run advanced ONLY on acceptance; the receiver
counts **sender restarts** (sequence going backwards); the sender prints the
expected receive count so loss is a subtraction, not an inference.

**`espnow-probe-receiver` is now a first-class build target**
(`./build-role.sh espnow-probe-receiver esp32`), NOT a hand-edited sdkconfig —
ESP-IDF reads the defaults only when the generated sdkconfig does not exist yet, so
flipping that switch by hand silently gives a second SENDER, and two senders with no
receiver look exactly like total loss.

**The numbers, two PICO-V3-02 on channel 1:** sweep 1→**1470** all accepted,
**1471** → `ESP_ERR_ESPNOW_ARG` (ceiling now confirmed on a SECOND, independent
board); at IMU rate 50 × 524 B in 10.20s = 4.9 frames/s, **2.5 KB/s**; flat out 160
of 500 accepted (340 refused at the API), 180.9 frames/s, **92.6 KB/s**; receiver
**219 of 219, `seq gaps 0`, last seq 218**. Both boards report ESP-NOW **version 2**.

**Both boards are ESP32-PICO-V3-02 rev v3.0** (`0c:8b:95:96:b9:f4` = 13793649670644,
`0c:8b:95:96:bc:4c` = 13793649671244) — two for two, which is evidence for #343's
open "is the fleet uniformly V3-02?" question.

**Left on #346, neither blocking the decision:** `esp_now_get_version()` on a **C3**
(neither board is one; significance dropped since the worry was a **v1** primary and
both boards we have are v2 — it only matters again if a C3 becomes a leaf/primary),
and **contention between several SENDING nodes**, which needs N+1 boards and belongs
on **#348** since it is about hub capacity, not frame format.

## Background — #346's earlier measurement (`e7894ca`)

**The epic's "biggest unknown" was already dead at 75%.** Both numbers
the epic reasoned from were wrong, and measuring them removed the problem:
- **The frame is 524 bytes, not ~5 KB.** `NatImuBulkDataSchema` Binary encodes
  `24 + 50 * sampleCount`; the running firmware sends 10 samples, and the live
  console prints `Bytes Encoded 524`. The 5 KB figure was the legacy 5000-byte
  fallback or the 16 KB MQTT buffer.
- **ESP-NOW on this PICO-D4 is version 2 with a ceiling of exactly 1470 bytes**
  (1470 confirmed, 1471 → `ESP_ERR_ESPNOW_ARG`). Probed, not read off a header.
- At the real IMU rate: 50/50 frames confirmed, 0 failures, 2.5 KB/s. Flat out:
  177.8 frames/s (91 KB/s), excess **refused at the API** — explicit
  back-pressure, no silent loss. ~35× headroom.
- **DECIDED and on the ticket: the NODE builds the canonical frame, one frame =
  one packet.** No fragmentation, no reassembly state on the primary, loss
  degrades to whole missing frames that `seqNo` already makes detectable.
- Serial budget also fine: 2.5 KB/s per node vs ~11.5 KB/s at 115200 ≈ 4 nodes
  (~35 at 921600). natVR's stall was 19 KB/s of JSON — a different regime.

**Still open on #346, both needing hardware I don't have:** `esp_now_get_version()`
on a **C3** (a v1 primary would break the decision — v1 devices cannot receive v2
packets >250 B), and the multi-node loss run. **The harness is committed and
ready:** `./build-role.sh espnow-probe esp32` for the sender, a second board with
`CONFIG_NATKIT_ESPNOW_PROBE_RECEIVER=y` on the same channel for the receiver,
which reports **sequence gaps** (4-byte seq in every packet), not just a count.

⚠️ **The probe commit `e7894ca` broke the other three roles' builds; fixed in
`dd543d6`.** `CONFIG_NATKIT_ESPNOW_CHANNEL` was `depends on NATKIT_ESPNOW_PROBE`,
so the symbol vanished whenever the probe was not selected — while
`espnow_probe.cpp` reads it as a VALUE and compiles into every image by design.
Leaf, primary and gateway all failed with "was not declared in this scope"; only
the probe role built. Un-gated rather than wrapping the file in `#if`, because
compiling every source into every image is the invariant that stops a role from
rotting. All four roles build for esp32 again from a cleared sdkconfig.

⚠️ **`Blocked` is now stale on BOTH #345 and #346 and the CLI still cannot remove
a label** — `task update -label -Blocked` 401s (adding works). **Both need
clearing in the web UI.** #347 is correctly labelled.

## Superseded — #345's earlier WIP state (40%, NOT streaming)

Kept because the hypotheses it rules out are still worth not re-testing; the
fix is in the Current Task section above.

**Committed `b42d763` on natKit-IMU `trunk`, deliberately as WIP.** The board was
restored to `embeded/` afterwards and verified streaming, so hardware is safe.

**Works on hardware:** the hub answers (4 product ids); `sh2_getCalConfig` reports
**0x05 (accel=1 gyro=0 mag=1)**, the same value the Arduino firmware sees, so the
port reads the hub correctly; accelerometer reads `+0.051 -5.371 +8.184` m/s²
(**magnitude 9.76** = a real gravity vector); **the ticket's calibration fix
works** — deferred `setCalConfig(0x07)` returns 0 with a 0x07 read-back and gyro
accuracy reached **high**; heap flat over 40s.

**Does NOT work:** sustained streaming. A few reports arrive, then the hub
**resets itself ~10× in 40s** (real `SH2_RESET` events, with ZERO INT timeouts of
ours), and reads return 15-byte SHTP **channel-0** packets instead of the
**channel-3** sensor reports that were enabled. **The fault is in the transport,
not the decode.**

**Two findings that contradict #345's "port the fixes verbatim" advice:**
1. **`setCalConfig` must NOT be called in setup on this fork.** On Arduino it
   fails there harmlessly (`SH2_ERR_HUB`); here it SUCCEEDS, and a succeeding
   early call is the documented way to wedge this hub — observed exactly that
   (returned 0 → hub stopped asserting INT → next op -5 → stream dead after 2
   reports). Timing, not code: Arduino starts the IMU after WiFi/MQTT, a leaf gets
   there ~350ms after power-on. The SHTP *pumping* the old note calls
   "load-bearing" is kept explicitly; the write is deferred to the sample loop.
2. **The Adafruit two-CS-framed read does not port.** It relies on the hub
   re-presenting an unread packet after CS deasserts; literally ported it gave a
   byte-shifted stream (17,593 reads, 0 errors, all "15 bytes, channel 0", seq
   jumping 198/74/208/88). Now one continuous CS assertion
   (`spi_device_acquire_bus` + `SPI_TRANS_CS_KEEP_ACTIVE`) covers header + body.

**Next hypotheses, in order:** (1) whether the Arduino build actually drives
**software** SPI — `platformio.ini`'s pinned-BusIO comment says BusIO 1.17.3/4's
rewrite "lands in the exact software-SPI transfer path `begin_SPI()` drives",
which would mean the working timing is not what I reproduced; (2) SPI mode/clock;
(3) CS-to-clock and inter-transfer setup times, the class of thing the
two-transaction read was accidentally providing.

**Diagnostics are committed and are what this needs:** `Bno08x::halStats()`
counts reads, packets, empty/oversize headers, per-phase SPI failures and INT
timeouts, and records the last packet's length, channel and sequence; the leaf
prints all of it once a second with the INT level. Captures in
`~/natkit-verification/b42d763/` (3 attached to #345).

⚠️ **Reflashing the fork takes the IMU node off the air.** Rollback is `cd
embeded && pio run -e release -t upload` (~29s incremental) and a byte-exact 4 MB
pre-flash dump is at `~/natkit-verification/598a800/`.

## Prior Task — EPIC #343 slice 0 DONE and hardware-verified (#344 CLOSED)

**#344 (TEC-NATKIT-21) is CLOSED at 100%** — commits `598a800` (scaffold),
`880a042` (config corrected from what the board reports), `84ed628` + `a4952cb` +
`59cb34a` (READMEs).

**MERGED TO TRUNK 2026-08-11 (Zach's call — "we are using a separate code
path").** natKit-IMU `trunk` is now `59cb34a` and **the parent repo's pin is
bumped to it** (`e32af4e`), so `natKit-IMU/firmware-idf/` is in a default
checkout — which is what #344 wanted (both firmwares in one checkout). The
`firmware-idf-fork` branch still exists and is identical to trunk; it is now
redundant and safe to delete. Nothing is pushed — both repos are local-only.

Why the merge was safe, verified not assumed: `git diff trunk..fork` was **971
insertions, 0 deletions**, nothing under `embeded/`, and the only file outside
`firmware-idf/` was natKit-IMU's own README. Re-verified AT trunk after
merging: `embeded/` builds (`pio run -e release`, SUCCESS) and all three fork
roles build.

The fork is a sibling directory `natKit-IMU/firmware-idf/` — native `idf.py`, no
PlatformIO, `natVR/firmware` as the template.

- **Role is a Kconfig choice** (`main/Kconfig.projbuild`:
  `CONFIG_NATKIT_ROLE_{LEAF,PRIMARY,GATEWAY}`), so it is three images from one
  tree rather than a hand-edited `#define`. `main.cpp` logs the banner (firmware
  + version, role, target/rev/cores/IDF, device id + MAC, reset reason, heap),
  inits NVS, then dispatches to `runLeaf/runPrimary/runGateway`; each stub logs
  which slice fills it in and falls into `idleStatusLoop` (uptime + free heap
  every `CONFIG_NATKIT_STATUS_LOG_INTERVAL_S`, default 10s) so an unimplemented
  role is a visibly-alive board, not an apparently-bricked one.
- **`./build-role.sh <role> [target] [idf.py args]`** is the reproducible path:
  each (role, target) gets its own build dir AND its own generated `sdkconfig`
  (`-D SDKCONFIG=`), because a shared `./sdkconfig` is how one role silently
  inherits another's config. Plain `idf.py build` still works and gives the leaf.
- **All three role sources compile into every image** even though one entry
  point is called — conditional registration would leave two roles never
  compiled in any given build.
- `sdkconfig` and `dependencies.lock` are **gitignored** (both bake in the
  target; the lock rewrites itself on every alternate-target build). The
  committed truth is `sdkconfig.defaults[.esp32|.esp32c3]` +
  `roles/*.defaults`.
- **Device-id compatibility is pinned at compile time.** `packMac` is
  `constexpr` and `device_id.cpp` static_asserts the real board
  (`0c:8b:95:96:b9:f4` → `13793649670644`, the number inside every existing
  topic name). Verified the assert FIRES by sabotaging a shift and rebuilding —
  an untested guard is decoration.

**Verified — Zach plugged the node in mid-session, so this is on real silicon.**
All 6 images (3 roles × esp32/esp32c3) build clean, ~`0x2c110` bytes on esp32 /
~`0x2db40` on esp32c3 against the default 1 MB app partition (83% free); each
build's generated `sdkconfig` really carries its `CONFIG_NATKIT_ROLE_*` (a
fragment that failed to apply would still have built). On the board
(**ESP32-PICO-V3-02 rev v3.0, MAC `0c:8b:95:96:b9:f4`**, `/dev/ttyACM0`) the leaf
image boots and logs the full banner — `natKit-IMU-idf v0.1.0`, `role: leaf`,
`target: esp32 rev 3.0, 2 core(s)`, `device id: 13793649670644`, `last reset:
power-on` — with **heap flat at 297112 B across 40s**.

**The rollback contract is proven, not just documented.** `pio run -e release -t
fullclean` + rebuild (25m07s, SUCCESS) then `pio run -e release -t upload`
brought back `natKit-IMU v0.5.0` / `Unique ID: 13793649670644`, NTP synced and
**streaming** to `natKit/sending/Data-13793649670644-Binary-NatImuBulkDataSchema`.
**The board was left running the original firmware, streaming as found.**
Evidence + a full 4 MB pre-flash dump: `~/natkit-verification/598a800/`
(`MANIFEST.md`; 4 files attached to #344).

**QEMU worked at TEC-NATKIT-21 — Zach installed `libslirp` mid-session, so all six
STUB images had been booted, not just built. ⚠️ NO LONGER TRUE for any role that
starts the radio; see the #315 section above.** leaf/esp32 on silicon; primary/esp32,
gateway/esp32 and leaf/esp32c3 under QEMU (`./build-role.sh <role> <target>
qemu`). The C3 reports `rev 0.3, 1 core(s)`, confirming the packed-`MXX`
revision handling on a second target. Caveats, all in the fork's README:
- Use the **plain `qemu` action, NOT `qemu monitor`** — the monitor refuses to run
  without a TTY, while `qemu` alone uses `-serial mon:stdio`, so
  `timeout 40 ./build-role.sh <role> <target> qemu </dev/null` is scriptable.
- **QEMU's efuse is blank**: MAC `00:00:00:00:00:00`, device id `0`. An emulator
  artifact — do not "fix" it. The real id is only observable on silicon.
- No BNO08x, no ESP-NOW peer, no UART peer emulated, so #345/#346 need the bench.

**Traps found while doing it:**
- ⚠️ **ESP-IDF reads `sdkconfig.defaults*` ONLY when the generated `sdkconfig`
  does not exist yet.** Editing the defaults after the first build silently does
  nothing: the build succeeds and the setting is absent from the image. Caught
  only by reading the generated `sdkconfig` back — a flash option had been
  "applied" for two builds. `build-role.sh` now warns when a defaults file is
  newer than the generated `sdkconfig`; fix is `rm build/<target>-<role>/sdkconfig`.
- ⚠️ **Read the serial port from exactly ONE process.** Two readers split the
  byte stream into plausible-looking interleaved output (half of one line spliced
  into another), which reads exactly like a firmware bug. Cost three captures.
  Reset + read in a single process (`/tmp/esp-boot-capture.py` pattern: pyserial,
  DTR low / pulse RTS, then read).
- **The board is NOT the 4 MB PICO-D4 the epic assumes** — it is a PICO-V3-02
  with 8 MB flash and 2 MB PSRAM. Flash size is still declared 4 MB on purpose
  (under-declaring wastes space; over-declaring on a real 4 MB part breaks a
  boot), and the open question "is the fleet uniformly V3-02?" is on #343.
- Flash is a **Boya** part; it was falling back to the generic driver on every
  boot until `CONFIG_SPI_FLASH_SUPPORT_BOYA_CHIP=y`.
- `esp_chip_info_t` has **no `full_revision`** in IDF 5.5.3; `revision` is packed
  `MXX` (major × 100 + minor), so this PICO-V3-02 reads `301`.
- **`main` does not get every component's headers implicitly** — `esp_timer.h`
  was "No such file or directory" until `esp_timer` went into `REQUIRES`.
- `pio run -t fullclean` on `embeded/` forces a **network re-fetch** of the
  pinned git deps (libnatkit-core and its nested submodules) plus an
  Arduino-from-source rebuild: **25m07s measured**. The rollback is one command,
  but after a fullclean it is a slow one — do not fullclean if rolling back in a
  hurry, and note that for ~25 min this session the documented rollback was not
  actually available, which is why the 4 MB flash dump was taken first.

**Two READMEs, deliberately split:** `natKit-IMU/README.md` gained the
authoritative "there are two firmwares" section — which image is on which board
(a record to update when you flash, not a measurement), and the one rollback
command (`cd embeded && pio run -e release -t upload`).
`natKit-IMU/firmware-idf/README.md` carries the fork's build/config/invariants.

**Rollback is unchanged by the merge** — `embeded/` is byte-identical to what it
was at `635d86e`, so `cd embeded && pio run -e release -t upload` is still the one
command, and the epic's "the current firmware must stay flashable" constraint
still holds with both trees on one branch.

**Next slice: #345 (TEC-NATKIT-22)** — BNO08x on native IDF (`spi_master` + CEVA
`sh2`), carrying the five hardware-found fixes listed on that ticket. Then #346
(TEC-NATKIT-23), the on-air frame format, which is the epic's biggest unknown.

## Board — EPIC #343 filed 2026-08-10 (ESP-IDF firmware fork)

**#343 (TEC-NATKIT-20), the board's first EPIC**, with 7 child slices #344–#350:
a **fork** of the ESP32 node firmware on native ESP-IDF that changes the
architecture to primary/secondary per the #319 whiteboard — leaf nodes are sensor
+ ESP-NOW only (no WiFi/MQTT/NTP), a primary is the ESP-NOW hub and 1s timing
master, and it forwards over serial to a gateway ESP32 on WiFi/Ethernet that
speaks the existing MQTT topic contract.

Zach's constraint, which shapes every slice: **the current firmware must not be
overwritten** — we may not keep this. So `natKit-IMU/embeded` (`trunk` @
`635d86e`, Arduino via pioarduino / IDF 5.5.5, board `pico32`) stays buildable and
flashable throughout, the fork is recommended as a sibling directory
(`natKit-IMU/firmware-idf/`, native `idf.py`, `natVR/firmware` as the template),
rollback is one documented command, and #350 is an explicit adopt-or-discard
decision with measured criteria.

Slice order: #344 scaffold → #345 BNO08x on native IDF (spi_master + CEVA sh2,
carrying the hardware-found fixes) → #346 **on-air frame format** (the biggest
unknown: ~5 KB bulk frame vs ESP-NOW's per-packet limit → fragment or shrink;
measure on our chips) → #347 leaf → #348 primary (registry, reassembly, serial mux,
backpressure) → #349 gateway (WiFi/Ethernet, esp-mqtt, `esp_netif_sntp`) → #350
bench vs the current firmware and decide.

Open questions left for Zach, deliberately not decided: primary and gateway as one
board or two; which chip/PHY for the gateway's Ethernet; and whether the
`EXECUTION_COMMAND` path is relayed to nodes in the first cut.

**#340** (ESP-NOW timing broadcast) IS this epic's timing slice but is only
*related* — the CLI's `-parent` is create-only, so it cannot be reparented from
here. Also note **#339 no longer exists** (404), so #340's `follows #339` gate is
gone; if the uPTP-vs-ESPNow-vs-NTP evaluation still matters it needs refiling.

## Prior Task — Committed Playwright suite for the VP UI (TEC-NATKIT-15 DONE)

**#338 CLOSED 2026-08-10 — commit `20f2bc2`.** The throwaway `/tmp` verification
scripts are now a committed suite: `frontend/e2e/`, 23 tests over 7 spec files,
`npm run test:e2e`, ~1.4 min against the dev stack. `@playwright/test` is a real
dev dependency (browsers already cached in `~/.cache/ms-playwright`);
`npm run check` type-checks `tsconfig.e2e.json` too, and **vitest is now scoped
to `src/`** (`vite.config.ts` `test.include`) or it tries to run browser specs.

Read `frontend/e2e/README.md` first — it carries the paid-for gotchas. The ones
that cost time THIS session:
- **A Save clicked before the socket connects is a silent no-op.** Every editor
  action that talks to the backend returns false and only sets an error string.
  `VpApp.open` waits for `.conn-pill.connected`; before that, every test failed
  with "board never reached the backend store".
- **A new board is a local draft — there is no auto-save for one.** It must be
  saved explicitly, because `save_experiment` refuses to bind a board the backend
  has never seen (`persistExperiment` saves it first in the app's own flow).
- **A repeat group contains its children's fields and actions**, and `± Jitter
  (s)` exists at both levels — hence `ownField`/`stepAction`, which scope through
  the card's own `.card-main`. A bare `.locator('button[title=...]')` on a group
  matches 4 elements.
- **The canvas replaces the list**, so step rows are not in the DOM to count once
  Canvas is showing — read counts before switching.
- **`fill()` only raises `input`**; the comma-separated class list commits on
  `change` and needs a blur.
- **A rendered thumbnail is not proof the image loaded** — poll `naturalWidth>0`.
  (The old `/tmp/qs-images` PNGs were valid; the check was just too early. The
  committed fixtures are hand-generated 64×64 PNGs.)

Evidence: `~/natkit-verification/<sha>/` (`-dirty` when the tree is not clean),
`<ticket>-<nn>-<slug>.png` at 1600×1050 @2x + `MANIFEST.md` with a caption per
shot AND the run health (native dialogs / console errors / stores restored).
33 shots attached to #313/#314/#335/#336/#337; manifest on #338 (attachment #53
is current — **`attachment delete` still 401s**, so #52 is a stale duplicate).
Seeded randomization is proven by **image equality** (seed 1 / 2 / 1 again,
asserting shots 1 and 3 byte-identical).

**Real defect found by the suite → #342 (TEC-NATKIT-19):** the designer
re-renders the **last-saved** protocol for the duration of the save round trip,
because `flushExperimentEdit` clears `pendingExperimentEdit` when it SENDS the
save, not when the `experiment_saved` echo lands. Measured ~11ms via a
MutationObserver (410ms after the edit = the 400ms debounce), but it is as long
as the round trip. It resets the canvas's zoomed-into group (keyed by step id) —
which is why "open a repeat group right after converting" bounced to the top
level — and is a plausible source of a transient `recipe.cues`-on-null crash in
`QuickSetupCard`. `Designer.convertToSteps` waits for the round trip via
`VpApp.waitForStoredProtocol` instead of racing it; **that settle can be deleted
once #342 is fixed.**

Not covered (deliberate): recording a session (needs a device + live broker),
replay/instance review, and the markers-node "Open protocol" portal.

## Prior Task — Experiment authoring UX rework (Phase 1 SHIPPED, Phases 2–5 planned)

Zach flagged the VP experiment-definition panel as "genuinely a bad experience":
unlabeled fields, cramped 320px strip, no quick setup, and a wish for experiments
as zoomable/wireable spatial objects. Plan:
`plans/experiment-authoring-ux-rework-plan.html` — 5 phases, one `StepProtocol`
shape under every altitude (quick-setup recipe → step list → step detail →
(later) sequence canvas with zoomable repeat groups → session composition).
Keeps the experiment-as-entity model and the `markers` node untouched.

**Phase 1 DONE 2026-08-07 (uncommitted, branch `zach/tab-persistence`):**
- Every step field labeled (Step type / Shown to participant / Class label
  (trained on) / Hold (s) / Continue-button text / Times / Shuffle each pass /
  Tutorial (not trained on)). `ExperimentPanel.svelte` step rows restructured
  into head (type + actions) / labeled fields / flags.
- **Instructions can hold for input**: `InstructionStep` gained
  `wait_for_input` + `continue_label` (`experimentSteps.ts`); the toggle swaps
  Duration for button text. Compiles to the same zero-length barrier a `wait`
  step emits, so runner/clock-freeze/`resolveScheduleWaits` needed no changes;
  the standalone `wait` kind survives for existing protocols.
- Kind color accents (left border), Duplicate-step button (deep-copies repeat
  groups with fresh ids), and kind changes now carry text/duration/media over
  (`retypeStep` swapped wholesale via `replaceStep` so old-kind fields don't
  linger — `patchStep` merges and would leak them).
- Verified: svelte-check 0 errors, vitest 79/79 (2 new tests), and LIVE
  headless screenshots against the dev stack (frontend container bind-mounts
  ./frontend with HMR, so source edits are served immediately). Scratch board +
  experiment created and fully deleted after — boards back to the original 8.
  Recipe: playwright-core from `~/.hermes/hermes-agent/node_modules` (import by
  absolute path — ESM ignores NODE_PATH), Node 22's global WebSocket for the WS
  protocol, deep-link to /VisualProgramming does NOT route (tinro lands on
  Home) — click the nav link instead. Auth is open in dev (session endpoint
  answers authenticated without a cookie).

**Zach signed off (2026-08-07): designer = overlay; recipe hard-detaches on
customize; Phase 4 canvas will be a view toggle, list stays canonical.**

**Phase 2 DONE 2026-08-07 (uncommitted):** new `ExperimentDesigner.svelte`
overlay (same idiom as composite-internals: z-60 backdrop, Esc/backdrop close);
ALL protocol authoring moved there (step editor, legacy fixed form, built-ins,
media); `ExperimentPanel.svelte` rewritten as the operator status card
(bind/create, participant/notes, protocol summary card + "Edit protocol",
Record/Stop, live cue, history). `createExperiment` opens the designer
immediately. New in the designer: **compiled-timeline strip** (per-class colored
segments via scheduleForProtocol — works for BOTH protocol shapes; waits render
as amber ticks since they have no length; tutorial spans hatched; class legend),
**collapsible repeat groups** (one-line "10 steps · ~60s total" summary),
**drag-to-reorder** off a grip handle (HTML5 dnd; arrows kept as accessible
path; repeat groups refuse to nest; drop-into-group appends).

Verified: svelte-check 0/0, vitest 79/79, live headless: designer auto-opens on
create, convert-to-steps, wait toggle updates strip (tick + chip), collapse,
reorder AND drop-into persist through the debounced save + echo, Esc closes,
"Edit protocol" reopens, no console errors, stores restored exactly (8 boards /
7 experiments — Zach ACTUALLY HAS 7 real experiments now, created since Aug 5;
state.md's old "0 experiments" is stale — filter cleanups by scratch label,
never assume the store is empty).

Gotchas learned the hard way:
- **Playwright's `dragTo` does not drive HTML5 dnd here** — dispatch synthetic
  DragEvents (`new DataTransfer()` works in Chromium) to test drag paths.
- **Real bug found by that test:** dragover on the group body bubbled to the
  group card's own handler, overwriting "into the group" with "after the group
  card" — every drop-into was silently a no-op reorder. Fixed with
  stopPropagation in `handleGroupBodyDragOver`.
- A crashed UI script leaks its scratch experiment AND board; two leaked this
  session and were cleaned by id/label over the WS protocol
  (delete_experiment / delete_stream_graph). Verify store counts after every
  scripted run.

**Phase 2.5 DONE 2026-08-07 — seeded randomization + step-type cleanup
(uncommitted).** Zach asked for: randomization that is seed-based/recreatable,
and better step types.
- `experimentSteps.ts`: `TimedStep` mixin (`duration_s` + optional `jitter_s`)
  on instruction/cue/rest; `StepProtocol.seed` feeds one mulberry32 stream in
  `compileStepProtocol` (advanced once per jittered emission) → duration ±
  jitter, clamped ≥0. Barriers (wait / instruction-holding) never jitter. Same
  protocol JSON = same schedule; reroll seed = new variation. 4 new tests
  (83/83).
- Designer: "± Jitter (s)" on timed steps (0 stored as undefined to keep JSON
  clean; hides while an instruction holds for input); shuffle Seed + dice on
  repeat groups (shown when shuffle on); "Timing seed" + dice in the header;
  legacy fixed form gained its Shuffle seed field.
- Step-type cleanup: `wait` retired from the add palette and the kind dropdown
  (option still shown when the step IS one, so old protocols render);
  `retypeStep` wait→instruction carries `wait_for_input`+`continue_label` so
  conversion is behaviour-preserving. Add buttons now have kind color dots +
  "what it's for" tooltips.
- Verified: svelte-check 0/0, vitest 83/83, live headless (palette without
  Wait, dropdown without wait option, both dice buttons render, timeline strip
  visibly recompiles on timing-seed reroll, jitter field hides under the wait
  toggle, stores restored exactly, no console errors).

**Vikunja board audited 2026-08-10** (project 53 via the `assistant` CLI). This
work maps onto tickets **#313** (rests) and **#314** (experiment window), whose
descriptions are the original asks. #314's undone bullets were split into
**#335** quick setup and **#336** spatial canvas. Findings recorded as ticket
comments; also corrected #321 (the hardware channel family already exists —
`HARDWARE_CONFIGURATION` is declared but never used) and anchored #318 to the
`StreamType` extension seam.
⚠️ **Vikunja stores descriptions/comments as HTML (tiptap), NOT markdown.** The
`assistant` CLI DOES convert markdown now (v0.7.0) — the older note here saying
it does not is wrong — but **do not hard-wrap the markdown you send it**: inside
a list item a soft line break becomes `</p><p>`, splitting a wrapped sentence
into two paragraphs, and `**bold**` spanning a newline is not emphasised at all
(the asterisks show verbatim). One long line per paragraph and per bullet.
Comment edit works; `comment delete` and `attachment delete` still 401.

**#313 DONE 2026-08-10 — rest interleaving (the other half of the ticket).**
`RepeatStep.interleave_rest?: InterleavedRest` ({duration_s, jitter_s?, label?,
text?}); the compiler inserts a rest after EVERY child including the last (that
trailing rest is what separates consecutive passes), and does so **after
shuffling** — which is the whole reason it is a compile step and not real rows.
"Interleave on, 0s" inserts nothing. Jitter composes with the protocol timing
seed. UI: "Rest between steps" toggle on the group card revealing Rest (s) +
± Jitter (s); collapsed summary says "5 steps + rests · ~60s total".
Verified: vitest 8 new tests including **an interleaved group reproducing
`buildCueSchedule`'s exact phase/gesture sequence and duration**; live run went
32 segments (10 rows) → 17 (5 cue rows) → 32 segments with only 5 rows.

**#335 DONE 2026-08-10 — quick setup.** New `StreamViewer/quickSetup.ts` (pure,
20 tests): `QuickSetupRecipe` → steps in the shape get-ready → practice
(tutorial) → ready gate → main block, built on #313's interleave so the
generated protocol is N cue rows not 2N. `labelFromFilename` ("Fist Closed.PNG"
→ `fist_closed`). New `QuickSetupCard.svelte` in the designer replaces the step
list while a recipe is attached: Images/Class-names toggle, multi-file drop zone
uploading via `/api/media`, thumbnail tiles with editable labels, knobs, live
summary. Recipe stored as `protocol.quick_setup` (typed `unknown` on
StepProtocol + `isQuickSetupRecipe` guard, to avoid a circular import and
because it is read back from a store).
**Detach is enforced at the `commitSteps` choke point** — every hand edit funnels
there, so that is where the recipe is dropped; "Customize steps…" confirms and
is one-way by design. Live-verified with 3 real uploads incl. thumbnails
actually rendering, knob→regenerate, backend round-trip, and detach keeping the
steps while a following hand edit stays detached.

Totals now: svelte-check 0/0, **vitest 110/110**. Board: #313 and #335 closed,
#314 at 80% (only #336 left).

**Follow-ups after Zach moved #313/#335 to a validation bucket (2026-08-10):**

1. **Interleaving is now the DEFAULT.** `stepsFromLegacyProtocol` emits cues +
   `interleave_rest` instead of rest rows, so converting ANY legacy protocol
   (incl. the Finger-counting default) yields 5 rows not 10 with the toggle
   already on — compiled timeline unchanged (32 segments), which the existing
   equivalence test pins. `blankStep("repeat")` also defaults to
   `interleave_rest: {duration_s: 2}`.
2. **All 20 `window.confirm/alert/prompt` call sites are GONE.** New
   `VisualProgramming/dialogs.svelte.ts` (await-able `askConfirm`/`askName`/
   `showAlert`, a queue, and a settle-guard against Enter+click double-resolve)
   plus `DialogHost.svelte` mounted once in the editor (z-index 80, above the
   designer's 60). The name dialog **lists existing names and filters as you
   type** with an "n of m" counter, warns on a case/whitespace-insensitive exact
   match (does NOT block — ids are generated, so duplicates are legal), and is
   reused for experiment / profile / composite names.
   - Functions that now await a dialog became `async`: `selectGraph`,
     `createGraph`, `loadStarterTemplate`, `createExperiment`, `deleteInstance`,
     `deleteBoundExperiment`, `convertExperimentNode`,
     `createCompositeFromSelection`, `saveCurrentAsProfile`, `removeProfile`,
     `loadProfile`. **The non-dirty path stays synchronous** (no `await` is
     reached), so callers depending on immediate selection are unaffected.
   - ⚠️ **CSS trap hit twice, both caught only by screenshotting:** a
     `display:flex` container turns bare text nodes into flex items (the
     collision sentence stacked into columns) and strips `list-item` off `<li>`s
     (bullet markers vanished). Don't flex a text paragraph or a `<ul>`.
   - Live check **asserts Playwright's `dialog` event never fires**, which is the
     regression guard for this work.

**#336 DONE 2026-08-10 — spatial protocol canvas (commit `8cd8408`).**
`ProtocolCanvas.svelte`: List/Canvas toggle; steps as colour-coded nodes in an
auto-laid-out sequence lane; repeat groups as black-box containers with
double-click/Open zoom, breadcrumb, and a group-scoped add palette (no nesting);
selection opens labelled fields. **`StepFields.svelte` extracted (~330 lines out
of the designer) so the list rows and the canvas inspector render ONE
definition** — that extraction is what keeps the canvas from being a second copy
of the fields.
- The markers-node portal is an **"Open protocol" button, not double-click**:
  that gesture already opens the participant run surface and repurposing it
  would break conducting an experiment. Flagged on the ticket for Zach's call.
- ⚠️ **Class-name collision bug, found only by measuring:** container nodes had
  ~300px dead space either side because a dependency ships a global
  `.container { margin: auto }`. Svelte scopes OUR rules but a global rule still
  matches our element by class name. Renamed to `.is-group`; swept all unscoped
  rules matching canvas elements (rest are Tailwind resets). **Generic class
  names are unsafe here even with scoped styles.**

**TEC-NATKIT-3 (#314) is CLOSED** — all five bullets done. Phase 5 (wiring whole
experiments together as session blocks) deliberately deferred as **#341**, which
carries the open question: is a block a copy or a reference?

**Board now labelled** (the org had zero labels before): one type label per
ticket (Feature / Task / EPIC / Maintenance / Testing) plus UI/UX where
user-facing. Note the list endpoint does NOT return labels — read per ticket.

**Verification screenshots are attached to tickets** via `assistant task attach`
(v0.7.0). Capture script conventions live in #338; sets are written to
`~/natkit-verification/<sha>/` with a MANIFEST.md.

⚠️ **Scripted-UI hygiene, learned again:** a script that throws before its
cleanup leaks a scratch board AND experiment. Wrap cleanup in `finally`. Also
**do not reload the page and assume the same board is selected** — the VP page
picks its own, which is how one run ended up reading a different experiment.
Zach has **8 real experiments** in the store now; filter cleanup by the
"UX Scratch Test" label and verify counts after every run.

## Prior Task — EXECUTION_COMMAND channel (slice 1 DONE on hardware, slice 2 NEXT)

Bidirectional server<->sensor commands, with command output on the log channel.
The device subscribes to its own `Command-<id>-Json-NatExecutionCommandV1` topic
and answers on `Log-<id>-Json-NatLogV1`, correlated by `command_id`.

**Slice 1 — DONE, verified end-to-end on the board** (root `0e5538e`):
- `libnatkit` `4998c19`: bridge outbound prefix typo fixed,
  `natKit/reciving/` -> `natKit/receiving/`. Requires the bridge image to be
  rebuilt (`podman build -t natnl/natkit-bridge:latest -f
  Dockerfile_libnatkit_bridge .` in `libnatkit/`, then retag to
  `docker.io/natnl/...` — compose resolves the docker.io name, not `localhost/`).
- `natKit-IMU` `6e32315`: `embeded/include/CommandChannel.hpp` (two FreeRTOS
  queues + a minimal JSON field reader), command/log topics on `KafkaTopic`,
  `ping` / `calibrate.save_dcd` / `calibrate.status`, and a fix for the device
  name (`String{UNIQUE_ID}` narrowed a uint64 to one byte).
- No C++ schema classes were needed: the bridge only decodes for *logging*, so
  forwarding is schema-agnostic and the schema name in the topic is the contract.

**Slice 2 — DONE** (libnatkit `4b8b9b8`, root `be5b672`): a `send_device_command`
WS action that subscribes to the log topic, produces the command, then collects
records until one is terminal; plus "Save to device" / "Read config" buttons on
the VP IMU-calibration node. 17/17 backend checks and 11/11 browser checks
against the live board. Gotcha: on a device's FIRST command the Command topic does
not exist, and the bridge only forwards topics it has a messenger for (1 s
discovery poll) — so the action creates the topic and waits a poll cycle before
producing, or that first command is silently dropped. The buttons deliberately do
NOT sit under the accuracy-selection branches; they need only a stream id.

**Slice 3 — NEXT:** a guided calibration sequence (the 6-side routine driven from
the server) with progress on the log channel.

**Verification recipe** (a Kafka/MQTT-level alternative to the UI button):
```
podman exec mosquitto mosquitto_pub -h localhost \
  -t 'natKit/receiving/Command-13793649670644-Json-NatExecutionCommandV1' \
  -m '{"command_id":"x","source":"server","target":"sensor","command":"calibrate.status"}'
podman exec natkit_natkit-v0-kafka_1 kafka-console-consumer --bootstrap-server \
  localhost:9092 --topic Log-13793649670644-Json-NatLogV1 --partition 0 --offset 0
```
(`kafka-console-consumer` without `--partition/--offset` prints nothing here;
`kafka-get-offsets` is the quick liveness check. `podman images` is broken on
this box — readlink on the overlay dir — but build/ps/exec all work.)

**CALIBRATION ROOT CAUSE FOUND AND FIXED (2026-08-05).** `calibrate.status`
reported `cal_config=0x05 (accel=1 gyro=0 mag=1)` with accuracy
`accel=2 gyro=0 rotation=0`: gyro dynamic calibration was never on, which is why
rotation never left Unreliable. `sh2_setCalConfig` has failed with `SH2_ERR_HUB`
from `setup()` since Feb 2026 (71e3be8), leaving the hub on its default 0x05.

The call works nowhere in `setup()` — measured: first hub command -> OK but the
hub goes silent; before the enableReports -> `SH2_ERR_HUB`; after them -> OK and
silent; **deleted entirely -> silent too**, because each sh2 op pumps SHTP while
awaiting its reply and the FAILING call was load-bearing timing. So `setup()` is
left byte-for-byte as the verified-streaming version and the enable is deferred
into the sample loop (`enableDynamicCalibrationOnce`, 5 s after the first sample,
3 retries, failure reported on the log channel).

Result, reproducible over two hardware resets: `setCalConfig(0x07) -> 0`,
read-back 0x07, ~1900 frames/70 s, zero "Nothing to read", zero panics, and
`/api/get_accuracies` now reports `gyroscope: 3` (was 0), stable over 20 polls.

Also fixed in the same path: the SH2 status byte was used unmasked as an accuracy
(bits 7:2 are the report delay, and values are packed 2 bits per sensor, so a
nonzero delay would corrupt neighbouring sensors), and the backend ignored
`has_data` while reading only `records->back()` — so any sensor absent from the
last sample of a frame reported Unreliable.

**Zach ran the 6-side routine (2026-08-05): gyro now reads High, confirming the
fix — but rotation did NOT move off 0 and accel stayed at 2.** So rotation is a
SEPARATE defect, not a consequence of the gyro bug.

Plumbing was ruled out by reading it: the active path (update3 -> event-based,
ImuReader.hpp ~950) sets `data_point.calibration = event.accuracy`, which is the
masked status of SH2_ROTATION_VECTOR. So the hub itself is reporting 0.

Leading hypothesis, NOT yet measured: for the BNO08x the rotation vector's real
quality signal is the separate `accuracy` float (radians) in
`sh2_RotationVectorWAcc`, and its 2-bit status field may simply never be
populated — the 0..3 status is meaningful for the raw accel/gyro/mag reports. If
so, "Rotation: Unreliable" was never a measurement at all. AGAINST this
hypothesis: Zach remembers rotation reaching High about a year ago, and the
overall readout is worst-case, so it could not have shown High with rotation at 0.
One of those two must be wrong; measure, do not assume.

**UNCOMMITTED, COMPILED BUT UNFLASHED** in natKit-IMU (deliberately not committed
so trunk stays at the verified-good state): an `imu.diag` command reporting raw
per-report status bytes, report counts, and the rotation vector's `accuracy`
float, plus `NAT_BNO08X_ENABLE_MAGNETIC_FIELD_CALIBRATED` turned on so mag
convergence is observable at all. The mag report-enable is a hub-timing change and
this hub has proven fragile about those, so it MUST be checked for streaming
health after flashing.

BLOCKED ON HARDWARE: /dev/ttyACM0 re-enumerated at 16:31 (while the board was
being handled) and is now wedged — reads return nothing and both the DTR/RTS
reset ioctl and a usbfs USBDEVFS_RESET hang. The board itself is fine and still
streaming over WiFi. Needs a physical USB unplug/replug before anything can be
flashed.

## Previous Task — Experiment history snapshots (Phases 0 + 1 DONE, Phase 2 NEXT)


Plan: `plans/experiment-history-snapshots-plan.html`. Redesigns the VP experiment:
it stops being a NODE and becomes a first-class object owning a graph + a history
of **instances**. Each recording mints an immutable snapshot (graph + data +
markers); forking mints an editable one. Detail + gotchas in the auto-memory
`experiment-history-snapshots-plan.md`.

**Decisions locked by Zach (2026-07-29):**
- Materialize **raw sources only** — no transform outputs. Keeps snapshots small and
  lets a fork legitimately recompute (the point of forking).
- **A fork IS an instance that happens to be editable** — same record shape, same
  place in the tree. It *inherits* `recording` verbatim, so it points at the same
  Parquet; forking never copies data. Running a fork does NOT mint a new instance.
- **Retire the provenance edges** (`prov_source` / `prov_experiment`) — experiment-
  owns-the-graph expresses that lineage implicitly.
- **Parquet is the stored form; replay streams out of it.** No Kafka time-travel.

**Phase 0 DONE + verified over the WS protocol (7 checks, all passing):**
- `StreamGraphDefinition` gained `experiment_id`, `instance_id`, `immutable`,
  `origin` ("recording"|"fork"), `forked_from`, `recording` (opaque json). All
  optional and emitted only when set, so a plain board's JSON is byte-identical.
- New `fork_stream_graph {source_graph_id, label?}` → `stream_graph_forked`. Fork
  ids suffix the parent (`run-0001` → `run-0001-a` → `run-0001-a-a`) so lineage is
  readable. Refuses to fork a live board (no recorded data behind it).
- `handleSaveStreamGraph` rejects overwriting an immutable instance AND re-pins all
  provenance from the stored record — a client cannot launder a fork into a
  recording, re-parent it, or repoint it at another session's artifacts.
- `sendError` now takes an optional `requestId` and echoes it. Errors were
  previously uncorrelatable, which matters once rejection is a NORMAL outcome
  (saving an immutable instance) rather than a fatal surprise.
- Verified with a throwaway backend on :7410 + its own graph store; the live stack
  was untouched.

**Phase 1 DONE — the experiment is an object, not a node. Verified 24/24 over the
WS protocol** (throwaway backend on :7411 with its own stores; the live stack was
untouched) plus svelte-check 0 errors and vitest 59/59.

Backend (`StreamViewerWebSocket.cpp`):
- `Experiment` entity + `experiments.json` store behind `NATKIT_EXPERIMENT_STORE`
  (atomic write, load-on-startup — mirrors the profile store).
  `list/save/delete_experiment` → `experiment_list|saved|deleted`. `protocol` is
  stored as OPAQUE json (same reasoning as `editor_metadata`: the frontend owns
  that shape and already round-trips it).
- **`save_experiment` is the SOLE writer of the 1:1 experiment↔board binding.**
  Setting `live_graph_id` stamps `experiment_id` onto that board and clears it from
  any other LIVE board (instances keep theirs — they're history). Bind is applied
  BEFORE the experiment record is written, so a refused bind (unknown graph, or an
  immutable instance) leaves the record untouched. Lock order is always
  experiment → graph. `delete_experiment` refuses when the experiment has recorded
  instances (they'd be orphaned) and unbinds the board otherwise.
- New **`markers` node kind**: config-less source, no inputs, one `markers` output
  resolving `Marker/<experiment_id>` from the GRAPH's binding (a legacy node's own
  config is the fallback). Allow-list + normalization + validation + start dispatch
  + catalog entry. `experiment` is REMOVED from the catalog but still parsed.
- **Provenance edges retired** (the plan's DECIDED): `prov_source` /
  `prov_experiment` are gone from the catalog and normalization, AND edges touching
  them are dropped in `from_json` — without that, an old board loaded with edges
  pointing at ports that no longer exist and went invalid on a diagnostic the
  author couldn't fix. `prov_models`/`prov_model` (train→classify) survive: a model
  artifact IS a real handoff.
- `isMarkerSourceKind(kind)` centralizes `markers|experiment` so combine's marker
  lane and export's label join can't disagree about one of the two names.

Frontend:
- New `ExperimentPanel.svelte` (board-level: bind/create/delete, protocol
  authoring, participant/notes, Record/Stop + live cue + schedule preview),
  toggled from a toolbar pill that shows the bound experiment. Board header also
  gained IMMUTABLE and ● REC pills.
- Recording is now experiment-driven (`SessionRecordingState.nodeId` →
  `experimentId`); device ids come from EVERY `stream_source` on the board, which
  is what replaced the source→experiment edge.
- `markers` node: palette (all 3 surfaces are catalog-driven, so it appeared for
  free), node card, inspector explainer, and the inline/expanded `ExperimentRunner`
  moved onto it (`inline_experiment`).
- **Legacy convert**: the `experiment` node's inspector offers "Convert to
  experiment + markers" — lifts the protocol into a stored experiment bound to the
  board and swaps the node IN PLACE (same node id), so every edge survives.
- Board picker filters `instance_id != null` — instances share the graph store and
  would otherwise show up as boards.
- Train run scoping now reads the board's binding instead of a `prov_experiment`
  edge; starter templates carry an `experiment` record (protocol left the canvas)
  and the loader creates + binds it.
- `StreamGraphDefinition` gained the read-only Phase-0 fields (`experiment_id`,
  `instance_id`, `immutable`, `origin`, `forked_from`, `recording`).

Also: `NATKIT_EXPERIMENT_STORE: /graphs/experiments.json` added to all three
compose files (same volume as the graph store — losing it orphans history), and
the smoke script now covers the markers node + the experiment store + the binding
being written on both sides.

**Phase 1 UI LIVE-VERIFIED 2026-07-29** against the running stack (backend image
rebuilt, container recreated, Playwright headless at :8080). Two suites, both
green: 18/18 on the main flow (palette offers Markers and no longer offers
Experiment · pill opens the panel · create binds the experiment · protocol form is
board-level · cue-schedule preview · Record enabled · a protocol edit survives a
reload, so the debounced save reaches the backend · no console errors) and 10/10 on
the migration flow (a seeded legacy board keeps `kind:"experiment"`, drops the
retired port, offers Convert, and after converting the node IS a markers source
with the protocol/participant carried over **and the edge into the viewer intact**).

**Two real bugs the live run caught that static checks could not:**
1. **The toolbar overlapped the floating panels.** Panels were pinned at a
   hardcoded `top: 72px`, but the toolbar WRAPS — selecting a node adds "Group",
   and the pills I added made a second line likely. The taller toolbar (z-index 20)
   then covered the panels' first row and swallowed clicks on it. Fixed by
   measuring the toolbar (`bind:clientHeight`) and driving all three panels off
   `--panel-top`. This latently affected the sidebar/inspector too.
2. **`boundExperimentLabel` was declared on the node card but never passed** at the
   call site, so a Markers node always read "No experiment bound". An optional prop
   that is never passed type-checks perfectly — only a render shows it.

Also fixed while there: retired provenance ports are now stripped in
`from_json` (not just on save), so a legacy board stops RENDERING a dead
`prov_source` port before anything re-saves it.

⚠️ **Test-data hygiene, learned the hard way.** The UI runs mutated real boards
before I scoped them: they bound test experiments to two of Zach's boards and left
stray Markers nodes on them (1 on `stream-graph-1785336487040`, 3 on
`starter-1784569198910`). All cleaned up — the strays had to be removed from
`editor_metadata` as well as `nodes`, since the editor prefers that tree on load.
A later "read-only" look also accidentally loaded a starter template, because the
sidebar's starter buttons share `.graph-list-item` with the board list. Verified
afterwards: no experiments remain, no board is bound, and every Convention EMG
board is back to its original 7 nodes with its own `experiment` node.
- **Leftover test boards (harmless, mine):** `stream-graph-1785346642668`,
  `ui-legacy-convert-check`, `starter-1785347037130`. **There is no
  `delete_stream_graph` action** — worth adding before Phase 2, since instances
  are graph records and a failed materialization will want pruning.
- Next time: create a scratch board first and delete it after; never let a UI
  script run against whatever board happens to load.

**Backend image build cache — FIXED + MEASURED 2026-07-29.**
`Dockerfile_natkit_backend` did `COPY . ./` before building drogon, so any source
edit invalidated the drogon layers. Now: toolchain probes → `COPY third-party` →
configure/build/install drogon → `COPY . ./` → project build. Safe because the
project consumes drogon from its install prefix (`/usr/local`); the top-level
CMakeLists never adds `third-party/drogon` as a subdirectory, so nothing rebuilds
it, and `.dockerignore` keeps the later `COPY . ./` from clobbering its build dir.
- Also tightened `.dockerignore`: `build/` matches only the ROOT build dir, so
  `lib/libnatkit-core/build` (**171M** of host output) was being shipped in the
  context and re-COPYed on every source edit. Now `**/build/` as well. Verified the
  only `build` dirs in the tree are ./build, ./lib/libnatkit-core/build and
  ./third-party/drogon/build — all output.
- **Measured, and my earlier estimate was WRONG.** I claimed ~20 min → ~2 min.
  Reality on this box (12 cores, `--parallel 10`): full build **2m52s**, and a
  source-only rebuild **1m44s** with all four drogon steps cached. So the saving is
  ~68s per backend edit (~40%), not 18 minutes. The original ~17 min build was a
  cold base image + the Arrow APT download, not drogon.
- Verified after: the rebuilt image serves the Phase 1 protocol (catalog advertises
  `markers`, `experiment` retired, experiment store reachable), and the bridge image
  — which shares this `.dockerignore` — still builds.

## Phases 2 + 3 DONE — recording mints a DURABLE instance (2026-07-29)

Shipped as one slice deliberately: Phase 2 alone would mint instances whose data
still only exists in Kafka, which is the "permanent snapshot that silently becomes
empty" the plan warns about. **25/25 checks pass against the LIVE stack.**

Protocol (all new):
- `start_experiment_instance {experiment_id, window_start_us}` → snapshots the
  experiment's live board (nodes + edges + `editor_metadata`), mints
  `instance_id` = `run-0001`, `run-0002`, … per experiment (forks then suffix them,
  `run-0001-a`), records the raw sources, `status: "recording"`. Graph id is
  `<experiment_id>-<instance_id>`.
- `finish_experiment_instance {graph_id, window_end_us, completed}` → closes the
  window, `status: "materializing"`, then materializes on a **detached thread**
  (draining a topic takes tens of seconds; pinning a drogon worker would stall
  every client) and BROADCASTS the outcome as `experiment_instance`.
- `verify_experiment_instance {graph_id}` → re-checks every artifact against its
  recorded sha256. Added because a checksum nobody re-checks is decoration: I only
  noticed a corrupted artifact by comparing hashes by hand.
- `delete_stream_graph {graph_id, force}` → deletes a board or fork; a SEALED
  instance needs `force` (it destroys recorded history + its artifacts). Refuses
  while the graph is running, unbinds the experiment, removes the artifact dir and
  prunes the now-empty per-experiment parent.

Materialization (`materializeInstance`): per recorded raw source, reuse
`exportStreamToParquet` pointed at `NATKIT_INSTANCE_STORE/<experiment_id>/<instance_id>/`
→ verify non-empty → rename to `<stream_id>.parquet` → sha256 → chmod read-only →
`status: complete` (which is what SEALS `immutable`) or `failed` with the exporter's
own diagnostic. `ParquetExport` gained a **markers JSONL sidecar** (written from the
markers it had already decoded — a second drain would be slower and racier against
retention) and the **`natkit.schema_name` metadata** the plan flagged as missing.

Decisions/judgements made here:
- **`complete` is what seals an instance, not minting.** A recording is mutable
  while it runs (the status transitions are writes), and a FAILED instance stays
  unsealed on purpose so it can be deleted or retried — sealing an empty snapshot
  is the exact failure the plan warns about.
- **A failed instance leaves NO files.** The sidecar is written before the long
  data drain, so a failure otherwise orphaned a markers.jsonl that was on disk but
  absent from the manifest.
- **Read-only mode bits are an accident guard, not a guarantee** — the backend runs
  as root and root ignores them. Verified the hard way: `echo x >` truncated a 15MB
  sealed artifact (a throwaway test instance). The sha256 caught it, which is the
  point, and `verify_experiment_instance` now makes that check a one-liner.
- Instance-store mount: dev/base compose both define `/instances`; the merge
  resolves by target so the dev named volume (`natkit-v0-instances`) wins, exactly
  as `/graphs` already behaves.

Live-verified end to end with the real 1M-record IMU topic: empty window → `failed`
with "No data frames inside the session window (387075 of 387075 scanned)" and no
files left; wide window → `complete`, 393,764 rows, 15MB Parquet + a 66-line markers
sidecar, both checksummed, sealed; tamper → detected; a fork shares the artifacts
and reports the same corruption.

## Phase 4 DONE — history tree + instance review (2026-07-29)

**Verified: 14/14 backend, 6/6 histogram, 25/25 UI — all live.**

Two backend gaps the plan assumed were already closed:
- **The label histogram did NOT exist.** The plan says review can use "the label
  summary already computed during materialization" — only `labelled_rows` was.
  `ParquetExport` now returns per-class `labelCounts` (empty key = rows inside the
  window but between cues, surfaced as `(unlabelled)`) and materialization records
  it per artifact. This is the difference between "395k rows" and "usable": one
  class never firing is invisible in a row count.
- **`GET /api/instances/artifact?graph_id=&path=`** — reviewing a snapshot has to
  read the FILE. The pre-existing `/api/export/parquet` re-drains Kafka, which is
  meaningless for an instance whose whole purpose is that its data has left the
  broker. The `path` is matched against the instance's MANIFEST rather than joined
  onto the directory, because a client-supplied path would otherwise be a directory
  traversal out of the volume (verified: `../../../etc/passwd`, `/etc/passwd` and an
  unlisted sibling all 404).

UI: sidebar **Experiments & history** tree (experiment → recordings → forks, nested
recursively via `forked_from`, newest first, with row counts); opening an instance
loads a **genuinely read-only** board; an Instance review section with window,
status, artifacts (rows / schema / checksum / truncation warning), a **label
histogram** with proportional bars, download links for the parquet and the markers
sidecar, **Fork to edit**, and **Verify**. Forking opens the fork immediately —
that's the point of forking.

**Read-only was enforced at the choke point, not per-widget.** `markDraftChanged`
is the funnel all 32 edit paths pass through, so gating it covers palette adds,
drags, config edits, composites and param writes at once; `startNodeDrag` refuses
early (no phantom drag that snaps back), and `saveDraftGraph` +
`scheduleReactiveRestart` bail so Phase 7's debounced auto-save can't spray
rejections. The backend rejection remains the outer backstop.

Two bugs the SCREENSHOT caught that 23 passing assertions did not:
- A window duration rendered as `1785351523s`. Now humanized (`20663d 18h`, `2m 5s`).
- The canvas note rendered ON TOP of the toolbar — same wrapping-toolbar bug class
  as the panels earlier; my longer read-only message made it visible. Now offset
  from `--panel-top`. Both now have assertions.

All Phase 2–4 test data removed: 0 experiments, 0 instances, 0 artifact files, and
the 16 pre-existing boards untouched.

## Phase 5 DONE (backend) — replay streams a snapshot out of Parquet (2026-07-29)

**21/21 checks pass live.** New `ReplaySource.{hpp,cpp}`: read an instance's Parquet
via Arrow, rebuild canonical `NatSignalFrameDataSchemaV1` frames, interleave the
markers sidecar, publish to a **scratch Kafka topic per replay session**, and bind
the instance's source nodes to it. Actions: `start_instance_replay
{graph_id, mode, speed}`, `stop_instance_replay`, `list_instance_replays`;
`start_stream_graph` gained an optional `replay_id`.

Plan non-negotiables, each verified:
- **`device_ts_us` preserved** — asserted the last published timestamp lies inside
  the recorded window and is ~90,000s away from `now`. Restamping would destroy the
  label interval join and desynchronise multi-stream replay.
- **Markers interleaved** on ONE merged timeline with the frames (a k-way sort by
  original timestamp), so two streams recorded together replay together.
- **Review paced / recompute unpaced** — 3s of data at 0.25× was still mid-flight
  after 4s; recompute published all 80 frames immediately.
- **Scratch topics deleted** when the replay ends or is stopped.
- **Stateful transforms reset by construction**: a replay-bound run goes through
  `start_stream_graph`, which creates fresh workers, so IIR/envelope/vote state
  starts clean and two replays of one instance are comparable.

Four real problems found while verifying (the interesting part):
1. **`BrokerManager::deleteTopic` was a NO-OP.** It built a `rd_kafka_DeleteTopic_t`,
   destroyed it, and the actual `rd_kafka_DeleteTopics` call sat inside a comment
   block — so it had never deleted anything, and the `delete-topic` tool never
   worked either. My "scratch topics die with the replay" claim rested on it, and
   testing leaked 18 topics. Now implemented properly (async request + bounded wait
   on the result queue, tolerating UNKNOWN_TOPIC_OR_PART).
2. **The markers sidecar was written UNCLIPPED.** One experiment publishes every run
   to the same `Marker/<experiment_id>` topic, so an instance's sidecar contained
   *other runs'* markers — replaying it emitted markers that were never part of that
   recording. Now clipped to the resolved window (moved after window resolution,
   still before the long data drain so a partial failure keeps its timeline).
3. **Replay-bound sources failed validation** with `missing_stream_topic`:
   validation asks the BROKER whether the source's topic exists, but a scratch topic
   is auto-created on first produce. The replay plan is the authority for those ids,
   so validation now takes an assumed-source set.
4. **Paced replay would sleep ~56 years** on an item far from the rest (a lifecycle
   marker, or markers bracketing a window wider than the data). Pacing is now
   cumulative per-item deltas with each gap clamped to `maxGapUs` (2s): local timing
   exact, dead air compressed.

Also worth remembering: `start_stream_graph` answers an invalid graph with
`stream_graph_validation`, NOT an error — a client that waits only for
`stream_graph_started` hangs forever. That cost time chasing a "crash" that was
really my test client. And a gdb attach inside the container needs
`add-auto-load-safe-path`, else the backtraces are unusable garbage.

**Broker left exactly as found**: the original 7 topics at their original offsets
(Data 1,032,486 / Heartbeat 38,267 / 3 Marker / 2 Meta); all 18 leaked replay topics
and ~25 test marker topics removed. Stores clean (0 experiments, 0 instances).

**Phase 5 UI DONE too — 13/13 live checks.** The instance review panel gained a
Replay section: Mode (Review paced / Recompute unpaced), a Speed selector
(0.25×–8×) that hides itself in recompute mode because it is meaningless unpaced, a
Replay button, live progress (frames/total + bar + markers) and Stop.

The ordering matters and is encoded in the page, not the panel: **the page starts the
graph against the replay only when the backend confirms the replay started** (which
it does only after the first record is on the scratch topic). Doing it from the click
handler would race topic auto-creation, and a transform resolving its source topic on
the broker would fail to start. Stop tears down both the replay and the graph —
leaving workers bound to a topic that is about to be deleted would strand them.

Verified live: controls render, speed hides in recompute, pressing Replay streams
(progress observed at 1/80 and climbing), the board reaches `running` against the
replay, Stop returns the controls, the scratch topics are gone afterwards, no console
errors. Screenshot confirms the panel reads correctly end to end (real recorded date,
humanized `3s`, `alpha 80` histogram at 100% labelled — the sidecar-clipping fix
showing through).

**Still not built (deliberate, not forgotten):** scrub/seek within a replay. The plan
lists it under review mode ("with a speed multiplier and scrub"); the speed
multiplier ships, scrubbing does not. It needs a seek in `ReplaySource` (skip the
timeline to a timestamp) plus a scrub control wired to the existing TimelineStrip —
a self-contained follow-on.

## Phase 6 DONE — train from instances (2026-07-29). PLAN COMPLETE.

**10/10 live checks: a real LDA model trained from an instance's materialized
Parquet, with no broker involved.** `/models/<job>/lda-model.json`, report naming
`run-0001` as its lineage.

The training path turned out to already featurize from *a Parquet + a markers file* —
which is exactly what an instance materializes. So the work was seams, not a rewrite:
- **natVR `featurize_instances()`**: featurize straight from an instance's artifacts,
  skipping Kafka discovery/reconstruction. Reconstruction only works while records are
  inside retention (168h), so before this a model could not be retrained from an older
  session; and two reconstructions aren't guaranteed identical if retention rolled.
- **Label-column compatibility**: natVR writes `cue_gesture`/`cue_phase`, the natKit
  exporter writes `label`/`label_phase`. `rows_to_sample_stream` now accepts either
  rather than forcing one writer to imitate the other.
- **Samples are read as float, not int.** They were truncated because EMG is int16 and
  truncation was lossless for it — an instance can hold any sensor, and IMU
  accel/gyro are genuinely fractional.
- **`finish_pipeline()` extracted** so the Kafka path and the instance path share the
  family evaluation / bundle / report code. A model trained from an instance must be
  produced by the same code as one from a reconstruction, or comparing them is
  meaningless.
- **Backend resolves instance ids → artifact paths** when proxying the job
  (`resolveTrainInstanceDatasets`): the browser must not know container paths and the
  control plane must not read the graph store. Refuses a live board, a non-complete
  instance, or one with no artifacts.
- **Instance lineage survives the report sanitizer.** Paths are still stripped (they're
  container-local) but `instance_id`/`instance_graph_id` now travel — a model whose
  lineage can't be traced to its snapshot is the problem this phase exists to solve.
- Compose: `/instances` mounted **read-only** into the control plane and worker.
- Frontend: train inspector gained a **Recorded instances** picker (rows + classes per
  instance, train/validate toggles, a warning when an instance has no labelled
  classes); submit accepts either dataset kind.

Three real bugs found by verifying, two of them pre-existing:
1. **`ensureMlControlPlaneClient` self-deadlocked and wedged the WHOLE backend.**
   `connectToServer` runs its callback SYNCHRONOUSLY when the control plane is
   unreachable, and that callback re-locked the non-recursive `ml_client_mutex_` the
   caller still held. Every `ml_proxy` action starts by calling that function, so the
   deadlock consumed each drogon event loop in turn until nothing answered — HTTP
   included. **Restarting the control-plane container was enough to trigger it.** Fixed
   by releasing the lock before connecting; verified by three CP down/up cycles with
   proxy actions fired at a dead CP (backend stayed responsive throughout). This was
   pre-existing Phase-5-era ML-proxy code, not new work.
2. **Featurization wrote its feature file next to the source Parquet** — i.e. into the
   read-only, checksummed instance directory. The read-only mount caught it; had
   /instances been writable, the trainer would have silently added unlisted files to a
   sealed historical record. Features now go to the job workspace.
3. **`annotate_rows_with_cue_markers` died with a bare `KeyError: 'prompt'`** on a cue
   marker lacking that display-only attribute. Instance sidecars can come from any
   producer, so the optional fields are now tolerated (label fields stay strict).

Also learned: the control plane advertises thread slots for **workers that no longer
exist** (its scheduler state outlives container recreates — 148 slots advertised, ~16
live), and a job assigned to a dead worker never runs and never reports. The
frontend's `pickThreadSlot` sorts by busy-ness across ALL advertised slots, so a user
can silently submit into a black hole. **Not fixed** — flagged as the next thing worth
doing.

natVR suite: 92 passed / 9 pre-existing failures (the Kafka-ABI tests need a broker
the local `.so` can't reach) — baseline held, plus 3 new tests. One of the new tests
is SKIPPED under system python (no pyarrow), so the instance-featurization path is
verified in the ml-worker container instead, where training actually runs.

**All 6 plan phases are now complete.** Deliberately not built: replay scrub/seek, and
the dead-slot filter above.

**Still open (do not block Phase 1):** storage budget/retention for instances
(permanent by design, ~2.3 MB per 30s of IMU parquet); is a live graph owned 1:1 by
one experiment (I'd start yes); per-source opt-out from materialization.

---

## Also completed this session (2026-07-28/29)

### Parquet export — built in Python, then REBUILT in C++ at Zach's direction
Plan: `plans/parquet-export-node-plan.html`. First cut ran as a natVR +
control-plane job; Zach pushed back ("I would rather not use python for as much as
I can"), so it was reworked to run entirely in the backend and the Python path was
DELETED (`natvr/session_export.py`, its tests, `start_export_job`, the `/exports`
volume). See auto-memory `prefer-cpp-over-python.md` — treat a new C++ dep as
cheap and new Python in the data path as expensive.

Shipped:
- `export` node kind (allow-list, validation, port normalization, catalog entry,
  start dispatch) — terminal + variadic + topic-aware.
- `ParquetExport.{hpp,cpp}` (~780 lines new): drain a channel's Data+Marker topics,
  project frames, join cue labels via `nat::core::assignIntervalsToTimeline` (the
  SAME stitcher the training path uses), write Parquet.
- `GET /api/export/parquet?stream_id=…` — auth-gated, returns the file as an
  attachment plus `X-Natkit-Frame-Count` / `-Labelled-Frame-Count` /
  `-Marker-Count` / `-Session-Id` / `-Truncated`. Optional `marker_stream_id`
  (markers from a different channel, so a `combine` bundle is convenient not
  mandatory), `label_field`, `run_index`, `start_us`/`end_us`, timeouts.
- Arrow/Parquet dep: Apache's APT source + `libparquet-dev` in
  `Dockerfile_natkit_backend`; CMake gates it behind `find_package(Parquet)` →
  `NATKIT_HAVE_PARQUET`, so a build without it still compiles and the endpoint
  answers 501.
- Frontend: export node card + inspector + fetch/blob download with the counts
  surfaced; the `ml_proxy` export-job plumbing removed.
- **Shared `projectRecordToChannelFrame(record, streamId)`** in
  `StreamViewerWebSocket` — canonical channel-frame contract first, then
  `findCompatibleAlternateInputMapping`. Both the streaming path and the exporter
  call it. This is why IMU/Muse export at all; duplicating the canonical path is
  how export ended up silently supporting fewer sensors than transforms.
- **Window seek**: the exporter resolves a start offset from the session window via
  `queryStreamTime`/`offsetsForTimes` (rewound 10s of slack, since that keys on the
  broker append timestamp not `device_ts_us`) and stops once past the window end.
  Reading from OFFSET_BEGINNING could never reach a recent session on a busy topic.

Verified live end-to-end: 1,575 frames / 1,179 labelled in 6.9s from a 930k-record
topic, labels `still|moving|None` correct, plus a whole-stream IMU export
(56,513 rows, Accel/Gyro channels, real values).

### Bridge log flood silenced
`KafkaMosquittoBridge.cpp`: per-message payload tracing is now OFF by default
behind `NATKIT_BRIDGE_LOG_MESSAGES=1`, checked BEFORE formatting (the format call
decoded the whole record — ~100 lines per bulk IMU frame, twice per frame). Also
warn-once per unrecognized MQTT topic. Measured over identical 20s runs with the
device streaming: **53,306 lines → 0** per-message lines, while still forwarding
~30 records/s. Flag documented in `docker-compose.dev.yml`.

### Two build/deploy traps fixed or documented
- **Arrow broke the drogon link.** `libparquet-dev` pulls `libgrpc29` →
  `libc-ares-dev`; the Dockerfile installs Arrow BEFORE building drogon, so trantor
  compiled `AresResolver.cc` and the backend's hardcoded link list had no
  `-lcares`. Fixed with a conditional `find_library(CARES_LIBRARY)` appended AFTER
  `trantor` (static-archive resolution is order-sensitive). **Underlying
  fragility:** the backend hardcodes drogon's transitive deps instead of using its
  exported CMake target — any future ambient library drogon auto-detects breaks the
  link the same way.
- **`podman-compose up -d` does NOT recreate a container after an image rebuild.**
  It silently keeps the old one, so you retest the old binary and see the identical
  failure. Need `podman rm -f --depend natkit-v0-backend` first (the ml-worker pins
  it via `--requires`). Verify with `podman inspect <c> --format '{{.Image}}'`.
- **A host build compiles NONE of the exporter** — without libparquet-dev,
  `NATKIT_HAVE_PARQUET` is off and the body is `#if`'d out, so a green host build
  only proves the 501 stub compiles. Validate exporter changes in the image.

### Two operational faults diagnosed (pre-existing, not from this work)
- **Frontend wouldn't load:** `natkit_natkit-v0-frontend_1` was an orphan created by
  a hand-rolled `podman run` WITHOUT `:Z`, so npm got EACCES on
  `/app/package.json` (exit 243, crash-looping). The compose file was correct; the
  orphan held the name so compose skipped the service. Fixed by
  `podman rm -f` + recreating through compose.
- **ML worker crash-looping (1370 restarts) on HTTP 401.** `NATKIT_AUTH_DISABLED`
  only short-circuits `authenticateRequest()`; `/api/auth/login` still does a real
  credential check, and the stored admin password (set 2026-07-08) didn't match
  `.env`. Zach fixed it by resetting the password via `/api/admin/users/update`
  (reachable precisely because auth is bypassed). Real fix later: a component
  shouldn't need to log in when the backend has auth disabled.

---

## Blockers / known issues carried forward

- ~~**Kafka storage is INSIDE the container**~~ **FIXED 2026-07-29.**
  `docker-compose.yml` now uses `KAFKA_LOG_DIRS=/var/lib/kafka/data` on a named
  volume `natkit-v0-kafka-data` — matching what `docker-compose.portainer.yml` had
  always done (the dev/base stack was the outlier). **The existing 608M of topics
  was MIGRATED, not wiped**, and verified: all 7 topics at identical end offsets
  (Data 1,032,486 / Heartbeat 38,267 / 3 Marker / 2 Meta), a deep segment read at
  IMU offset 1,000,000, the 07-29 `finger-counting-1785336502546` markers readable,
  the backend enumerating 4 streams, and **the whole set surviving a full container
  recreate** — which is the point.
  - Gotchas worth remembering: `podman rm` a service with dependents needs
    `--depend` (kafka pins backend/bridge/control-plane/worker/frontend), and it
    took two passes plus a by-id `rm` to actually go. **podman-compose prefixes
    named volumes with the project** (`natkit_natkit-v0-kafka-data`), so a
    hand-created unprefixed volume is silently ignored and the broker comes up on
    an empty one — check `podman volume ls` after, not just the compose file.
  - Migration recipe (if ever needed again): `podman stop` kafka →
    `podman cp <c>:/tmp/kraft-storage /tmp/stage` → load into the volume via a
    root helper container (`cp -a` + `chown -R appuser:appuser`, so the uid lands
    right inside the userns) → recreate → compare `kafka-get-offsets`.
  - Still open, deliberately: **retention is 168h**, so a recorded session's
    markers/data still age out in 7 days. Permanence is Phase 3's job (materialize
    to Parquet), not a broker setting.
- **The bridge silently stops forwarding and never recovers.** Found it frozen for
  ~10 hours (last Kafka record 07-28 22:45) while the device was still publishing to
  MQTT; it had created **40,941** producers and did not exit, so `restart: always`
  couldn't help. `podman restart natkit-v0-bridge` restored flow immediately. This
  is why Zach's 07-29 08:48 experiment recorded ZERO data frames. Needs a real
  health check / fail-fast.
- **IMU frames are ~90% zero padding** — 100 sample slots carrying ~10 real
  samples. Now visible in exported Parquet. Possibly related to the known ADC stall.
- Everything this session is **UNCOMMITTED** (root repo + `libnatkit` submodule +
  new `plans/*.html`).
- `graphiti-memory` MCP was NOT available this session, so the architectural
  decisions above live in `plans/` + the auto-memory files instead of episodes.

---

## Prior Task (paused) — natKit-IMU firmware overhaul (Phase 2, CHECKPOINTED)

Plan: `plans/natkit-imu-esp-idf-c-overhaul-plan.html`. Full detail (root causes,
commits, gotchas) lives in the auto-memory `natkit-imu-overhaul-roadmap.md`.
Phases 0 + 1 DONE and HW-verified (frame envelope, heartbeat, sensor-regression
fix, MQTT reliability, heap-leak fix, dead-dep removal, boot MQTT retry, -frtti
drop). Phase 2 = migrate Arduino→ESP-IDF.

**Phase 2 re-baseline to ESP-IDF 5.x — DONE + HW-VERIFIED 2026-07-27.**
Re-baselined the platform (espressif32@6 / arduino 2.0.17 / IDF 4.4.7 → pioarduino
55.03.311 / arduino 3.3.11 / **ESP-IDF 5.5.5**, matching natVR). The firmware now
BOOTS + STREAMS on the ESP32-PICO-D4: BNO08x inits, WiFi + NTP + MQTT up, framed
`NatImuBulkDataSchema` at ~2.5/s, **zero crashes over 45s**. Branch
**`phase2-esp-idf5`** @ `69dd080`. The device is CURRENTLY running this build.

The fix = **`custom_sdkconfig`** in platformio.ini → pioarduino from-source
Arduino/IDF HybridCompile (builds esp-idf v5.5.5 libs with our overrides):
- `CONFIG_SPIRAM=n` + `CONFIG_BT_ENABLED=n` — prebuilt esp32 libs assumed a PSRAM
  board (`SPIRAM=y`, `RESERVE_INTERNAL=0`) + full BTDM (~64KB DRAM); PICO-D4 has
  neither → internal heap starved → esp_timer couldn't create its task at boot.
- `CONFIG_LWIP_CHECK_THREAD_SAFETY=n` — ESPNtpClient calls raw lwIP `udp_new()` off
  the TCPIP thread; IDF 5.x's default assert (old 2.0.17 had it off) killed it.
Commits on `phase2-esp-idf5`: `8f7b2fe` (arduino-3.x source fixes: WiFiEvent
ARDUINO_EVENT_*, wdt config struct, esp_mac.h), `d8287f4` (custom_sdkconfig fix +
project-local huge_app.csv), `69dd080` (gitignore HybridCompile artifacts +
drop stale Phase-2a files).

⚠️ GOTCHA: pioarduino & espressif32 both name themselves `espressif32` and SHARE
`~/.platformio/packages/framework-arduinoespressif32` — they can't coexist.
Switching between builds = `rm -rf` that framework dir + project `.pio`, then
rebuild. `experimental` is pinned `platform = espressif32@6.12.0` (`3124d98`).

**Branch state:** `experimental` @ `3124d98` = known-good arduino-2.0.17 build (was
verified streaming). `phase2-esp-idf5` @ `69dd080` = working ESP-IDF-5.x build.
NOT merged — pending user decision + frontend-render confirmation.

**Next:** (a) frontend-render check / longer soak on the IDF-5.x build; (b) decide
merge phase2-esp-idf5 → experimental; (c) continue Phase 2 by peeling subsystems to
native ESP-IDF (NTP → esp_netif_sntp first — removes the lwIP-assert workaround —
then esp-mqtt / esp_wifi; BNO08x native LAST) → eventually `framework = espidf`.

---

## Prior Task (paused) — Visual Programming Rework

**Last updated:** 2026-07-08
**Session duration:** ~2 sessions

### Active Task

Visual Programming Rework (`plans/visual-programming-rework-plan.html`) — a 9-phase
(0–8) sensor-agnostic reactive-canvas rework. **Phases 0 and 1 COMPLETE and
statically verified** (npm run check 0 errors, vitest 11/11, C++ backend builds,
smoke script compiles + extended). Live end-to-end run still pending (needs the
dev backend container restarted onto the freshly-built binary + auth creds).
Nothing committed.

### Phase 0 — De-EMG the seams (DONE)
- C++ `StreamViewerWebSocket.cpp`: `struct EmgTransformConfig` → `TransformConfig`
  with `using EmgTransformConfig = TransformConfig;` alias (16 other refs untouched).
  Env var was already generic (`NATKIT_TRANSFORM_THREADS`, EMG name a fallback).
- `EmgViewer.svelte` → `ChannelFrameViewer.svelte` (git mv) + 3 usage sites.
- `MlPipeline/fieldSelection.ts`: `getChannelFieldOptions(ChannelFramePreview)` —
  dropped `EmgDataMessage` coupling; old names kept as aliases; caller updated.
- `inferStreamType` channel-frame branch now uses
  `descriptorSupportsNumericChannelFrames(descriptor)` not schema-name matching.
- Note: the `"imu"|"muse"|"emg"` viewer ladder in StreamViewer/page.svelte is
  LEFT for Phase 2 (descriptor-driven viewer registry).

### Phase 1 — Node Catalog service + data-driven node rendering (DONE)
- Backend: `buildNodeCatalogJson()` + `list_node_catalog` action →
  `node_catalog` message. Each entry: node_type/kind/category/runner/
  config_fields/input_ports/output_ports/variadic_inputs (+ transform-only
  input_mappings/input_descriptor_paths/output_schema_name). Wraps the existing
  transform capabilities + static stream_source/combine/viewer/sink entries.
  New `handleListNodeCatalog`/`sendNodeCatalog` (declared in .hpp).
  `list_transform_capabilities` kept for backward compat.
- Frontend types: opened `TransformKind` to `KnownTransformKind | (string & {})`;
  added `NodeCategory`/`NodePortTemplate`/`NodeCatalogEntry`/`NodeCatalogMessage`/
  `ListNodeCatalogAction` and wired them into the unions. websocket.ts:
  `onNodeCatalog` callback + `node_catalog` dispatch.
- `VisualProgramming/page.svelte`: fetches `list_node_catalog` on connect, stores
  `nodeCatalog`, DERIVES `transformCapabilities` from it (single source of truth),
  passes `nodeCatalog` to the editor.
- `StreamGraphEditor.svelte`: new `nodeCatalog` prop; `utilityCatalog` derived +
  `addCatalogNode()` dispatcher + `utilityIcon()`; ALL THREE palette surfaces
  (command palette, context menu, sidebar) now render viewer/sink/combine from
  the catalog (transforms already were). Inspector config form replaced with the
  new shared `StreamViewer/NodeConfigFields.svelte` (dark-themed, catalog-driven).
- Deliberately did NOT retrofit `EmgTransforms.svelte` (legacy light-themed
  StreamViewer panel; dark NodeConfigFields would clash; slated for Phase 2/5).
- Smoke script `natkit_stream_graph_smoke.py` now asserts the catalog advertises
  the structural kinds + a compiled transform + required transform-entry fields.

### Phase 2 — Descriptor-driven viewers on-canvas (DONE, frontend-only)
- New `StreamViewer/viewerRegistry.ts`: `chooseViewerRenderer(descriptor, shape?)`
  → `muse | channel_frame | feature_vector | classification | inspector`, plus
  `isClassificationFrameLabels()`. Muse probe `descriptorLooksLikeMuse()` added
  to `schemaDescriptor.ts` (eeg.tp9/af7/af8/tp10 shape — NOT schema_name).
  Classification detected by channel-label shape (`predicted_class` +
  `confidence.*`, matching the backend `transformLdaClassify` output).
- New `StreamViewer/ClassificationViewer.svelte` (predicted class + confidence
  bars). Unit tests `viewerRegistry.test.ts` (10 cases; vitest now 21/21).
- Both surfaces now select the renderer via the registry, NOT sensor name:
  `StreamGraphEditor.svelte` viewer-node overlay (`liveRenderer` derived) and
  `StreamViewer/page.svelte` (`rendererKind` @const). The page's `inferStreamType`
  sensor ladder + the inline IMU markup were RETIRED — IMU now falls to the
  SchemaDescriptorInspector fallback (plan ships no IMU renderer). Removed the
  orphaned getAccuracy* helpers + IMU-only CSS.
- Decision (per plan's renderer list): NO IMU renderer — IMU → inspector.
- Deferred to Phase 3: `inferStreamType` still exists for buffer bucketing +
  the stream-type badge/count (the 3 typed buffers imu/muse/emg). The editor's
  now-unused `liveStreamType` prop + the parent's schema-name `inferLiveStreamType`
  also stay until the generic-frame refactor. Compact on-node viewer preview
  (vs the current expandable overlay) also deferred — not required by acceptance.
- Verified: npm run check 0 errors (8 pre-existing a11y warnings), vitest 21/21.
  No backend changes this phase. Live run still pending (Phase 1 needs the
  backend container rebuilt for the palette).

### Phase 3 — Sensor onboarding pipeline (core DONE; one sub-item deferred)
- Backend `StreamViewerWebSocket.cpp`: new free fn `formatNormalizedFrameAsJson`
  emits a generic `type:"frame"` channel-frame message. Added an ADDITIVE generic
  fallback at the end of the streaming dispatch loop (after the dynamic_cast
  chain): look up the record's descriptor via
  `DataSchemaDescriptorRegistry::getDefault().findBySchemaName`, run the existing
  `tryNormalizeNumericChannelFrame(record, descriptor)`, and if it matches emit
  `frame`. So ANY record whose descriptor matches the canonical channel-frame
  contract is projected with NO per-sensor formatter/dispatch edit. Existing
  imu/muse/emg/signal-frame branches are UNCHANGED (compat aliases).
- Frontend: `websocket.ts` routes `case "frame"` → `onEmgData` (alias of
  `emg_data`); `EmgDataMessage.type` broadened to `"emg_data" | "frame"` (+ optional
  `schema_name`). Both the StreamViewer page and VP editor share this WS, so a new
  channel-frame sensor buffers + plots (ChannelFrameViewer via the Phase-2 registry)
  and is band-passable (canonical_channel_frame input mapping matches its descriptor).
- Doc: `docs/SENSOR_ONBOARDING.md` (checklist + the contract table).
- Verified: C++ backend builds; npm run check 0 errors; vitest 21/21.
- DEFERRED (tracked): making `getAlternateTransformInputMappings()` a
  registrable/config-driven mapping registry (for sensors whose fields DON'T match
  the canonical contract, e.g. Muse-style nesting). Not required by the acceptance
  (a canonical channel-frame sensor onboards with zero code); it's a separate
  mechanism. The zero-code path today = publish the canonical channel-frame layout.
- NOT run end-to-end against a live new sensor (needs a running stack + a
  registered test schema); the frame path reuses the already-exercised
  tryNormalizeNumericChannelFrame used by the transform path.

### Phase 4 — First-class multi-sensor sessions (IN PROGRESS)
Map (from Explore): the session/marker PAYLOAD types (experiment.ts), the publish
transport (handlePublishSessionBundle → META + MARKER topics keyed on session_id),
the schemas (MarkerEventV1, SessionMetadataRecord), and the natVR run-discovery
(reconstruct_session, keyed on session/cue marker types + labels) are ALREADY
sensor-agnostic. EMG coupling is concentrated in: EMG_GESTURE_OPTIONS + the "rest"
filler literal + protocol_id "emg-gesture-cues-v1" (experiment.ts/cues.py), the
BufferedEmgSample-typed stream/frame wrappers, Hudgins features, and
select_model's rest/active gesture defaults.

**Slice A DONE — generic SessionProtocol model (frontend, verified):**
- `experiment.ts`: added `SessionProtocol` (protocol_id/label/classes/rest_class/
  repetitions/hold_s/rest_s/lead_in_s/tail_rest_s/seed) + `EMG_GESTURE_PROTOCOL`
  (the built-in as one instance) + `buildCueScheduleForProtocol()`. Generalized
  `buildCueSchedule` with an optional `restClass` (default "rest") so the filler
  class is no longer hardcoded. Backward compatible — EmgExperiment.svelte
  untouched, still works via the default.
- Tests `experiment.test.ts` (6 cases: a generic 3-class direction protocol +
  EMG backward-compat). vitest now 27/27; npm run check 0 errors.

**Remaining Phase 4 slices (NOT done — substantial):**
- Slice B: make "session" a first-class node kind. Backend: add to the kind
  allow-list (StreamViewerWebSocket.cpp ~L2004) + a validation branch (inputs, no
  output, like sink) + port normalization + a catalog entry. Frontend: a session
  node whose inspector authors a SessionProtocol and drives recording.
- Slice C: multi-sensor recording — the session node subscribes to N upstream
  source streams and records them under ONE marker timeline (shared session_id;
  runs = session lifecycle marker pairs). Simplest low-risk route: client-side
  recorder reusing the existing publish_session_bundle path (like EmgExperiment),
  NOT a new C++ recorder worker. Produce a labeled-dataset handle (named set of
  runs across the subscribed streams, one label column from the cue timeline).
- Slice D: make "training session" a first-class stored/discoverable object; natVR
  label-field generalization (cue_gesture → configurable label field).

**Slice B DONE — "session" is a first-class node kind (verified):**
- Backend `StreamViewerWebSocket.cpp`: added "session" to the kind allow-list +
  a validation branch (no output ports; >=1 connected input, no upper bound —
  multi-sensor) + port normalization (defaults to in1, clears outputs, multiple
  inputs preserved) + a start-dispatch branch (marks it "running"; recording is
  client-side, no worker/output stream) + a node-catalog entry (category
  "session", runner "frontend", variadic_inputs). The protocol persists in the
  node's generic `config` json (round-trips like transform config).
- Frontend: `SessionProtocol` MOVED to types.ts (shared home; experiment.ts
  imports + re-exports it — avoids a cycle). New `SessionNodeConfig` +
  `StreamGraphSessionNode` (config = {protocol, participant_id?, notes?}); added
  "session" to StreamGraphNodeKind + the node union. StreamGraphEditor:
  `addSessionNode` (generic 2-class default, 2 input ports) wired into
  `addCatalogNode`; a full protocol-authoring inspector section (label/id/classes
  (comma-sep)/rest_class/reps/hold/rest/lead-in/tail/participant/notes) with a live
  schedule summary via buildCueScheduleForProtocol+scheduleDurationMs.
  StreamGraphNode.svelte: ClipboardList icon + session meta.
- Smoke test: the graph now includes a session node (transform → session) and
  asserts it starts "running" with no output stream.
- Verified: backend builds; npm run check 0 errors; vitest 27/27; smoke compiles.

**Slice C DONE — client-side multi-sensor recorder (frontend-only, verified):**
- VP `page.svelte`: `publishSessionBundle()` forwards the bundle over the backend
  WS (mirrors saveStreamGraph); passed to the editor.
- `StreamGraphEditor.svelte`: `resolveSessionInputStreamIds` (stream_source →
  stream_id; transform/combine → runtime output_stream_id), `startSessionRecording`
  / `tickSessionRecording` / `finishSessionRecording`. On Record: generate a
  session_id from the protocol_id, publish a start bundle (metadata + session
  lifecycle start marker, device_ids = all resolved streams), run the cue timeline
  on a 100ms tick showing elapsed + active cue, and on completion/stop publish the
  cue markers (clipped to end) + a session end marker. One session_id spans every
  recorded stream → one labeled dataset. Record/Stop control + live cue display in
  the session inspector. Verified: npm run check 0 errors; vitest 27/27.

**Phase 4 ACCEPTANCE MET (Slices A–C).** Author a generic protocol → record N
sensors via the session node → one labeled session (single session_id, device_ids
spanning every recorded stream, cue + lifecycle markers) published through the
existing publish_session_bundle. natVR's reconstruct_session already discovers such
sessions and trains on the per-cue class label (stored in the marker's "gesture"
attribute, which already holds arbitrary class strings — no rename needed to train).

Deferred (cosmetic / Phase-5-adjacent, NOT blocking the acceptance):
- natVR "gesture" → generic "label" RENAME (functional training on arbitrary
  classes already works; this is naming hygiene). Filed under Phase 5's
  "make the label source generic" bullet.
- Stored-session DISCOVERY in the palette (needs a backend list-sessions action).
- Live end-to-end verification of the recorder (publish + timeline) — static only
  so far (type-check + unit tests + build + smoke-compiles), same live-stack
  constraint as the rest.

### Phase 8 — beginner UX (Part A DONE: starter templates)
- New `starterTemplates.ts`: `STARTER_TEMPLATES` presets ("View a stream", "Filter +
  envelope" = bandpass→rectify→lowpass_envelope→viewer, "Record a session" = source→session
  with a 2-class protocol). Each `build(sourceStreamId)` returns a fresh EditorGraphDefinition.
- Editor: `loadStarterTemplate` (loads a preset as a new board, auto-binding the source to
  the first available stream) + a "Starter templates" sidebar group.
- Verified: npm run check 0 errors; vitest 28/28; Playwright — the 3 starters appear and
  loading "Filter + envelope" populates a valid source-bound Band-pass→Rectify→envelope→viewer
  board (source auto-bound to the live EMG stream, "No validation issues"). Frontend-only.
**Part B+C DONE — PHASE 8 COMPLETE.**
- Part B (guided flows): `recommendedNextTransforms` derived from the selected node's OUTPUT
  descriptor (getOutputDescriptorForNode → transforms whose input mapping matches);
  "Recommended next" inspector panel with one-click `addRecommendedTransform` (adds a
  transform downstream + wires the edge). Fixed `getOutputDescriptorForNode` (streamGraph.ts)
  to return a REAL channel-frame descriptor for transform/combine outputs (was an empty stub)
  so compatibility + input-mapping auto-pick + recommendations resolve.
- Part C: inline node doc (capability.description) in the transform inspector; typed
  invalid-connection feedback (`connectionMessage` set on a descriptor-incompatible connect,
  shown as a dismissible note over the canvas).
- Verified: npm run check 0 errors; vitest 28/28; Playwright — node doc shows, "Recommended
  next" lists 8 compatible transforms. Frontend-only.
- Deferred (documented): train/classify starter presets (need model_path scaffolding);
  config-field-level descriptions in the backend catalog; dropdown/threshold param variants.

### Phase 7 — reactive execution + composite round-trip (IN PROGRESS)
**Part B DONE — composite round-trip (opaque backend metadata), live-verified:**
- Backend `StreamGraphDefinition` gained `nlohmann::json editorMetadata` (default null);
  to_json emits `editor_metadata` when non-null, from_json reads it verbatim — round-trips
  through save/persist/list with zero interpretation. The executed graph is still the
  flattened `nodes`/`edges`.
- Frontend: `StreamGraphDefinition.editor_metadata?: unknown` (types.ts). `saveDraftGraph`
  attaches the unflattened editor tree (stripped of any nested editor_metadata) to the
  flattened graph; `resolveDraftForGraph` falls back to `backendGraph.editor_metadata`
  when localStorage is absent → a composite graph reloads from the backend alone.
- Verified live (WS client): saved a graph with editor_metadata → save reply + list both
  return the composite tree (composite_id preserved) while flattened nodes stay primitive.
  npm run check 0 errors; vitest 27/27; backend builds. Test artifact: vp-composite-verify
  in the container store (ephemeral).
**Part A DONE — incremental reactivity, live-verified:**
- Backend `handleRestartStreamGraphNode(graph_id, node_id)` (new `restart_stream_graph_node`
  action): in a RUNNING graph, BFS the forward edge adjacency to get node_id + descendants,
  stop those transform/combine workers (stopGraphWorkerByOutputStreamId), then recreate
  them in topo order from the current stored config (createTransformWorker/createCombineWorker),
  resolving inputs from each node's stable output stream id (deterministic from
  output_identifier). Upstream/unrelated branches untouched. Updates runtime nodeStatuses +
  persists + pushes stream_graph_status. Guarded against concurrent stop/start via activeRunId.
- Frontend: RestartStreamGraphNodeAction type; VP page `restartStreamGraphNode()`; editor
  `updateTransformConfigField` → debounced (350ms) `scheduleReactiveRestart` that, only when
  the graph run_state==="running", saves the draft then restarts just that node's subgraph —
  no manual stop/start.
- VERIFIED live (WS, real EMG stream): started source→highpass_iir; edited cutoff_hz →
  restart_stream_graph_node → transform came back "live" with the same output id + "Restarted
  with updated config.", source stayed running. npm run check 0 errors; vitest 27/27; backend
  builds. Deferred: sampled live-value-on-node (plan nice-to-have, not in acceptance);
  run-gate for ML train nodes (train already gated behind an explicit Submit button).

**Part C DONE — param/input nodes, verified. PHASE 7 COMPLETE.**
- `composites.ts`: new editor-only `ParamNode` (kind "param") + `isParamNode`; added to
  `EditorGraphNode`. `flattenGraph` drops param nodes + any edge touching them (their value
  is already written into the target transform's config), so the backend never sees them.
  `updateSelectedNode` now also skips "param" (keeps its StreamGraphNode narrowing).
- Editor: `addParamNode` + palette entries (sidebar + ⌘K, SlidersHorizontal icon);
  `selectedParamNode` + `paramTargetFields` (numeric config fields of the bound transform);
  `applyParamValue` writes the param's value + the target transform's config[field] then
  drives the Part-A `scheduleReactiveRestart`; `updateParamBinding` for min/max/step/target.
  Param inspector (value slider + target transform + target field + bounds).
- StreamGraphNode.svelte: inline range slider on the param node card (mousedown
  stopPropagation so the drag doesn't move the node) → `onParamValueChange` → applyParamValue.
- Tests: composites.test.ts asserts flattenGraph drops param nodes + binding edges (28/28).
  npm run check 0 errors. Playwright-verified live: Param in palette, adds a node with an
  inline slider, inspector shows Value/Target transform/Target config field/Min/Max/Step.
- Frontend-only (no backend change). Acceptance met: a bound slider changes a transform's
  config and auto-restarts the downstream subgraph while running (Part A + C together).
- Deferred (plan nice-to-haves, not in acceptance): dropdown/threshold param variants
  (only the numeric slider shipped); sampled live-value-on-node.

### LIVE VERIFICATION — Phases 1–4 confirmed against the running podman stack (2026-07-09)
The dev stack was already rebuilt from my committed source (backend binary contains
all my Phase 1/4 strings). Verified two ways:
- **Backend protocol** (WS client run inside the ml-control-plane container, reaching
  ws://natkit-v0-backend:7409/ws/stream_viewer with the admin session cookie from the
  shared auth DB): `list_node_catalog` returns 20 node types across all 6 kinds incl.
  `session` (category=session, runner=frontend, variadic, 0 outputs); a transform→session
  graph SAVES (session config.protocol round-trips: classes ["a","b","c"]) and VALIDATES
  clean. Live EMG stream = 3ch×50 samples, ExgPillEmgDataSchemaV1, descriptor present.
- **Frontend visual** (Playwright/chromium headless at http://localhost:8080, admin
  cookie): VP palette is fully catalog-driven — Utility (Combine/Viewer/Sink/Session) +
  all transforms + live stream, no console errors. Adding a Session node shows the full
  protocol-authoring inspector (Protocol name/id, Classes, Rest class, Repetitions,
  Hold/Rest/Lead-in/Tail, Participant, Notes) + "Record session" button, and renders
  on-canvas with ports + "N classes" meta. Stream Viewer subscribed to the EMG stream →
  descriptor-driven registry picked the WAVEFORM renderer (1 Chart.js canvas, live
  rolling trace) + the SchemaDescriptorInspector header. Screenshots: /tmp/vp-session.png,
  /tmp/sv-viewer.png.
- Phase 3 generic `frame`: the EMG stream uses the concrete emg_data path (matches its
  dynamic_cast branch, as designed); the generic `frame` fallback only fires for a NEW
  unmatched schema (not observable live without registering a synthetic sensor schema) —
  verified by build + the shared tryNormalizeNumericChannelFrame logic.
- Test artifact: a `vp-verify` graph persisted in the backend CONTAINER's
  /libnatkit/data/stream_graphs.json (no delete action exists; not bind-mounted → vanishes
  on container recreate). Harmless; left in place (didn't restart the user's backend).

### Phase 5 — ML nodes on the canvas: DESIGN + DECOMPOSITION (not started)
Mapped the full surface (Explore). Key facts:
- Control plane = standalone Python `websockets` server on :8786 (NOT drogon), shared
  auth via NATKIT_AUTH_DB_PATH + natkit_session cookie on the WS upgrade. Actions incl.
  start_train_validate_job / get_job_status / stop_job / list_jobs / list_recorded_runs
  / list_workers / list_thread_slots (+ worker-facing register/heartbeat/claim/report).
  Messages: hello/recorded_runs/workers/thread_slots/job_list/job_accepted/job_status/
  error. Full contract already typed in frontend MlPipeline/types.ts.
- Frontend MlPipeline talks DIRECTLY to :8786 (MlControlPlaneWebSocket). startJob()
  payload: train_runs/eval_runs, families (MODEL_FAMILIES=lda|linear_svm|random_forest),
  selected_fields, rest/active gesture, window/hop/vote/confidence/min-hold. Decision #3:
  drop this direct connection; route through the backend /ws/stream_viewer.
- train_validate (natVR kafka_train_validate.py + select_model.py): families train,
  best selected by accuracy; LDA→JSON, SVM/RF→joblib. Field selection is EMG-constrained
  (regex ^channels\.(\d+)\.samples$). Control plane STRIPS model_path (ephemeral scratch)
  → no durable artifact surfaced today.
- classify LARGELY EXISTS: the lda_classify transform (loads LDA-JSON model_path, emits
  predicted_class + confidence.*) + the Phase-2 ClassificationViewer. But C++ loads ONLY
  model_type=="lda"; SVM/RF have no C++ inference path.
- Backend has NO outbound WS/HTTP client, but drogon ships drogon::WebSocketClient
  (third-party/drogon/lib/inc/drogon/WebSocketClient.h) — usable, no new dep.

Proposed slices:
- **B (proxy, foundational, decision #3):** backend gains a drogon::WebSocketClient to
  ws://control-plane:8786 (reconnect/backoff), presents an auth cookie on upgrade,
  forwards browser ML actions received on /ws/stream_viewer up to the control plane, and
  re-broadcasts hello/workers/thread_slots/job_list/job_status/error back down. Frontend:
  drop MlControlPlaneWebSocket; route ML actions/messages over the existing
  StreamViewerWebSocket. Verify via the WS client (list_workers/list_jobs flow through).
- **C (durable artifacts):** control plane surfaces a durable, addressable model_path
  (stop stripping it / persist artifacts outside ephemeral scratch) so train→classify
  can wire. natVR pytest-verifiable.
- **A (train node):** train node kind (backend allow-list/validation/catalog + frontend
  inspector authoring families/features/windowing/run+field selection, config on the
  node, like the session node) → submits via the proxy. classify already = lda_classify.
- **D (classify generalization):** either restrict classify to LDA (v1) OR add a C++
  joblib/ONNX inference path for SVM/RF. + natVR label-field generalization
  (cue_gesture → configurable) for non-gesture training.

DECISIONS (user chose): 1 = service identity (v1). 2 = LDA-only classify (v1).

**Slice B DONE — control-plane proxy (decision #3), LIVE-VERIFIED:**
- Backend: `AuthManager::createServiceSession(username)` mints a token for an existing
  user without a password (backend owns the auth DB). StreamViewerWebSocket gained a
  drogon::WebSocketClient to the control plane (env NATKIT_ML_CONTROL_PLANE_URL, default
  ws://127.0.0.1:8786; service user env NATKIT_ML_PROXY_USERNAME default "admin"):
  `ensureMlControlPlaneClient` (lazy connect + reconnect via loop->runAfter),
  `broadcastMlControlPlaneMessage` (wraps each control-plane frame as
  {type:"ml_control_plane",message:…} → all /ws/stream_viewer clients),
  `handleMlProxyAction` (browser {action:"ml_proxy",message:<cp-action>} → forwarded up;
  transient "connecting" error if not yet connected). Dispatch: action=="ml_proxy".
- Frontend: StreamViewerWebSocket gained onMlControlPlane + sendMlAction + the
  ml_control_plane/ml_proxy types. New MlPipeline `ProxiedMlControlPlane` adapter rides on
  the StreamViewerWebSocket (same MlControlPlaneWebSocket surface; connect/disconnect
  no-ops). MlPipeline/page.svelte now routes ML over its existing descriptorWsManager
  (onMlControlPlane→wsManager.handleMessage; sv onConnectionChange→wsManager.setConnectionState);
  the direct :8786 MlControlPlaneWebSocket + the Control-Plane-URL input are GONE.
- Compose: NATKIT_ML_CONTROL_PLANE_URL=ws://natkit-v0-ml-control-plane:8786 on the backend.
- VERIFIED live: hot-patched the new binary into the container, ran it on :7410 with the
  proxy env, connected a WS client with the admin cookie, sent ml_proxy list_workers →
  got the control-plane snapshot burst wrapped as ml_control_plane (hello service=
  natkit-ml-control-plane, workers×2, thread_slots, job_list) + periodic worker pushes.
  Both directions confirmed. npm run check 0 errors; vitest 27/27; backend builds/links.
  (Briefly bounced the :7409 backend during cleanup; it respawned via its CMD loop.)

**Slice C DONE — durable model artifacts (control plane), unit-verified:**
- `natkit_ml_control_plane.py`: `resolve_artifacts_dir()` (env NATKIT_ML_ARTIFACTS_DIR,
  default /models) + `persist_selected_model_artifact(report, job_id)` copies the winning
  model out of the ephemeral job workspace into <artifacts>/<job_id>/ BEFORE the workspace
  is rmtree'd. `sanitize_pipeline_report(report, model_path=None)` now surfaces
  `model_path` + `model_family` + artifact_storage "durable"|"ephemeral_scratch" (was
  always stripped). Wired into the in-process job path (_run_job_in_slot). Remote-worker
  jobs keep artifact_storage ephemeral (model stays on the worker fs — documented follow-up).
- Compose: shared `natkit-v0-models` volume — control plane rw (+ NATKIT_ML_ARTIFACTS_DIR=
  /models), backend ro at /models — so a classify node (lda_classify) can load model_path
  directly.
- Verified: py_compile; functional test in the control-plane container (persist copies the
  model, sanitize surfaces durable path/family, no-model→ephemeral). Full train→classify
  e2e not runnable here (needs recorded runs + a live pipeline).

**Slice A DONE — train node (backend + frontend), verified:**
- Backend (submodule 82ad060): "train" node kind mirroring session — allow-list,
  validation (no outputs; inputs optional — dataset via run selectors), normalization,
  start-dispatch (marks running; job submitted client-side), catalog entry (category
  "ml", runner "control_plane"). Smoke covers it. Live-verified: catalog=21 types incl.
  train; train graph validates clean.
- Frontend: TrainNodeConfig + StreamGraphTrainNode (types.ts). Editor: addTrainNode +
  a train inspector (families/train_runs/eval_runs/window_ms/hop_ms) + "Submit training
  job" button + job-status + model-path display; StreamGraphNode Cpu icon + meta. VP
  page.svelte: onMlControlPlane→handleMlControlPlaneMessage (tracks trainJobStatus +
  trainModelPath from job_accepted/job_status), submitTrainJob() sends
  start_train_validate_job via wsManager.sendMlAction (through the Slice-B proxy). Props
  passed to the editor. Verified: npm run check 0 errors; vitest 27/27; Playwright — Train
  in palette, adds a node, inspector shows the train-spec form + Submit button, no console
  errors. Full train RUN needs recorded runs (not available here).

PHASE 5 essentially COMPLETE: B (proxy) + C (durable artifacts) + A (train node) done +
verified; classify = the existing lda_classify transform + ClassificationViewer (wire a
train node's model_path into an lda_classify node's model_path config to run predictions).
Remaining minor: D = natVR "gesture"→"label" rename (cosmetic; training on arbitrary
classes already works) + SVM/RF C++ inference (deferred; classify LDA-only for v1) +
remote-worker durable artifacts. Test artifacts left in the backend container's
stream_graphs.json: vp-verify, vp-train-verify, "verify" (ephemeral; vanish on recreate).

Phase 6 (script nodes) deferred by design. Phases 7 (reactive/composite round-trip) + 8
(beginner UX) remain and are independent of the control-plane work.

---

### (Prior task — still shippable) C ABI Multi-Language Bindings plan (`plans/c-abi-multi-language-bindings-plan.html`)
— Phases 1, 2, 3a, 3b COMPLETE. **Phase 4 (Kafka transport ABI) COMPLETE and
verified against a live broker: transport foundation + all four Python clients
(session_publish, replay, emg_consumer, reconstruct_session) migrated onto the
ABI. Only remaining item is a real docker build to validate librdkafka
packaging (unverifiable in this env).**

## Completed This Session (C ABI, Phase 4 — Kafka transport ABI)

Architecture decision (from the user): keep the two trees separate —
`libnatkit-core` stays the lean, embedded/ESP-friendly C-ABI-over-C++ library
(no librdkafka, ever); the full `libnatkit` tree grows its OWN C ABI layer that
binds out to its C++, bound separately from Python. Resolved plan Open Q #3.

- **Prerequisite thread-safety fix (was a tracked gap):** the meta-record
  registration guards reached by `createBrokerManager` →
  `Registry::createDefaultInitalizeRegistry()` are now safe.
  `ensureSessionMetadataRecordRegisteredForMetaRecord` /
  `ensureTransformProvenanceRecordRegisteredForMetaRecord` use `std::call_once`;
  the shared `metaRecordDecoders()` map is `std::mutex`-guarded on every
  read/write (`MetaRecord.cpp`, decoder copied out under lock, invoked outside).
  ABI_CONVENTIONS.md audit table updated: gap CLOSED. Core rebuilds; ctest passes.
- **Kafka C ABI** `libnatkit/libnatkit/include/libnatkit-kafka-abi.h` (pure C,
  reuses core's NAT_* status enum). Opaque `nat_kafka_broker_t*` /
  `nat_kafka_messenger_t*` handles; `nat_kafka_v1_` symbols: broker
  create/destroy/list_topics, messenger create/destroy/send/flush/try_recv.
  try_recv uses two-call peek semantics (no dropped msg on too-small buffer).
- **Shim** `.../core/kafka/.../abi/KafkaAbi.cpp` over BrokerManager +
  TopicMessenger raw send/recv (bytes in/out — no schema decode on the hot path).
  Plumbed a `start_offset` param (OFFSET_END live-tail / OFFSET_BEGINNING
  historical) through createMessenger → BrokerMessagingQueue → startConsumer
  (defaulted, backward-compatible). Added `flush()` to MessagingQueue (no-op
  default) / TopicMessenger / BrokerMessagingQueue for one-shot-producer
  durability.
- **Build:** new `libnatkit-kafka` SHARED target (the ABI layer, distinct from
  the `libnatkit-core-kafka-cxx` transport target) →
  `liblibnatkit-kafka.so`. New `-DBUILD_KAFKA_ABI_ONLY=ON` lean option builds
  only util+kafka-cxx+shim+core+librdkafka (skips mosquitto/mqtt/bridge/tools/
  backend; needed GNUInstallDirs + BUILD_TESTING OFF in lean mode). Verified:
  full build AND a from-scratch lean build both produce the .so; all 8 symbols
  exported; loads via ctypes with its dep chain resolving through rpath.
- **Symbol baseline** `.../core/kafka/abi/symbols.txt` + `check_abi_symbols.sh`
  (mirrors core lib); passes.
- **Python** `natVR/src/natvr/libnatkit_kafka.py`: own discovery +
  `LIBNATKIT_KAFKA_PATH`, `KafkaBroker`/`KafkaMessenger` (context-managed) and a
  confluent-`Producer`-shaped `KafkaProducer` adapter (produce/flush).
- **Acceptance test** `natVR/tests/test_libnatkit_kafka_abi.py` (skips w/o .so or
  broker): shim→shim round trip (incl. empty + binary payloads) AND
  byte-for-byte wire-compat with confluent-kafka in BOTH directions. Passes
  against the live broker on 127.0.0.1:29092.
- **Producer migration pilot:** `session_publish.py` now uses `open_producer()`
  (ABI-preferred, confluent fallback, `NATVR_KAFKA_TRANSPORT` override).
  Verified end-to-end: published via ABI, read the exact bytes back via
  confluent. Full natVR suite: 75 passed, only the 2 known pre-existing failures
  (WindowInferenceResult ctor TypeError; flaky ML-accuracy smoke) remain.
- **Docker:** `Dockerfile_natkit_ml_control_plane` extended to build the kafka
  shim via the lean option + set `LIBNATKIT_KAFKA_PATH` (added librdkafka apt
  build-deps). NOT built in this env (no docker) — needs a real image build to
  confirm the from-source librdkafka step / apt deps.

## Completed This Session (C ABI, Phase 4 — production migration)

All four Python Kafka clients migrated onto the ABI, with a shared transport
selector `natVR/src/natvr/kafka_transport.py` (ABI-preferred, confluent-kafka
fallback; `NATVR_KAFKA_TRANSPORT=auto|abi|confluent` override):

- `session_publish.py` + `replay.py` (producers) use `open_producer` →
  `KafkaProducer` (added a no-op `poll()` for replay's confluent-shaped calls).
- `emg_consumer.py`: `StreamKafkaConsumer` now builds its consumer via
  `open_stream_consumer`. New `KafkaConsumer` adapter in `libnatkit_kafka.py` is
  confluent-`Consumer`-shaped (one messenger per topic, round-robin blocking
  `poll(timeout)`, `_ConsumerMessage` with value/topic/partition/offset/error).
  All three high-level consumers (Emg / EmgAndMarker / SessionMetadata) ride on
  it unchanged. offset() is a synthetic per-topic counter (raw ABI has no broker
  offsets; consumers use in-payload seq_no/emitted_at_us) — documented.
- `reconstruct_session.list_broker_topics` → `KafkaBroker.list_topics()`.
- Semantic note: the ABI has no consumer groups / committed offsets — each
  consumer reads from its start_offset (earliest→BEGINNING, latest→END);
  group_id is ignored. Suits natVR's one-consumer-per-stream usage.
- **Verified live** (broker on :29092): new
  `test_migrated_consumer_stack_over_abi` produces an EMG frame + marker via the
  ABI and decodes both through the migrated `EmgAndMarkerKafkaConsumer` (asserts
  it's the ABI `KafkaConsumer`, not confluent). 3/3 kafka tests pass; full natVR
  suite 76 passed, only the 2 known pre-existing failures remain.

## Docker packaging — VALIDATED (podman)

- `podman build -f Dockerfile_natkit_ml_control_plane -t natkit-ml-cp-test .`
  succeeds (exit 0): from-source librdkafka builds in-image, the lean
  `BUILD_KAFKA_ABI_ONLY=ON` path links `liblibnatkit-kafka.so`, and
  `LIBNATKIT_KAFKA_PATH` is set. The apt build-deps (libssl-dev/zlib1g-dev/
  libsasl2-dev/libzstd-dev) were sufficient.
- Runtime verified inside the image: `natvr.libnatkit_kafka._load_library()`
  discovers the .so via the env var and binds all 8 `nat_kafka_v1_*` symbols;
  `libnatkit_core` also loads. Note: env is **podman**, not docker
  (`podman 5.8.0`).
- Minor optimization left on the table: the Dockerfile builds libnatkit-core
  twice (once via STANDARD_BUILD for LIBNATKIT_CORE_PATH, once as the lean
  build's ExternalProject). Works; could dedupe to one build later.

## Phase 4 — COMPLETE, switched over to the ABI

- **Switch done:** `NATVR_KAFKA_TRANSPORT` default flipped `auto`→`abi` in
  `kafka_transport.py`. The ABI is now the committed transport with no silent
  fallback; confluent-kafka is reachable only via explicit
  `NATVR_KAFKA_TRANSPORT=confluent`. Suite still 76 passed (2 pre-existing
  fails); `.so` auto-discovers from the build tree so a plain checkout works.
- **DEPLOYMENT REQUIREMENT:** with the hard `abi` default, any process running
  this code MUST have `liblibnatkit-kafka.so` (the updated
  Dockerfile_natkit_ml_control_plane builds it + sets LIBNATKIT_KAFKA_PATH). The
  control-plane/worker image must be REBUILT from that Dockerfile or the pipeline
  fails loudly. Definitive ABI tell in logs: "[Kafka] Initializing Kafka Broker
  Manager…" (only the C++ BrokerManager prints that).
- **confluent-kafka FULLY REMOVED from natVR.** `kafka_transport.py` is pure-ABI;
  the last two direct users migrated (transport-only — the Phase 5 *architecture*
  question stays deferred):
  - `classifier.py`: producer now `open_producer()` (`confluent.Producer` gone);
    its consumers were already the migrated ABI ones. Added `producer.close()`.
  - `bridge/hand_state_bridge.py`: consumer now `open_stream_consumer()`;
    dropped the confluent `Consumer/KafkaError/OFFSET_END/TopicPartition` import
    and the (ABI-inert) PARTITION_EOF branch.
  - Removed `_optional.require_confluent_kafka` (last user gone) and dropped
    `confluent-kafka` from `natVR/pyproject.toml`.
  - `test_libnatkit_kafka_abi.py`'s confluent wire-compat cross-check still runs
    while confluent happens to be installed (importorskip), skips otherwise.
  - (The only remaining confluent imports in the repo are under `deprecated/` —
    a separate old codebase, image-excluded, not natVR.)
  - Verified: all modules import, suite 76 passed / 2 pre-existing fails.

## Also this session (ML pipeline unblock — NOT Kafka-related)

- `docker-compose.dev.yml`: removed the `ml-worker` profile gate (worker now
  starts by default); added a shared `natkit-v0-auth` volume + `NATKIT_AUTH_DB_PATH`
  on backend + control-plane so login sessions (written by the C++ backend's
  Auth.cpp) resolve on the control-plane WS — fixed "authentication required" /
  0 visible slots. Root cause was a pre-existing WIP auth-wiring gap, not our work.
- Everything is uncommitted (libnatkit + nested libnatkit-core submodules +
  untracked natVR + compose/Dockerfile at repo root).

## Prior Phase status (still true)

## Completed This Session (C ABI, Phase 3b — EMG rollout)

- Rolled the two-call JSON pattern out to ExgPillEmgDataSchemaV1:
  `nat_core_v1_emg_frame_encode_json` / `_decode_json` in
  `ExgPillEmgDataSchemaV1.cpp` (declared in `libnatkit-core-abi.h`, added to
  `abi/symbols.txt` — now 13 symbols).
- Refactored the Python two-call machinery into shared
  `natVR/src/natvr/libnatkit_schema.py` (generic `_transcode` + marker & emg
  wrappers); `libnatkit_marker.py` is now a thin re-export (existing imports/
  tests unchanged).
- `natVR/tests/test_libnatkit_emg_abi.py`: parity + byte-stable round trip vs
  the Python `natvr.models` decoder, plus int16-range rejection. Frames use the
  real producer wire format seeded from recorded session params (no raw EMG
  capture exists in-repo — only markers/features/metadata). 4 tests pass.
- SessionMetadataRecord: intentionally NOT duplicated into a two-call symbol —
  it already has a working callee-allocates ABI wired into models.py via
  `libnatkit_meta`. Documented in ABI_CONVENTIONS.md.
- Full natVR suite: 73 passed, only the 2 known pre-existing failures remain
  (unrelated); 3 pre-existing collection errors in ml_* tests are a
  `natkit_auth_shared` script-path issue, also unrelated.

## Scope note on "rewire consumers"

- Did NOT reroute `emg_consumer.py`/`natvr.models` hot-path decode through the
  ABI. The plan puts consumer migration in Phase 4 ("Migrate emg_consumer.py …
  onto it"), and rerouting now would (a) add a hard runtime lib dependency to
  basic model decode, (b) change decode strictness on the live path, and (c)
  need a broker-level integration test to validate. The CI parity tests
  (marker + emg) already pin the C++ and Python decoders together, which is the
  anti-drift guarantee; one implementation becomes authoritative when consumers
  migrate in Phase 4.

## Completed This Session (C ABI, Phase 3a — MarkerEventV1 JSON pilot)

- Added the two-call variable-length JSON ABI for MarkerEventV1:
  `nat_core_v1_marker_event_encode_json` / `_decode_json` in
  `MarkerEventV1.cpp` (declared in `libnatkit-core-abi.h`, added to
  `abi/symbols.txt`). Both round-trip through the shared C++ `MarkerEventV1`;
  they coincide for the JSON-wire marker but exist as distinct symbols for API
  symmetry / future wire-format changes.
- Python ctypes wrapper `natVR/src/natvr/libnatkit_marker.py` mirroring
  `libnatkit_meta.py` but using the two-call size/fill pattern (NULL buffer to
  size, allocate, fill) instead of callee-allocates + `nat_free_bytes`.
- Acceptance test `natVR/tests/test_libnatkit_marker_abi.py` against REAL
  captured payloads (`natVR/tests/data/marker_events_real.jsonl`, a 6-line slice
  of `captures/reconstructed/...run-01.markers.jsonl`): asserts C++ decode ==
  Python `natvr.models` hand-decoder field-for-field, byte-stable idempotent
  round trips, and cross-direction encode agreement. 4 tests pass.
- Deliberately did NOT rewire `emg_consumer.py`/`models.py` onto the ABI — that
  is Phase 3b.

## Completed This Session (C ABI, Phases 1 & 2)

- **Pure-C ABI header** `libnatkit/lib/libnatkit-core/include/libnatkit-core-abi.h`:
  moved the existing `extern "C"` block out of `libnatkit-core.hpp` (which now
  `#include`s it) so FFI generators (bindgen/jextract/Panama) can parse it, and
  added the `NAT_*` status-code enum + ABI conventions in the header comment.
- **Moved `stableStreamId()`** (FNV-1a, `0->1` fallback) out of the anonymous
  namespace in `StreamViewerWebSocket.cpp` into `nat::core::stableStreamId`
  (declared in the header, implemented in `BasicTopicInformation.cpp`); the
  backend now calls the shared function. Single source of truth.
- **New ABI functions** in `BasicTopicInformation.cpp`:
  `nat_core_v1_stream_id` (fixed output), `nat_core_v1_topic_build` and
  `nat_core_v1_topic_parse` (both use the new two-call size/fill pattern for
  variable-length string output — this is the pattern Phase 3a will extend to
  JSON). identifier validated against `^[A-Za-z0-9][A-Za-z0-9_-]*$`.
- **Python ctypes binding** `natVR/src/natvr/libnatkit_core.py` (mirrors
  `libnatkit_stitch.py`, reuses its `find_libnatkit_core` discovery). `topics.py`
  now delegates all topic building to it — the Python FNV reimplementation is
  gone. `test_models.py::test_topic_helpers` still passes byte-for-byte.
- **Golden vectors** `libnatkit/lib/libnatkit-core/tests/stream_id_golden.json`
  read by BOTH the C++ test (`tests/stream_id_abi_test.cpp`, built with
  `-DLIBNATKIT_CORE_BUILD_TESTS=ON`, wired into ctest) and the Python test
  (`natVR/tests/test_libnatkit_core_abi.py`). Covers UTF-8 identifiers and the
  63-bit-mask / `0->1` post-condition. Both pass.
- **Phase 2 deliverables:** ABI conventions doc `docs/ABI_CONVENTIONS.md`
  (incl. a thread-safety audit — new Phase-1 fns are safe; the pre-existing
  `nat_session_metadata_record_*` registration guard is NOT thread-safe on first
  concurrent use, documented as a tracked gap), append-only versioning policy,
  `abi/symbols.txt` baseline + `scripts/check_abi_symbols.sh`, and
  `.github/workflows/abi.yml` (build + ctest + symbol diff).
- **Verified:** libnatkit-core builds; ctest passes; 4 Python ABI/topic tests
  pass; the full `libnatkit-natkit-backend` recompiles and links against the
  moved symbol. All changes are in the `libnatkit` + nested `libnatkit-core`
  submodules and untracked `natVR/` — nothing committed.

## Not Done (later phases, own ships)

- Phase 4: `extern "C"` shim over `BrokerManager`/`TopicMessenger` in a separate
  shared lib + `librdkafka` packaging in the Docker image (heavy lift).
- Fix the tracked thread-safety gap in `ensureSessionMetadataRecordRegisteredForMetaRecord`
  (use `std::call_once`) before those fns are called from multiple GIL-released
  Python threads.
- Pre-existing unrelated `test_models.py` failures (WindowInferenceResult ctor
  signature; a flaky ML-accuracy smoke assertion) — NOT caused by this work.

## Prior Task (still shippable)

Stream Graph Programming plan — FUNCTIONALLY COMPLETE (details below).

## Completed Prior Session

- Audited the existing implementation against the plan's Implementation Checklist,
  Validation Algorithm, and Acceptance Tests (frontend types/websocket/page.svelte/
  StreamGraphEditor.svelte and backend StreamViewerWebSocket.cpp/.hpp in the
  `libnatkit` submodule were already ~95% built out from a prior session).
- Fixed `handleSaveStreamGraph` (libnatkit `StreamViewerWebSocket.cpp`) so it no
  longer rejects saving a graph that fails validation — drafts can now be saved
  incomplete/invalid and iterated on, matching the plan's `draft` state semantics.
- Fixed `handleStartStreamGraph` so transform/viewer/sink nodes whose upstream
  transform failed to start are marked `blocked` (not generic `error`) with the
  upstream node id named in the diagnostic message, per the plan's Execution
  Semantics section.
- Added `libnatkit/scripts/natkit_stream_graph_smoke.py`, a manual smoke-test
  script that saves/validates/starts/stops a two-node graph over the real
  WebSocket protocol and asserts node states/output stream ids (checklist item 11
  — no backend test coverage existed before this).
- Verified `libnatkit-natkit-backend` builds clean after the fixes and
  `npm run check` (svelte-check + tsc) in `frontend/` passes with 0 errors
  (6 pre-existing a11y warnings only, unrelated to graph work).

- Split `StreamGraphEditor.svelte` (was 2176 lines) into three files at the
  user's request: `streamGraph.ts` (pure helpers — `createEmptyGraph`,
  `cloneGraph`, `sanitizeIdentifier`, `getNodeHeight`, `getPortPosition`,
  `buildDefaultTransformConfig`, `getOutputDescriptorForNode`,
  `graphRunStateClass`, plus the `GraphStreamOption` type) and
  `StreamGraphNode.svelte` (presentational node-card component). Canvas/
  palette/inspector/context-menu stayed together in `StreamGraphEditor.svelte`
  (now 1820 lines) since they share mutable interaction state (drag/pan/
  pending-connection/context-menu) that would need lifting to split further.
  `svelte-check` still passes with 0 errors after the split.

## Not Done / Optional Remaining Work

- No provenance record is emitted with a "stop reason" when `stop_stream_graph`
  runs (plan's Provenance and Lineage section mentions this as a nice-to-have).
- The smoke test script requires a live backend + an existing stream id and has
  not been run end-to-end against real hardware/broker data in this session.

## Next Steps

- If picking this back up: run `libnatkit/scripts/natkit_stream_graph_smoke.py`
  against a live backend with a real EMG-like stream to validate end-to-end.
- Otherwise this plan can be considered shippable as-is.

---

*For historical decisions and failed approaches, query graphiti-memory.*
