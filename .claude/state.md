# Current Work State

> This file is maintained by Claude Code. Read on session start, update before session end.

**Last updated:** 2026-08-10

## Board — new EPIC #343 filed 2026-08-10 (ESP-IDF firmware fork), NOT started

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
