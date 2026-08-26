import { describe, expect, it } from "vitest";
import { resolveSourceView, type ViewEdge, type ViewNode } from "./sourceOnlyView";

const src = (id: string, stream_id?: string): ViewNode => ({ id, kind: "stream_source", stream_id });
const viewer = (id: string): ViewNode => ({ id, kind: "viewer" });
const xform = (id: string): ViewNode => ({ id, kind: "transform" });
const edge = (from: string, to: string, kind?: "data" | "provenance"): ViewEdge => ({
    source_node_id: from,
    target_node_id: to,
    edge_kind: kind,
});

describe("resolveSourceView", () => {
    // The case the whole slice exists for: click the IMU node, see its stream.
    it("resolves a source node directly, with no walk and no runtime", () => {
        const r = resolveSourceView("s1", [src("s1", "13793649553360")], []);
        expect(r.reason).toBe("source_only");
        expect(r.streamId).toBe("13793649553360");
    });

    it("calls a source with no stream chosen unbound, not viewable", () => {
        const r = resolveSourceView("s1", [src("s1")], []);
        expect(r.reason).toBe("unbound_source");
        expect(r.streamId).toBeNull();
    });

    it("resolves a viewer wired straight to a source", () => {
        const r = resolveSourceView("v1", [src("s1", "42"), viewer("v1")], [edge("s1", "v1")]);
        expect(r.reason).toBe("source_only");
        expect(r.streamId).toBe("42");
    });

    it("walks through an intermediate viewer", () => {
        const r = resolveSourceView(
            "v2",
            [src("s1", "42"), viewer("v1"), viewer("v2")],
            [edge("s1", "v1"), edge("v1", "v2")],
        );
        expect(r.streamId).toBe("42");
    });

    // ⚠️ The scope boundary. A transform needs a worker, so the board still has to
    // be started — this is exactly what Slice B would change, and until then a
    // wrong answer here would render raw data labelled as a transform's output.
    it("refuses a chain containing a transform", () => {
        const r = resolveSourceView(
            "v1",
            [src("s1", "42"), xform("t1"), viewer("v1")],
            [edge("s1", "t1"), edge("t1", "v1")],
        );
        expect(r.reason).toBe("needs_worker");
        expect(r.streamId).toBeNull();
    });

    it("refuses if a transform feeds in on ANY path, not just the first", () => {
        const r = resolveSourceView(
            "v1",
            [src("s1", "42"), src("s2", "43"), xform("t1"), viewer("v1")],
            [edge("s1", "v1"), edge("s2", "t1"), edge("t1", "v1")],
        );
        expect(r.reason).toBe("needs_worker");
    });

    // Two sources into one viewer is viewable in principle, but one viewer renders
    // one subscription — declining beats silently picking one of the two.
    it("reports every source on a fan-in but selects no single stream", () => {
        const r = resolveSourceView(
            "v1",
            [src("s1", "42"), src("s2", "43"), viewer("v1")],
            [edge("s1", "v1"), edge("s2", "v1")],
        );
        expect(r.reason).toBe("source_only");
        expect(r.streamIds).toEqual(["42", "43"]);
        expect(r.streamId).toBeNull();
    });

    it("ignores provenance edges, which are lineage rather than data flow", () => {
        const r = resolveSourceView(
            "v1",
            [src("s1", "42"), viewer("v1")],
            [edge("s1", "v1", "provenance")],
        );
        expect(r.reason).toBe("no_source");
    });

    it("says no_source for an unwired viewer", () => {
        expect(resolveSourceView("v1", [viewer("v1")], []).reason).toBe("no_source");
    });

    // ⚠️ The editor does not stop a cycle being drawn while wiring, and an
    // unguarded walk would hang the browser rather than fail.
    it("terminates on a cycle", () => {
        const r = resolveSourceView(
            "v1",
            [src("s1", "42"), viewer("v1"), viewer("v2")],
            [edge("s1", "v1"), edge("v1", "v2"), edge("v2", "v1")],
        );
        expect(r.streamId).toBe("42");
    });

    it("treats an unknown node id as nothing to view", () => {
        expect(resolveSourceView("nope", [src("s1", "42")], []).reason).toBe("no_source");
    });
});
