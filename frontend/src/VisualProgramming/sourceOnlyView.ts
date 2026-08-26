// Which nodes can be viewed live WITHOUT starting the board (TEC-NATKIT-98 / Slice A).
//
// ⚠️ THE CEREMONY THIS REMOVES. A viewer resolved what to subscribe to from
// `nodeRuntimeStatus(node.id)?.output_stream_id`, which the backend only reports
// once the graph is RUNNING. So looking at a raw sensor meant pressing Run, which
// is how "which stream is which node?" became a board-start away.
//
// It was never needed for a plain source. Device data reaches Kafka via the bridge
// regardless of run state, the WebSocket has a `subscribe` action keyed on stream
// ids that is independent of the graph runtime (it is how the standalone Stream
// Viewer page works), and a source node already carries its own `stream_id` in
// config. Everything required to render was present before Run was pressed.
//
// ⚠️ WHAT THIS DELIBERATELY DOES NOT DO. Run/Stop exists because *transform* and
// *combine* nodes need WORKERS: one thread plus two Kafka topics each, with no idle
// teardown anywhere. So a chain with any processing in it still has to be started,
// and making those live-on-view is a separate, much larger change (reference-counted
// liveness with a grace period, recording pinning, immutable-board guards and topic
// reaping). Scoped out on purpose — see the Slice B discussion.
//
// The rule, therefore: a viewer can go live without the board only if every path
// from it upstream reaches a bound `stream_source` and passes through nothing that
// needs a worker.

/** The minimum shape this needs from a graph node. */
export interface ViewNode {
    id: string;
    kind: string;
    /** Present on stream_source nodes; optional because "unbound" is a real state. */
    stream_id?: string;
}

/** The minimum shape this needs from a graph edge. */
export interface ViewEdge {
    source_node_id: string;
    target_node_id: string;
    /** Provenance edges are lineage, not data flow, and are excluded. */
    edge_kind?: "data" | "provenance";
}

/**
 * Node kinds that pass data through without a worker of their own.
 *
 * ⚠️ Only `viewer` qualifies. It is tempting to add `sink` or pass-through-looking
 * kinds here; anything that computes needs a worker and belongs to Slice B.
 */
const WORKERLESS_KINDS = new Set(["viewer"]);

export type SourceViewReason =
    /** Every upstream path ends at a bound source, through no worker. */
    | "source_only"
    /** A transform/combine is in the path: needs a started graph (Slice B). */
    | "needs_worker"
    /** Reached a source with no stream chosen yet. */
    | "unbound_source"
    /** Nothing upstream at all. */
    | "no_source";

export interface SourceView {
    reason: SourceViewReason;
    /**
     * The stream id to subscribe to, when `reason` is "source_only" AND exactly one
     * distinct source feeds this node. ⚠️ null for a fan-in of several sources even
     * though those are viewable in principle — one viewer, one subscription is what
     * the overlay renders, and silently picking one of several would be worse than
     * declining.
     */
    streamId: string | null;
    /** Every distinct bound source stream id reachable upstream, in walk order. */
    streamIds: string[];
}

/**
 * Resolve whether `nodeId` can be viewed without starting the graph.
 *
 * ⚠️ Cycle-safe by construction: the graph editor does not prevent a cycle being
 * drawn transiently while wiring, and an unguarded walk here would hang the UI.
 */
export function resolveSourceView(
    nodeId: string,
    nodes: readonly ViewNode[],
    edges: readonly ViewEdge[],
): SourceView {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const start = byId.get(nodeId);
    if (!start) return { reason: "no_source", streamId: null, streamIds: [] };

    // A source selected directly is its own answer — that is the common case for
    // "which stream is this?", and it needs no walk.
    if (start.kind === "stream_source") {
        const id = start.stream_id;
        return id
            ? { reason: "source_only", streamId: id, streamIds: [id] }
            : { reason: "unbound_source", streamId: null, streamIds: [] };
    }

    if (!WORKERLESS_KINDS.has(start.kind)) {
        return { reason: "needs_worker", streamId: null, streamIds: [] };
    }

    const incoming = new Map<string, ViewEdge[]>();
    for (const edge of edges) {
        if (edge.edge_kind === "provenance") continue;
        const list = incoming.get(edge.target_node_id);
        if (list) list.push(edge);
        else incoming.set(edge.target_node_id, [edge]);
    }

    const streamIds: string[] = [];
    const seen = new Set<string>([nodeId]);
    const queue = [nodeId];
    let sawSource = false;
    let sawUnbound = false;

    while (queue.length > 0) {
        const current = queue.shift() as string;
        for (const edge of incoming.get(current) ?? []) {
            const upstream = byId.get(edge.source_node_id);
            if (!upstream) continue;

            if (upstream.kind === "stream_source") {
                sawSource = true;
                if (upstream.stream_id) {
                    if (!streamIds.includes(upstream.stream_id)) {
                        streamIds.push(upstream.stream_id);
                    }
                } else {
                    sawUnbound = true;
                }
                continue;
            }
            // ⚠️ Any worker anywhere upstream disqualifies the whole viewer, so this
            // returns immediately rather than continuing to collect sources: a
            // partial answer here would render a chart of raw data labelled as the
            // output of a transform that never ran.
            if (!WORKERLESS_KINDS.has(upstream.kind)) {
                return { reason: "needs_worker", streamId: null, streamIds: [] };
            }
            if (!seen.has(upstream.id)) {
                seen.add(upstream.id);
                queue.push(upstream.id);
            }
        }
    }

    if (!sawSource) return { reason: "no_source", streamId: null, streamIds: [] };
    if (streamIds.length === 0 && sawUnbound) {
        return { reason: "unbound_source", streamId: null, streamIds: [] };
    }
    return {
        reason: "source_only",
        streamId: streamIds.length === 1 ? streamIds[0] : null,
        streamIds,
    };
}
