# Live Smoke Runbook

Use this when the local natKit broker stack is available and you want a real
Kafka-backed natVR sanity pass instead of the offline synthetic smoke harness.

This repo's current single-broker local stack cannot create `__consumer_offsets`
correctly, so natVR must use direct partition assignment for local smoke runs.

## Prereqs

- `podman compose` or `docker compose` available on the host
- root repo services up from `/home/zach/code/natKit`
- `natVR/.venv` created and `pip install -e .[dev]` already run

Bring up the shared stack:

```sh
cd /home/zach/code/natKit
podman compose up -d natkit-v0-kafka mosquitto natkit-v0-bridge
```

Verify Kafka is reachable:

```sh
timeout 2 bash -lc '</dev/tcp/127.0.0.1/29092' && echo open
```

## 1. Build synthetic artifacts

```sh
cd /home/zach/code/natKit/natVR
. .venv/bin/activate
natvr-emg-smoke --output-dir captures/live-smoke-seed
```

This gives you:

- `captures/live-smoke-seed/lda-model.json`
- `captures/live-smoke-seed/linear-svm-model.joblib`
- `captures/live-smoke-seed/random-forest-model.joblib`
- `captures/live-smoke-seed/sim-a__sim01.calibration.json`
- `captures/live-smoke-seed/sim-a__sim01.parquet`
- `captures/live-smoke-seed/smoke-summary.json`

Read the selected deployment artifact from the smoke summary:

```sh
MODEL_PATH="$(python - <<'PY'
import json
from pathlib import Path
summary = json.loads(Path("captures/live-smoke-seed/smoke-summary.json").read_text())
print(summary["selected_model_path"])
PY
)"
echo "$MODEL_PATH"
```

## 2. Start the live classifier

Terminal A:

```sh
cd /home/zach/code/natKit/natVR
. .venv/bin/activate
natvr-emg-classifier \
  --broker 127.0.0.1:29092 \
  --device-id sim01 \
  --session-id smoke-live \
  --direct-assign \
  --model-path "$MODEL_PATH" \
  --calibration-path captures/live-smoke-seed/sim-a__sim01.calibration.json \
  --vote-windows 1 \
  --min-hold-windows 1 \
  --confidence-threshold 0.0
```

This should publish:

- `Data-7872063431363821131-Json-HandStateV1`
- `Status-8780843145459086539-Json-DeviceStatusV1`

## 3. Start the WebSocket bridge

Terminal B:

```sh
cd /home/zach/code/natKit/natVR
. .venv/bin/activate
NATVR_HAND_STATE_TOPIC=Data-7872063431363821131-Json-HandStateV1 \
NATVR_KAFKA_DIRECT_ASSIGN=1 \
natvr-hand-state-bridge
```

That exposes `ws://127.0.0.1:8765`.

## 4. Replay a session into Kafka

Terminal C:

```sh
cd /home/zach/code/natKit/natVR
. .venv/bin/activate
natvr-emg-replay \
  captures/live-smoke-seed/sim-a__sim01.parquet \
  --broker 127.0.0.1:29092 \
  --topic Data-8780843145459086539-Json-ExgPillEmgDataSchemaV1
```

## 5. Observe output

You want three things:

1. `natvr-emg-classifier` keeps running and emits no Kafka errors.
2. The bridge accepts a WebSocket client on `ws://127.0.0.1:8765`.
3. The replay evaluator still matches the offline report:

```sh
natvr-emg-replay-eval \
  captures/live-smoke-seed/sim-a__sim01.parquet \
  --session-id smoke-live-check \
  --model-path "$MODEL_PATH" \
  --calibration-path captures/live-smoke-seed/sim-a__sim01.calibration.json \
  --vote-windows 1 \
  --min-hold-windows 1 \
  --confidence-threshold 0.0
```

## Expected current state

As of `2026-06-25`:

- transport/timestamp alignment is expected to be correct
- the old default LDA artifact is weaker than the stronger SVM/RF candidates
- the smoke summary now records the selected deployment artifact explicitly
- the broker-backed smoke path is verified locally with `podman`, direct Kafka
  partition assignment, live `hand.state` Kafka messages, live `device.status`
  Kafka messages, and WebSocket bridge output

So this runbook is mainly for verifying broker wiring and status publication,
not for claiming final classifier quality.
