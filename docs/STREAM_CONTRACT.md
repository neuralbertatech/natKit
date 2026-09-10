# The Stream Contract

_What a Visual Programming graph edge promises, and what an operator on one may
assume. Every clause here is enforced by code in the tree — this page describes
the runtime, it does not propose one._

The graph runtime is a **push-based dataflow of independent workers connected by
bounded channels**: one worker per node, one channel per edge, no central
scheduler. In Rx terms every edge is a **hot, lossy Observable** with the loss
policy chosen in advance rather than negotiated. Nothing here is novel; it was
built one node at a time and never written down, so each new node re-derived it.

Read this before adding a node type. The last section is a checklist.

---

## The six clauses

### 1. Channels are hot

A channel produces whether or not anybody is consuming, and a late subscriber
receives what arrives from then on — never history.

The one exception is a **root Kafka source**, which can start at an offset:
`makeGraphSourceMessenger()` takes a `start_offset`, and its comment states the
asymmetry plainly — in-process channels are live and "can't seek Kafka history,
so the offset only applies to a Kafka root source". An operator therefore may not
assume it has seen a stream from its beginning.

### 2. Loss is a policy, applied at the consumer

Each channel is bounded. When a subscriber's slot is full, the **oldest** frame in
that slot is evicted and the producer is never blocked.

- `InProcessChannelPolicy` (`InProcessTransport.hpp`:47) — `capacity = 256`,
  `overflow = DropOldest`.
- **Capacity counts frames, not samples**, "so a rate-changing stage (e.g. sliding
  window emitting one frame per N samples) needs no special case beyond sizing".
- **Each consumer gets its own FIFO slot**, so a slow consumer cannot starve its
  siblings; `publish()` fans one reference-counted handle out to every slot.
  Fan-out is therefore per-subscriber buffered, and **a drop is per-subscriber** —
  one slow viewer does not cost the trainer its frames.
- Overridable per deployment with `NATKIT_INPROCESS_CHANNEL_CAPACITY`.

Why drop-oldest rather than backpressure: **the producer at the head of the graph
is a sensor, and a sensor cannot be asked to slow down.** For live monitoring the
freshest frame is also the most valuable, so evicting the oldest is the correct
loss, not merely the convenient one.

### 3. `Block` exists, and no graph edge uses it

`InProcessOverflowPolicy` has a second member — `Block`, "for the rare edge that
requires lossless handoff and can tolerate throttling its producer"
(`InProcessTransport.hpp`:31). It is implemented (`InProcessTransport.cpp`:36) and
exercised by tests, and **`graphInProcessChannelPolicy()` never selects it**, so
today every graph edge is `DropOldest`.

This is a deliberate default, not a missing feature, and the distinction matters
for any future join or batch operator: the mechanism for lossless handoff is
already there. The rule for reaching for it:

> `Block` is legitimate only on an edge whose producer is **another graph node**.
> It must never appear on an edge fed directly by a sensor, because blocking
> there propagates back to a producer that cannot comply and the frames are lost
> anyway — just less visibly, and further upstream.

### 4. Time is `device_ts_us`, never arrival

Every temporal operator — window, debounce, dwell, refractory, join tolerance —
**must** read the frame's `device_ts_us`. An operator that reads the wall clock
makes replay disagree with live and makes a fast replay disagree with a slow one.

The test that enforces this is available and strong: **replaying a recording at
`max` speed must produce byte-identical output to replaying it at 1×.** Any
operator that fails it is reading the wrong clock.

Note that the timestamp reaching the graph has already been **transformed**. The
leaf ships raw device time and deliberately does not correct it; the clock fit
travels separately in the node-status frame "so raw device time survives to the
gateway and the correction stays undoable" (`espnow_link.cpp`:1366), and the shift
to wall clock happens at the last hop via `rewriteFrameTimestamps(...,
node->last_sync, primary_to_wall)`.

### 5. Errors are values, not terminations

A failed sensor is **data**, never an event that ends a stream. IMU frame v2
carries per-sample `has_data` bits with sample-and-hold in the floats, so a dead
report is expressible in-band.

This is the clause that most sharply diverges from Rx, where `onError` is terminal
and the expected response is a resubscribe. Terminating a stream here would couple
independent sensors: one leaf dying would stop the other five, which is precisely
the failure shape TEC-NATKIT-85 exists to prevent.

**An operator must not throw on bad input.** It emits a frame marked invalid, or
it emits nothing and counts the input; it does not end the channel.

### 6. Live never completes; a recording does

A live channel has no end. A replayed recording does. The same operator must work
on both — that is what makes record and replay a matter of swapping the source
rather than maintaining a second code path.

An operator holding state must therefore be correct when its stream simply stops
mid-window (live, sensor unplugged) *and* when it ends deliberately (replay,
recording exhausted). Neither is an error.

### 7. Transport is not part of the contract

An edge is an in-process ring buffer or a Kafka topic, chosen per edge from
colocation, and **a node cannot tell which it got.** Both sides rendezvous on a
deterministic channel id equal to the topic id, so an edge can be moved between
transports without touching node code.

---

## Ordering, and what `seq_no` promises

**`seq_no` is part of the contract.** Gap detection is a promise the runtime makes
and operators may rely on it.

Ordering at ingress is canonical: once a frame is in the pipe, its position is the
truth. `seq_no` is what makes a frame that *never arrived* distinguishable from one
that arrived late.

There are **three independent sequences** on the path and they answer different
questions. Do not substitute one for another:

| Sequence | Stamped by | Detects | Blind to |
|---|---|---|---|
| frame `seqNo` | the **leaf** (`leaf.cpp`:96/127/134) | loss anywhere on the path, end to end | which hop lost it |
| `uplink_seq` | the **primary→gateway serial link** (`gateway.cpp`:279) | loss on the serial hop only | ESP-NOW loss |
| Kafka offset | the **broker** | ingress order | everything upstream of ingress |

