import type { StreamInfo, TransformSummary } from "./types";

/**
 * Arranges the Available Streams panel as a tree: device data streams at the
 * top, and every transform output nested under the stream it was derived from
 * (TEC-NATKIT-89).
 *
 * --- Where the parent/child edges come from --------------------------------
 *
 * From `TransformSummary`, which already carries `source_stream_id` and
 * `output_stream_id`, and which the page already holds for the transforms
 * panel. Deliberately NOT from the shape of a stream id: a derived stream's id
 * is opaque to this module, and inferring lineage from a name is how a tree
 * starts quietly claiming a relationship that does not exist.
 *
 * --- The rule that matters most --------------------------------------------
 *
 * ⚠️ EVERY STREAM APPEARS EXACTLY ONCE. A tree that drops a stream is strictly
 * worse than the flat list it replaces, because it fails in the way that is
 * hardest to notice: the row you are looking for is simply not there, and
 * nothing anywhere says why. Three cases would each lose a stream if handled
 * naively, and all three are real:
 *
 *   * a transform whose `source_stream_id` is not in `availableStreams` at all
 *     (the source stopped, or was never subscribed) — its output is orphaned;
 *   * a transform list that has not arrived yet — `list_transforms` is a
 *     separate round trip from `stream_list`, so for the first moments there
 *     are no edges and every stream is a root, which must look exactly like the
 *     old flat list;
 *   * a cycle, from a stale or malformed transform list — an unguarded
 *     recursive walk would not merely render badly, it would hang the page.
 *
 * So orphans are promoted to roots rather than dropped, and the walk carries a
 * visited set.
 */

export interface StreamTreeNode {
  streamId: string;
  info: StreamInfo;
  /** Streams derived from this one, recursively. Empty for a leaf. */
  children: StreamTreeNode[];
  /** 0 for a top-level data stream; 1 for its output; 2 for that one's output. */
  depth: number;
  /**
   * True when this stream IS some transform's output but we are showing it at
   * the top level anyway, because its source is not in the list. Lets the UI
   * say "derived, source unavailable" instead of implying it is a device.
   */
  orphaned: boolean;
}

export interface StreamTree {
  roots: StreamTreeNode[];
  /**
   * Streams named as a transform output whose source is missing. Same nodes as
   * appear in `roots` with `orphaned` set — surfaced separately so a caller can
   * count them without walking the tree.
   */
  orphanIds: string[];
  /**
   * Ids dropped from the walk because following them would revisit a node.
   * Non-empty means the transform list describes a cycle, which is a bug
   * somewhere upstream; the tree stays renderable and says so.
   */
  cycleIds: string[];
}

export function buildStreamTree(
  availableStreams: Record<string, StreamInfo>,
  transforms: readonly TransformSummary[],
): StreamTree {
  const streamIds = Object.keys(availableStreams);

  // output -> source. A Map rather than an object because stream ids are
  // arbitrary strings and one of them being "__proto__" should not be exciting.
  const sourceOf = new Map<string, string>();
  for (const transform of transforms) {
    // ⚠️ Self-reference is the degenerate cycle and the cheapest to reject
    // here, before it can reach the visited-set logic below.
    if (transform.output_stream_id === transform.source_stream_id) {
      continue;
    }
    sourceOf.set(transform.output_stream_id, transform.source_stream_id);
  }

  const childrenOf = new Map<string, string[]>();
  const rootIds: string[] = [];
  const orphanIds: string[] = [];

  for (const streamId of streamIds) {
    const sourceId = sourceOf.get(streamId);
    if (sourceId === undefined) {
      rootIds.push(streamId); // not derived from anything: a data stream
      continue;
    }
    if (!(sourceId in availableStreams)) {
      // Derived, but the thing it came from is not in the list. Show it rather
      // than lose it, and mark it so the UI need not pretend it is a device.
      rootIds.push(streamId);
      orphanIds.push(streamId);
      continue;
    }
    const siblings = childrenOf.get(sourceId);
    if (siblings === undefined) {
      childrenOf.set(sourceId, [streamId]);
    } else {
      siblings.push(streamId);
    }
  }

  const cycleIds: string[] = [];
  const visited = new Set<string>();

  function nodeFor(streamId: string, depth: number): StreamTreeNode {
    visited.add(streamId);
    const children: StreamTreeNode[] = [];
    for (const childId of childrenOf.get(streamId) ?? []) {
      if (visited.has(childId)) {
        // Already placed, or we are walking in a circle. Either way, following
        // it again would duplicate a subtree or never terminate.
        cycleIds.push(childId);
        continue;
      }
      children.push(nodeFor(childId, depth + 1));
    }
    children.sort((left, right) => left.streamId.localeCompare(right.streamId));
    return {
      streamId,
      info: availableStreams[streamId],
      children,
      depth,
      orphaned: depth === 0 && orphanIds.includes(streamId),
    };
  }

  const roots = rootIds
    .filter((streamId) => !visited.has(streamId))
    .map((streamId) => nodeFor(streamId, 0))
    .sort((left, right) => left.streamId.localeCompare(right.streamId));

  // ⚠️ THE BACKSTOP FOR THE INVARIANT, not decoration. Anything the walk failed
  // to reach — a cycle with no entry point, say, where every member is some
  // other member's output — is appended at the top level. Without this the
  // stream would vanish, which is the one outcome this module exists to
  // prevent, and it would do so silently.
  for (const streamId of streamIds) {
    if (!visited.has(streamId)) {
      cycleIds.push(streamId);
      roots.push(nodeFor(streamId, 0));
    }
  }

  return { roots, orphanIds, cycleIds };
}

/** Every stream id in the tree, in render order. For tests and for counting. */
export function flattenStreamTree(nodes: readonly StreamTreeNode[]): string[] {
  const out: string[] = [];
  for (const node of nodes) {
    out.push(node.streamId);
    out.push(...flattenStreamTree(node.children));
  }
  return out;
}
