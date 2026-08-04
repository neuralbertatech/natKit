# natKit — ClojureScript frontend (Visual Programming)

A standalone frontend whose entire scope is the **Visual Programming** page:
author, validate, run and observe stream graphs; record experiments; train and
classify. It speaks the *existing* `/ws/stream_viewer` protocol and
`/api/auth/*` — **zero backend change** — and runs alongside the Svelte app in
`../frontend` until it earns the right to replace its VP page.

Plan: [`../plans/clojurescript-vp-frontend-plan.html`](../plans/clojurescript-vp-frontend-plan.html)

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Toolchain, socket, live connection | **done** |
| 1 | Protocol codec + schemas + pure logic ports + tests | **partial** — codec, schemas, graph model, composites, descriptor probing, viewer registry |
| 2 | Canvas + design system (read-only) | not started — `ui/harness.cljs` is a placeholder |
| S0 | Script-node frame contract + runtime selection spike | **done** — see [`../plans/script-nodes-plan.html`](../plans/script-nodes-plan.html) |
| 3–8 | Editing, inspector, live data, experiments, composites, cutover | not started |

Still to port for Phase 1: `experiment/protocol` (cue engine), `experiment/time`
(time context), `graph/starters`, `graph/library`, `graph/validate`.

## Commands

```bash
npm install                  # once

npm run watch                # dev server on :8280, nREPL on :8777
npm run release              # optimized build into resources/public/js/compiled

npm test                     # unit + golden-payload suite (node, no browser)
npm run test:watch

npm run integration          # boots the real socket/events/app-db against a
                             # running backend and asserts on live data
npm run smoke                # raw protocol check + golden-payload capture
```

`npm run smoke -- --capture` refreshes `test/resources/*.json` from whatever
backend you point it at. Those captured payloads are what the golden tests
validate against; the suite skips them gracefully if absent.

## Configuration

The backend WebSocket URL is configuration, never a hardcode
(`natkit.config/ws-url`), resolved in this order:

1. `window.NATKIT_WS_URL` — set in `resources/public/index.html` for dev, where
   the shadow dev server is on `:8280` and the backend on `:7409`.
2. `NATKIT_WS_URL` in the environment — used by the node integration check.
3. Derived from the page origin — what works behind nginx in production.

Cookies are host-scoped rather than port-scoped, so a `natkit_session` cookie set
on `localhost` is sent to `ws://localhost:7409` from a page served on `:8280`.
**This has not yet been confirmed on this machine**: the dev stack runs with
`NATKIT_AUTH_DISABLED=true`, so there is no cookie to test with. Confirm it
against an auth-enabled backend before relying on it; the documented fallbacks
are an nginx dev service or keeping `NATKIT_AUTH_DISABLED=1` for local work.

## Two rules that are not stylistic

Both live in `natkit.protocol.wire`, both were found against real payloads, and
both have regression tests.

**1. Wire keys keep their snake_case spelling, verbatim.** No kebab-case
conversion anywhere. `editor_metadata` round-trips through the backend opaquely
(it carries the unflattened composite editor tree, which is how a composite graph
reloads from the backend alone), and a transform's `config` keys come from the
runtime node catalog, so they are unknown at compile time.

**2. Only plain field names become keywords.** A key becomes a keyword only when
it matches `^[A-Za-z_][A-Za-z0-9_]*$`; every other key stays a string.
`(js->clj x :keywordize-keys true)` turns a key containing a slash into a
*namespaced* keyword, and writing it back emits only the name — so
`"source/13793649670644-1785250699870"` silently became
`"13793649670644-1785250699870"`. natKit node ids routinely contain a slash and
`node_statuses` / `node_diagnostics` / `edge_diagnostics` are all keyed by node
id; three of five `node_statuses` keys in a real captured payload hit this.

The rule also lands on the right semantics: field names keywordize
(`:graph_id`), identifier keys stay strings, and every id-keyed lookup table is
accessed with the raw id.

## Layout

Everything above `ui/` is renderer-agnostic and runs under `npm test` with no
browser. That is deliberate: the renderer is the least important decision here
and the easiest to change.

```
src/main/natkit/
  core.cljs          mount + init
  config.cljs        build-time config (ws url, debug?)
  db.cljs            app-db shape + pure derivations
  events.cljs        the re-frame event surface (thin)
  subs.cljs          subscriptions
  theme.cljs         theme-as-data + garden stylesheet
  integration.cljs   live check against a running backend
  protocol/
    wire.cljs        the codec + the two rules above
    schema.cljs      malli schemas for messages / actions / graphs
    actions.cljs     outbound action builders (pure)
    socket.cljs      WebSocket transport as re-frame effects
  graph/
    model.cljs       geometry, ids, defaults, provenance ports
    composite.cljs   flatten / extract / instantiate / param nodes
  stream/
    descriptor.cljs      descriptor probing (capability, not sensor name)
    viewer_registry.cljs which renderer shows a stream
  script/
    contract.cljs        the frame contract (SHIPPING)
    sci.cljs             rev-1 browser evaluator — superseded, see below
  ui/
    harness.cljs     Phase-0 placeholder; Phase 2 replaces it
```

## Script nodes

`script/contract.cljs` holds the frame contract for user-authored script nodes
(plan: [`../plans/script-nodes-plan.html`](../plans/script-nodes-plan.html)). A
script is a pure function over one canonical channel frame, and the contract is
fixed so a script node's output descriptor is known *without running it* — every
compatibility check, viewer choice and "recommended next" list depends on that.
A script returning the wrong shape is a **node error**, never a frame that reaches
downstream consumers.

**`sci.cljs` is superseded.** It was the rev-1 in-browser ClojureScript runner.
Rev 2 of the plan collapsed to a single execution venue — an embedded QuickJS
inside the C++ transform worker — because SCI cannot be interrupted or
memory-capped (measured: `(loop [] (recur))` wedges the thread, `(vec (range))`
OOMs, and `:realize-max` contains neither). That measurement is what selected
QuickJS, which does have all three controls. `sci.cljs` is kept for now as a
possible scratch evaluator; it is **not** a shipping runner, and the frame verbs
will be reimplemented as a JS `nk` library shared with the embedded engine.

The runtime comparison lives in [`../spikes/script-runtime/`](../spikes/script-runtime/)
— Lua vs QuickJS on sandbox, interrupt, memory cap and throughput against real
frame sizes.

## Stack

Mirrors [rvbbit](https://github.com/ryrobes/rvbbit), which is the design and
architecture reference: **shadow-cljs** (deps in `deps.edn` via `:deps true`),
**reagent + re-frame**, **re-com** for layout, **garden** for theme-as-data,
**malli** for protocol schemas, plus `re-pollsive` (status polling),
`day8.re-frame/undo` (graph undo/redo), `re-pressed` (keybindings).

One deviation from the plan: **`websocket-fx` is not used.** It imposes its own
envelope on every frame (`{:id … :proto :request|:subscription :data …}`) and
routes inbound frames by matching `:id` against an outstanding request or open
subscription. natKit's protocol is flat and mostly push-driven — most inbound
frames are unsolicited broadcasts that correlate to no request id — so adopting
it would have meant changing the backend protocol. `protocol/socket.cljs` is the
~100 lines that actually apply. The rest of the stack is unaffected.