Nothing downstream rewrites the leaf's `seqNo`. The primary reads it and derives
`seq_gaps`, `seq_duplicates` and `seq_restarts` per node
(`espnow_link.cpp`:~1356), so per-device loss is already measured before the graph
ever sees a frame.

Two levels of absence, both already expressible, with no silent hole between them:

- **a missing sample inside a frame** — the `has_data` bit for that report
- **a missing frame** — a gap in `seq_no`

⚠️ **Kafka offsets are not yet a usable canonical order.** The producer selects a
partition at random with a null key and the consumer reads a hardcoded partition 0;
this works only because no topic currently has more than one partition. Until
TEC-NATKIT-108 is fixed, do not build an operator that relies on Kafka ordering
across a topic.

---

## Monotonicity: non-monotonic `device_ts_us` is not permitted

The runtime enforces a non-decreasing clock per channel **at ingress**, so no
operator has to defend against a backwards step individually.

### The rule

Let `w` be the highest `device_ts_us` seen on this channel, and `Δ` the expected
frame interval — computed from the normalized frame's own `sampleRateHz` and its
per-channel sample count, both of which every contract-matching frame carries, so
the bound scales with the stream instead of being a magic constant.

| Incoming timestamp `t` | Action |
|---|---|
| `t >= w`, within `k·Δ` of `w` | accept, advance `w` |
| `t < w`, within `k·Δ` of `w` | **log an error, clamp to `w`**, preserve the raw value, accept |
| further than `k·Δ` from `w`, either direction | **a fault** — see below |

So `1, 3, 5, 7, 6, 9` is republished as `1, 3, 5, 7, 7, 9`.

### A discontinuity is only accepted when something independent corroborates it

A wild jump is never resolved from the timestamp alone. Clamping is not
self-healing in the forward direction — one frame with a garbage-high timestamp
would raise `w` permanently and clamp every good frame after it for the rest of the
run — so a large jump is a fault, and it becomes a **new epoch** (reset `w`, reset
operator state, log) *only* if an independent signal agrees:

- a **sequence restart** for that device — already counted as `seq_restarts`, whose
  own comment reads "Strictly backwards: the leaf rebooted and began a new
  sequence"
- a **new clock fit** for that device, arriving on the node-status frame

Otherwise the frame is dropped as corrupt and counted. **A reboot must never be
clamped**: a restarted leaf legitimately starts lower, and clamping pins the whole
post-reboot run to the pre-reboot watermark.

### Where the clamp goes, and why it must keep the original

Apply it **after the last transformation, and preserve the pre-clamp value on the
frame.**

Backwards motion is usually not the leaf's fault. `node->last_sync` updates as
syncs arrive, so two consecutive frames can be shifted by two *different* clock
fits — a perfectly monotonic leaf clock can yield non-monotonic wall time. A clamp
that discards the original enforces monotonicity by destroying the evidence, and a
clock-fit regression becomes invisible. Keeping the raw value is the same principle
the firmware already follows in keeping its own correction undoable.

### Consequence: duplicate timestamps exist

Clamping makes two frames share a `device_ts_us`. Anything that treats it as a
unique key, sorts on it without a tiebreak, or joins on equality will meet the
pair. **`seq_no` is the tiebreak.** Specifically:

- a `zip`-style join must not match the same frame twice
- a threshold must not fire twice on a clamped pair
- a gate must not open twice

---

## What is counted, and what is not

Drop accounting already exists and is already on the wire.
`InProcessChannelMetrics` (`InProcessTransport.hpp`:58) is collected per channel
and published on the graph-status surface under
`node_statuses[<node>].channel` (`StreamViewerWebSocket.cpp`:2269):

```
transport: "in_process"
channel: { subscribers, published, dropped, depth }
```

So the counter's scope is settled by construction: **keyed on the producing node's
output channel, and its lifetime is the channel's — which is the graph run**, since
channels are created at start.

Two real gaps to know about rather than rediscover:

1. **`dropped` is summed across all subscribers** (`InProcessTransport.cpp`:101).
   With fan-out you learn that the edge dropped frames, not which consumer dropped
   them — so a single slow viewer looks identical to uniform overload.
2. **Kafka edges report no metrics at all.** The status annotation sets
   `transport: "kafka"` and stops. Drop visibility is asymmetric across a
   distinction clause 7 says a node cannot see.

⚠️ Cross-check any of these counters against an independently computed figure
before quoting one. Counters in this tree have measured something other than their
name on more than one occasion.

---

## Checklist for a new operator

1. **Read `device_ts_us`, never the wall clock.** If your operator has any notion
   of duration, this is the clause that decides whether it is correct.
2. **Assume a non-decreasing clock, and expect duplicates.** Monotonicity is
   guaranteed; uniqueness is not. Tiebreak on `seq_no`.
3. **Never throw, never terminate.** Bad input yields a frame marked invalid or no
   frame and a counter.
4. **Work on a stream that stops** — both mid-window and at a clean end.
5. **Assume nothing about transport,** and do not assume you saw the stream's
   start.
6. **Do not reach for `Block`** unless your upstream is another graph node, and say
   why in the code.
7. **Prove it with a replay.** Byte-identical output at 1× and at `max` speed is
   the test that catches every clock mistake at once.

---

## Related

- **TEC-NATKIT-102** — the epic this page underpins
- **TEC-NATKIT-103** — `combine`'s join policies, the first consumer of the
  duplicate-timestamp rule
- **TEC-NATKIT-108** — the Kafka partition bug that currently prevents offsets
  from being a canonical order
- **TEC-NATKIT-85** — the failure shape clause 5 prevents
