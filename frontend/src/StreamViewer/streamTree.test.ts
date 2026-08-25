import { describe, expect, it } from "vitest";
import { buildStreamTree, flattenStreamTree } from "./streamTree";
import type { StreamInfo, TransformSummary } from "./types";

function streams(...ids: string[]): Record<string, StreamInfo> {
  return Object.fromEntries(ids.map((id) => [id, { topics: [] }]));
}

/** A stream carrying one Data topic, i.e. one that can actually deliver samples. */
function dataStream(id: string): Record<string, StreamInfo> {
  return {
    [id]: {
      topics: [
        {
          schema_name: "NatImuBulkDataSchema",
          type: "Data",
          serialization_type: "Binary",
        },
      ],
    },
  };
}

function transform(source: string, output: string): TransformSummary {
  // Only the two lineage fields matter here; the rest is the worker bookkeeping
  // the panel shows, and pinning it in every fixture would make these tests
  // break for reasons that have nothing to do with the tree.
  return {
    source_stream_id: source,
    output_stream_id: output,
    output_identifier: output,
    transform_kind: "rms" as TransformSummary["transform_kind"],
    topic: `topic-${output}`,
    worker_id: "worker-a",
    slot_index: 0,
    thread_slot_id: "slot-0",
    status: "running",
  } as TransformSummary;
}

