#!/usr/bin/env node
// Protocol smoke test + golden-payload capture.
//
// Connects to a live natKit backend over /ws/stream_viewer, exercises the
// read-only actions the CLJS frontend issues on connect, prints a summary, and
// (with --capture) writes the replies into test/resources/ as golden payloads for
// the codec + schema tests.
//
// This is the Phase-0 exit gate: it proves the backend contract this port is
// written against, independent of any browser.
//
//   node scripts/protocol_smoke.mjs [--url ws://localhost:7409/ws/stream_viewer]
//                                   [--cookie natkit_session=...]
//                                   [--capture]
//
// Mirrors libnatkit/scripts/natkit_stream_graph_smoke.py in spirit: talk the real
// protocol, assert on the real replies.

import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const RESOURCES = resolve(HERE, "..", "test", "resources");

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const flag = (name) => process.argv.includes(`--${name}`);

const URL = arg("url", "ws://localhost:7409/ws/stream_viewer");
const COOKIE = arg("cookie", process.env.NATKIT_SESSION_COOKIE);
const CAPTURE = flag("capture");
const TIMEOUT_MS = Number(arg("timeout", "8000"));

// Actions the CLJS app sends on connect (natkit.events/:protocol/connected).
const ACTIONS = [
  { action: "get_streams" },
  { action: "list_node_catalog", request_id: "smoke:node-catalog" },
  { action: "list_stream_graphs", request_id: "smoke:stream-graphs" },
  { action: "list_profiles", request_id: "smoke:profiles" },
];

// type -> the file it is captured to.
const CAPTURE_TARGETS = {
  stream_list: "stream_list.json",
  node_catalog: "node_catalog.json",
  stream_graph_list: "stream_graph_list.json",
  profile_list: "profile_list.json",
};

const received = new Map();

function summarize(message) {
  switch (message.type) {
    case "stream_list": {
      const ids = Object.keys(message.streams ?? {});
      const described = ids.filter((id) =>
        (message.streams[id].topics ?? []).some((t) => t.descriptor),
      );
      return `${ids.length} streams (${described.length} with a descriptor)`;
    }
    case "node_catalog": {
      const byKind = {};
      for (const entry of message.nodes ?? []) {
        byKind[entry.kind] = (byKind[entry.kind] ?? 0) + 1;
      }
      const kinds = Object.entries(byKind)
        .map(([k, n]) => `${k}=${n}`)
        .sort()
        .join(" ");
      return `${(message.nodes ?? []).length} node types · ${kinds}`;
    }
    case "stream_graph_list": {
      const graphs = message.graphs ?? [];
      const withMetadata = graphs.filter((g) => g.editor_metadata != null).length;
      const states = graphs
        .map((g) => message.statuses?.[g.graph_id]?.run_state ?? "draft")
        .join(",");
      return `${graphs.length} graphs (${withMetadata} carrying editor_metadata)${
        states ? ` · states: ${states}` : ""
      }`;
    }
    case "profile_list":
      return `${(message.profiles ?? []).length} profiles`;
    case "error":
      return `ERROR: ${message.message ?? message.error}`;
    default:
      return "";
  }
}

const socket = new WebSocket(URL, {
  headers: COOKIE ? { Cookie: COOKIE } : {},
});

let timer = setTimeout(finish, TIMEOUT_MS);

socket.addEventListener("open", () => {
  console.log(`connected: ${URL}${COOKIE ? " (with session cookie)" : ""}`);
  for (const action of ACTIONS) {
    socket.send(JSON.stringify(action));
    console.log(`  -> ${action.action}`);
  }
});

socket.addEventListener("message", (event) => {
  let message;
  try {
    message = JSON.parse(event.data);
  } catch {
    console.log("  <- (unparseable frame)");
    return;
  }
  // Live sample frames arrive unsolicited once something is streaming; count
  // them rather than dumping them.
  if (["frame", "emg_data", "imu_data", "imu_bulk_data", "muse_data",
       "muse_bulk_data", "marker"].includes(message.type)) {
    received.set(message.type, (received.get(message.type) ?? 0) + 1);
    return;
  }
  if (!received.has(message.type)) {
    const note = summarize(message);
    console.log(`  <- ${message.type}${note ? `  ${note}` : ""}`);
  }
  received.set(message.type, message);

  if (CAPTURE && CAPTURE_TARGETS[message.type]) {
    mkdirSync(RESOURCES, { recursive: true });
    const path = resolve(RESOURCES, CAPTURE_TARGETS[message.type]);
    writeFileSync(path, JSON.stringify(message, null, 2) + "\n");
    console.log(`     captured -> test/resources/${CAPTURE_TARGETS[message.type]}`);
  }

  // Once every expected reply has landed, stop early.
  const expected = Object.keys(CAPTURE_TARGETS);
  if (expected.every((t) => received.has(t))) {
    clearTimeout(timer);
    timer = setTimeout(finish, 250);
  }
});

socket.addEventListener("error", () => {
  console.error("socket error — is the backend up on the given url?");
});

socket.addEventListener("close", (event) => {
  if (event.code !== 1000 && event.code !== 1005) {
    console.error(`socket closed: code=${event.code} reason=${event.reason || "-"}`);
    if (event.code === 1008 || /auth/i.test(event.reason ?? "")) {
      console.error("  looks like an auth rejection — pass --cookie natkit_session=...");
    }
  }
});

function finish() {
  const expected = Object.keys(CAPTURE_TARGETS);
  const missing = expected.filter((t) => !received.has(t));
  console.log("");
  if (received.has("error")) {
    console.log("RESULT: backend returned an error (see above)");
  } else if (missing.length) {
    console.log(`RESULT: FAIL — no reply for: ${missing.join(", ")}`);
  } else {
    console.log("RESULT: PASS — every expected reply received");
  }
  for (const [type, value] of received) {
    if (typeof value === "number") console.log(`  live frames: ${type} x${value}`);
  }
  try { socket.close(); } catch {}
  process.exit(missing.length || received.has("error") ? 1 : 0);
}
