# Visual Programming end-to-end tests

Playwright tests that drive the real Visual Programming UI against the dev stack,
and emit a captioned screenshot set as verification evidence.

These exist because every UI verification before them was a throwaway script in
`/tmp`, written per change and thrown away with the session. Those scripts caught
real bugs that static checks could not — an SVG collapsing to its 300×150
intrinsic size, a toolbar covering the floating panels, a drag handler whose drop
target was overwritten by event bubbling, a sentence stacking into columns inside
a flex container — but none of it was repeatable, so every regression had to be
re-found by hand.

## Running them

```bash
cd frontend
npm run test:e2e                 # against http://localhost:8080
npm run test:e2e:headed          # watch it happen
npx playwright test e2e/03-rest-interleave.spec.ts
NATKIT_E2E_BASE_URL=http://host:port npm run test:e2e
```

The dev stack must be up (`podman-compose -f docker-compose.dev.yml up -d`);
global setup fails with that message rather than a wall of timeouts if it is not.
Auth is open on the dev stack, so there is no login step. The frontend container
bind-mounts `./frontend` with HMR, so source edits are served immediately — no
rebuild between an edit and a run.

`npm run check` type-checks this directory too (`tsconfig.e2e.json`).

## Evidence

Verification of this UI happens by a human looking at it, so the suite emits the
evidence rather than leaving it to be re-captured by hand. Each run writes to
`~/natkit-verification/<sha>/` (plus `-dirty` when the tree has uncommitted
changes — a set captured from a dirty tree does not describe that commit):

- `<ticket>-<nn>-<slug>.png`, numbered per ticket, so one run drops a
  ready-ordered set per ticket;
- element-scoped shots, so each one reads on its own in a ticket comment;
- fixed 1600×1050 viewport at `deviceScaleFactor: 2`, so the set is consistent
  and legible once attached;
- `MANIFEST.md` with a caption per shot **and the run's health**: native dialogs
  raised, console errors, whether the stores were restored exactly. A clean set
  from a run that leaked data would otherwise read as a pass.

Override the location with `NATKIT_EVIDENCE_DIR`. A re-run replaces only files
matching the suite's own naming; anything else in the directory is left alone.

Attach a set to its ticket with `assistant task attach <id> <path>...`
(`-if-absent` makes re-runs safe).

Where an invariant can be proven by image equality, it is:
`04-seeded-timing.spec.ts` captures the compiled timeline at seed 1, seed 2 and
seed 1 again, and asserts the first and third are **byte-identical** while the
second differs. That is a stronger claim than any DOM assertion about
reproducible randomization, and it is a screenshot the ticket can carry.

## Fixtures

`support/fixtures.ts` provides, per test:

| Fixture | What it gives you |
|---|---|
| `app` | The editor open on a **scratch board**, saved to the backend, deleted afterwards |
| `designer` | A scratch experiment bound to that board with the designer open |
| `viewer` | A `stream_viewer` WebSocket client, for setup/teardown the UI is bad at |
| `evidence` | `shot(target, ticket, slug, caption)` |
| `health` | Native-dialog and console-error guards, asserted after the test |

**Teardown is the important part.** A script that threw before its cleanup leaked
a scratch board *and* experiment into the real store — twice — so cleanup lives
in fixture teardown, which Playwright runs even when a test fails or times out.
It deletes every experiment labelled `E2E Scratch…` and every board that was not
there before, then asserts the store counts are back to their baseline. Scratch
records from an earlier crashed run are cleaned too, so a leak is self-healing.

The suite runs with `workers: 1` and no retries: it drives one shared backend and
mutates its stores, so a second worker would race another test's scratch data,
and a retry would duplicate entries in the screenshot ledger.

## Gotchas already paid for — do not rediscover

- **Deep-linking `/VisualProgramming` does not route.** tinro lands on Home;
  click the nav link (`VpApp.open`).
- **Wait for the socket, not for a timeout.** Every editor action that talks to
  the backend returns false and only sets an error string when the socket is not
  connected yet, so a Save clicked too early is a silent no-op. `VpApp.open`
  waits for `.conn-pill.connected`.
- **A new board is a local draft.** There is no auto-save for one; it is saved
  explicitly, and an experiment cannot bind to a board the backend has never
  seen.
- **`dragTo` does not drive this dnd.** It produces mouse events; the handlers
  listen for DragEvents. `Designer.dragStepOntoStep` dispatches synthetic ones
  with a real `DataTransfer` (which works in Chromium).
- **Do not reload and assume the same board is selected.** The page picks its
  own, which once made a test read a different experiment.
- **Protocol edits are debounced (400ms) and the editor drops its local pending
  copy when it sends the save**, so between send and echo the designer briefly
  re-renders the last-saved protocol. Anything keyed on a step id across that
  window — the canvas remembers which group it is zoomed into — is reset.
  `Designer.convertToSteps` waits for the round trip via
  `VpApp.waitForStoredProtocol` rather than racing it with a sleep. That flash is
  a real defect, tracked separately; when it is fixed, that settle can go.
- **A repeat group contains its children's fields and actions**, and some labels
  (`± Jitter (s)`) exist at both levels. Use `ownField`/`stepAction`, which scope
  through the card's own `.card-main`.
- **`fill()` only raises `input`.** A field that commits on `change` (the
  comma-separated class list) needs the blur a real user gives it.
- **A screenshot is not proof that an image loaded.** An upload whose URL 404s
  back still renders a tile, so the thumbnail check polls `naturalWidth > 0`.
