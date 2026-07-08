# Current Work State

> This file is maintained by Claude Code. Read on session start, update before session end.

**Last updated:** 2026-07-08
**Session duration:** ~2 sessions

## Active Task

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

### Next: Phase 4 — first-class sessions/experiments (generic SessionProtocol,
multi-sensor recording under one marker timeline, labeled-dataset handle).

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
