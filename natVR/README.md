# natVR

`natVR` holds the EMG-to-VR project code that is specific to the Quest hand
presence work and should not live in shared natKit components.

Current scope:

- Phase 0 architecture and schema documentation
- topic naming helpers for the EMG/VR pipeline
- typed Python models for the EMG and hand-state payloads
- cue-marker side-stream support for training/session labeling
- a Kafka-to-WebSocket bridge for Quest/Unity clients
- EMG Kafka consumer, Parquet recorder, and replay tooling
- cue-based labeled capture tooling for dataset sessions
- pilot-session RMS summary and scatter-plot analysis tooling
- Phase 3 preprocessing and Hudgins feature extraction tooling
- calibration/normalization and baseline classifier evaluation tooling
- session-split LDA/SVM/RF comparison tooling
- trainable LDA model artifacts and live classifier-service scaffolding
- guided per-session calibration capture and artifact generation

Layout:

- `docs/`: ADRs and design notes
- `schemas/`: JSON schema references for pipeline payloads
- `src/natvr/`: Python package and bridge service
- `captures/`: optional local output folder for session recordings
- `tests/`: focused unit coverage for models and topic naming

Quick start:

```sh
cd natVR
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
natvr-hand-state-bridge
natvr-emg-record --help
natvr-emg-replay --help
natvr-emg-stitch-markers --help
natvr-emg-capture --help
natvr-emg-analyze --help
natvr-emg-dataset-manifest --help
natvr-emg-featurize --help
natvr-emg-calibrate --help
natvr-emg-guided-calibration --help
natvr-emg-baseline --help
natvr-emg-compare-models --help
natvr-emg-select-model --help
natvr-emg-train-validate-kafka --help
natvr-emg-channel-ablation --help
natvr-emg-train --help
natvr-emg-classifier --help
natvr-emg-classify-replay --help
natvr-emg-replay-eval --help
natvr-emg-publish-session --help
natvr-emg-reconstruct --help
natvr-emg-simulate --help
natvr-emg-smoke --help
```

Optional native stitcher:

```sh
cmake -S ../libnatkit/lib/libnatkit-core -B ../libnatkit/lib/libnatkit-core/build -DSTANDARD_BUILD=ON
cmake --build ../libnatkit/lib/libnatkit-core/build
```

Bridge environment variables:

- `NATVR_KAFKA_BROKER` default `127.0.0.1:29092`
- `NATVR_HAND_STATE_TOPIC` default `natvr.topics.hand_state("demo")`
- `NATVR_KAFKA_DIRECT_ASSIGN` default unset; set to `1` for single-broker local smoke runs that cannot use consumer groups
- `NATVR_KAFKA_PARTITION` default `0`
- `NATVR_WS_HOST` default `0.0.0.0`
- `NATVR_WS_PORT` default `8765`
- `NATVR_KAFKA_GROUP_ID` default `natvr-hand-state-bridge`

Recorder outputs:

- `<session-id>__<device-id>.parquet`: raw EMG frames with timestamps, gap
  counts, and channel arrays
- `<session-id>__<device-id>.markers.jsonl`: generic marker side stream for a reconstructed or replayed session
- `<session-id>__<device-id>.annotated.parquet`: optional raw EMG frames
  restitched with cue-marker stream annotations
- `<session-id>__<device-id>.meta.json`: session metadata sidecar
- `<session-id>__<device-id>.cues.json`: cue schedule and actual cue timestamps
- `<session-id>__<device-id>.summary.json`: optional analysis summary
- `<session-id>__<device-id>.scatter.svg`: optional RMS separability plot
- `<session-id>__<device-id>.features.jsonl`: optional windowed DSP/Hudgins features
- `dataset-manifest.json`: optional deterministic dataset manifest with
  session-level train/val/test split assignments
- `<session-id>__<device-id>.calibration.json`: optional normalization profile
- `<session-id>__<device-id>.guided-calibration.json`: optional guided-calibration artifact manifest
- `<session-id>__<device-id>.session-lda-model.json`: optional session-adapted LDA model artifact
- `baseline-report.json`: optional session-split baseline metrics
- `model-compare-report.json`: optional LDA vs linear-SVM vs random-forest comparison report
- `model-selection-report.json`: optional replay-scored deployment-artifact selection report
- `channel-ablation.json`: optional session-split accuracy report by channel count
- `lda-model.json`: optional trained LDA model artifact
- `<session-id>__<device-id>.hand-state.jsonl`: optional offline replay classification output
- `<session-id>__<device-id>.replay-eval.json`: optional replay-vs-cue evaluation report
- `smoke-summary.json`: optional deterministic synthetic pipeline regression summary

Guided calibration flow:

- `natvr-emg-guided-calibration` runs a fixed session-start routine: lead-in,
  rest baseline, max squeeze, then one prompted rep per gesture.
- It records the raw Parquet session and cue file, then immediately emits the
  matching `.features.jsonl`, `.calibration.json`, and manifest outputs.
- If you pass one or more `--train-feature-path` values, it also re-fits a
  session-adapted LDA model artifact by combining the fresh calibration session
  with prior feature sets.

Smoke harness:

- `natvr-emg-smoke` runs the synthetic session path end to end: simulate,
  featurize, calibrate, train, baseline, replay-eval, guided session-adaptation,
  and channel ablation.
- It writes a single `smoke-summary.json` so DSP/model regressions show up as a
  changed global-vs-guided replay accuracy delta instead of ad hoc notebook work.

Model artifacts:

- `natvr-emg-train` defaults to the existing JSON LDA artifact.
- `natvr-emg-train --family linear_svm` and `--family random_forest` write
  sklearn `joblib` artifacts that the same classifier and replay-eval runtime
  can load directly.