describe("buildStreamTree", () => {
  it("puts underived streams at the top level", () => {
    const tree = buildStreamTree(streams("dev-b", "dev-a"), []);
    expect(tree.roots.map((node) => node.streamId)).toEqual(["dev-a", "dev-b"]);
    expect(tree.roots.every((node) => node.children.length === 0)).toBe(true);
  });

  it("degrades to a flat list when the transform list has not arrived", () => {
    // list_transforms is a separate round trip from stream_list. Before it
    // lands there are no edges, and the panel must look like it always did
    // rather than like an empty tree.
    const tree = buildStreamTree(streams("a", "b", "c"), []);
    expect(flattenStreamTree(tree.roots)).toEqual(["a", "b", "c"]);
    expect(tree.roots).toHaveLength(3);
  });

  it("nests a derived stream under its source", () => {
    const tree = buildStreamTree(
      streams("device", "device-rms"),
      [transform("device", "device-rms")],
    );
    expect(tree.roots.map((node) => node.streamId)).toEqual(["device"]);
    expect(tree.roots[0].children.map((node) => node.streamId)).toEqual([
      "device-rms",
    ]);
    expect(tree.roots[0].children[0].depth).toBe(1);
  });

  it("nests recursively, not just two levels", () => {
    const tree = buildStreamTree(
      streams("device", "rms", "rms-smoothed"),
      [transform("device", "rms"), transform("rms", "rms-smoothed")],
    );
    expect(tree.roots).toHaveLength(1);
    const rms = tree.roots[0].children[0];
    expect(rms.streamId).toBe("rms");
    expect(rms.children.map((node) => node.streamId)).toEqual(["rms-smoothed"]);
    expect(rms.children[0].depth).toBe(2);
  });

  it("keeps several children under one source, sorted", () => {
    const tree = buildStreamTree(
      streams("device", "z-out", "a-out"),
      [transform("device", "z-out"), transform("device", "a-out")],
    );
    expect(tree.roots[0].children.map((node) => node.streamId)).toEqual([
      "a-out",
      "z-out",
    ]);
  });

  // ⚠️ The invariant this module exists for. A tree that loses a stream fails
  // in the way that is hardest to notice, so every case below asserts on the
  // full flattened set rather than on the specific shape.
  it("promotes an orphan to the top level rather than dropping it", () => {
    // The source stopped, or was never in the list. Its output must still show.
    const tree = buildStreamTree(
      streams("device", "ghost-rms"),
      [transform("stream-that-is-gone", "ghost-rms")],
    );
    expect(flattenStreamTree(tree.roots).sort()).toEqual([
      "device",
      "ghost-rms",
    ]);
    expect(tree.orphanIds).toEqual(["ghost-rms"]);
    const orphan = tree.roots.find((node) => node.streamId === "ghost-rms");
    expect(orphan?.orphaned).toBe(true);
    expect(orphan?.depth).toBe(0);
  });

  it("does not mark a genuine data stream as orphaned", () => {
    const tree = buildStreamTree(streams("device"), []);
    expect(tree.roots[0].orphaned).toBe(false);
    expect(tree.orphanIds).toEqual([]);
  });

  it("survives a two-node cycle without hanging, and still shows both", () => {
    const tree = buildStreamTree(
      streams("a", "b"),
      [transform("a", "b"), transform("b", "a")],
    );
    expect(flattenStreamTree(tree.roots).sort()).toEqual(["a", "b"]);
    expect(tree.cycleIds.length).toBeGreaterThan(0);
  });

  it("survives a self-referencing transform", () => {
    const tree = buildStreamTree(streams("a"), [transform("a", "a")]);
    expect(flattenStreamTree(tree.roots)).toEqual(["a"]);
  });

  it("survives a three-node cycle with no entry point", () => {
    // Every member is another member's output, so nothing qualifies as a root
    // by the normal rule. Without the backstop the whole group would vanish.
    const tree = buildStreamTree(
      streams("a", "b", "c"),
      [transform("a", "b"), transform("b", "c"), transform("c", "a")],
    );
    expect(flattenStreamTree(tree.roots).sort()).toEqual(["a", "b", "c"]);
  });

  it("ignores a transform whose output is not a known stream", () => {
    // The transform is running but its output has not appeared in stream_list
    // yet. It must not invent a row for a stream nobody can subscribe to.
    const tree = buildStreamTree(
      streams("device"),
      [transform("device", "not-listed-yet")],
    );
    expect(flattenStreamTree(tree.roots)).toEqual(["device"]);
  });

  it("shows every stream exactly once, across a mixed rig", () => {
    const tree = buildStreamTree(
      streams("dev-1", "dev-2", "dev-1-rms", "dev-1-rms-sm", "orphan", "lonely"),
      [
        transform("dev-1", "dev-1-rms"),
        transform("dev-1-rms", "dev-1-rms-sm"),
        transform("vanished", "orphan"),
      ],
    );
    const flat = flattenStreamTree(tree.roots);
    expect(flat.sort()).toEqual([
      "dev-1",
      "dev-1-rms",
      "dev-1-rms-sm",
      "dev-2",
      "lonely",
      "orphan",
    ]);
    expect(new Set(flat).size).toBe(flat.length); // exactly once, no duplicates
  });

  // TEC-NATKIT-90: the hub publishes only LOGGING_LOG topics, which
  // sendStreamList deliberately omits, so it arrives with an empty topic array.
  it("marks a stream with no Data topic as not deliverable", () => {
    const tree = buildStreamTree(
      { ...dataStream("leaf"), ...streams("hub") },
      [],
    );
    const byId = Object.fromEntries(tree.roots.map((n) => [n.streamId, n]));
    expect(byId["leaf"].hasDataTopic).toBe(true);
    expect(byId["hub"].hasDataTopic).toBe(false);
  });

  it("treats a meta-only stream as having no Data topic", () => {
    const tree = buildStreamTree(
      {
        stale: {
          topics: [
            {
              schema_name: "MetaRecord",
              type: "Meta",
              serialization_type: "Json",
            },
          ],
        },
      },
      [],
    );
    expect(tree.roots[0].hasDataTopic).toBe(false);
  });

  it("still shows an undeliverable stream rather than hiding it", () => {
    // Hiding these would lose the hub, which an operator legitimately wants
    // to see -- the same instinct the orphan handling exists to resist.
    const tree = buildStreamTree(streams("hub"), []);
    expect(flattenStreamTree(tree.roots)).toEqual(["hub"]);
  });

  it("handles a stream id that would collide with Object prototype keys", () => {
    const tree = buildStreamTree(streams("__proto__", "constructor"), []);
    expect(flattenStreamTree(tree.roots).sort()).toEqual([
      "__proto__",
      "constructor",
    ]);
  });
});