- `natvr-emg-select-model` trains the candidate families, replay-scores them on
  one or more recorded sessions, and writes `model-selection-report.json` with
  the selected deployment artifact path.
- `natvr-emg-train-validate-kafka` discovers recorded runs still available on
  Kafka, lets you pick training and validation sets, reconstructs and featurizes
  them, trains one or more model families, and writes a combined
  `kafka-train-validate-report.json`.
- The frontend-owned ML control-plane host now lives under
  `../libnatkit/scripts/natkit_ml_control_plane.py` so the WebSocket transport
  and orchestration boundary stay in core infrastructure instead of this
  client-specific package.

Real-session selection flow:

```sh
natvr-emg-featurize captures/session-a__emg01.parquet
natvr-emg-featurize captures/session-b__emg01.parquet
natvr-emg-featurize captures/session-c__emg01.parquet

natvr-emg-calibrate captures/session-a__emg01.features.jsonl
natvr-emg-calibrate captures/session-b__emg01.features.jsonl
natvr-emg-calibrate captures/session-c__emg01.features.jsonl

natvr-emg-select-model \
  captures/session-a__emg01.features.jsonl \
  captures/session-b__emg01.features.jsonl \
  --eval-parquet captures/session-c__emg01.parquet
```

That report is the input for choosing the live classifier `--model-path`.

Live broker smoke:

- [docs/live-smoke.md](docs/live-smoke.md) captures the exact broker-backed
  classifier/bridge/replay sequence to run once the root `docker compose` stack
  is available on the host.
- On the current single-broker local stack, use `--direct-assign` for EMG
  consumers and `NATVR_KAFKA_DIRECT_ASSIGN=1` for the hand-state bridge to avoid
  the broken `__consumer_offsets` path.

Marker stream:

- `natvr.topics.meta_session(session_id)` now resolves to a generic
  `MetaRecord` topic. Concrete metadata records are selected inside the payload,
  starting with `SessionMetadataRecord`.
- `natvr-emg-publish-session` can publish a `SessionMetadataRecord` and optional
  session lifecycle markers to Kafka, so a capture workflow can register
  metadata before cue markers and EMG frames arrive.
- `natvr.topics.marker_stream(session_id)` returns a dedicated companion Kafka
  topic for marker events. `cue_marker(session_id)` is kept as an alias for the
  cue-labeling case.
- `natvr-emg-reconstruct --session-id ...` rebuilds one historical capture from
  Kafka into the normal `<session>__<device>.parquet`,
  `<session>__<device>.markers.jsonl`, and `.meta.json` outputs by using the
  session marker window and the raw device EMG topic. On an interactive TTY you
  can omit `--session-id` and/or `--device-id` to browse discovered recorded
  runs and device IDs before reconstruction starts. If one `session_id` has
  multiple start/end capture windows, reconstruction now prompts for the
  specific run and writes `__run-NN` suffixed output files to avoid overwriting
  earlier reconstructions from the same session topic.
- The marker stream uses generic `MarkerEventV1` payloads so cue markers, task
  markers, operator notes, and later training annotations can share one stream.
- `natvr-emg-replay --cue-path captures/demo__emg01.cues.json --session-id demo`
  now publishes both raw `ExgPillEmgDataSchemaV1` frames and marker-stream cue start/end
  events.
- `natvr-emg-classifier`, `natvr-emg-record`, `natvr-emg-capture`, and
  `natvr-emg-guided-calibration` all accept `--input-topic` so the same consumer
  code can read live device topics or uploaded/replayed training streams.
- `natvr-emg-classifier` now subscribes to the session marker stream alongside
  raw EMG by default, with `--marker-topic` to override the marker source and
  `--disable-marker-stream` to fall back to EMG-only consumption.
- `natvr-emg-stitch-markers raw.parquet --marker-path markers.jsonl` merges a
  cue-marker side stream back onto raw EMG rows using `device_ts_us` by default.
- `natvr-emg-featurize`, `natvr-emg-analyze`, and `natvr-emg-replay-eval` also
  accept `--marker-path` directly, so raw EMG captures can be paired with a
  side marker stream at read time instead of requiring a pre-stitched parquet.
- `natvr-emg-classify-replay` now also uses the same merged timestamp timeline
  when you provide `--marker-path`, so offline replay consumes EMG and marker
  events through the same ordering contract as the rest of the pipeline.
- When replay classification runs with marker events present, each emitted
  output row can include the current active marker context, including cue
  fields and a generic `active_markers` object keyed by marker type.
- `natvr-emg-classifier`, `natvr-emg-classify-replay`, and `natvr-emg-replay-eval`
  now share engine-level marker context handling, and can gate state emission
  to active cue-hold windows with `--emit-only-during-cue-hold`.
- For cue-only streams it preserves the existing `cue_*` annotation fields. For
  mixed marker streams it can stitch one marker type with `--marker-type` or
  stitch all marker types into namespaced fields such as `trial_*` and `cue_*`.
- Timestamp alignment is the join contract for stream stitching. With NTP-synced
  producers, stream payload timestamps should be treated as canonical and Kafka
  receive time should only remain as diagnostics.
- If `libnatkit-core` is built, `natvr.markers` uses its native interval
  stitcher through `ctypes`; otherwise it falls back to the existing pure
  Python alignment path.
- `natvr.stream_alignment` now exposes the same timestamp contract for generic
  stream work:
  latest-point joins for discrete side streams, and stable timestamp-order
  interleave for mixing multiple decoded streams into one timeline.
