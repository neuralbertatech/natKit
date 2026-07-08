import { describe, it, expect } from "vitest";
import { flattenGraph, instantiateComposite } from "./composites";
import { EMG_PREPROCESSING_COMPOSITE } from "./defaultComposites";
import type { EditorGraphDefinition } from "./composites";

describe("EMG_PREPROCESSING_COMPOSITE", () => {
    it("has internally-consistent node ids across nodes, edges, and boundary ports", () => {
        const nodeIds = new Set(
            EMG_PREPROCESSING_COMPOSITE.nodes.map((node) => node.id),
        );
        expect(nodeIds.size).toBe(EMG_PREPROCESSING_COMPOSITE.nodes.length);

        for (const edge of EMG_PREPROCESSING_COMPOSITE.edges) {
            expect(nodeIds.has(edge.source_node_id)).toBe(true);
            expect(nodeIds.has(edge.target_node_id)).toBe(true);
        }
        for (const decl of [
            ...EMG_PREPROCESSING_COMPOSITE.inputs,
            ...EMG_PREPROCESSING_COMPOSITE.outputs,
        ]) {
            expect(nodeIds.has(decl.internal_node_id)).toBe(true);
        }
    });

    it("gives the combine node at least two inputs", () => {
        const combineNode = EMG_PREPROCESSING_COMPOSITE.nodes.find(
            (node) => node.kind === "combine",
        );
        expect(combineNode).toBeDefined();
        const inboundEdges = EMG_PREPROCESSING_COMPOSITE.edges.filter(
            (edge) => edge.target_node_id === combineNode?.id,
        );
        expect(inboundEdges.length).toBeGreaterThanOrEqual(2);
    });

    it("flattens to an all-primitive backend-safe graph with no diagnostics", () => {
        const instance = instantiateComposite(EMG_PREPROCESSING_COMPOSITE, {
            x: 0,
            y: 0,
        });
        const graph: EditorGraphDefinition = {
            graph_version: 1,
            graph_id: "test-graph",
            label: "Test graph",
            nodes: [instance],
            edges: [],
        };

        const { graph: flat, diagnostics } = flattenGraph(graph, () => undefined);

        expect(diagnostics).toHaveLength(0);
        expect(
            flat.nodes.every((node) =>
                ["stream_source", "transform", "viewer", "sink", "combine"].includes(
                    node.kind,
                ),
            ),
        ).toBe(true);
        expect(flat.nodes).toHaveLength(EMG_PREPROCESSING_COMPOSITE.nodes.length);

        // LDA Classify is intentionally not part of this composite — it's a
        // separate classification step, not EMG preprocessing. Add it as a
        // standalone transform node from the palette instead.
        const classifyNode = flat.nodes.find(
            (node) => node.kind === "transform" && node.transform_kind === "lda_classify",
        );
        expect(classifyNode).toBeUndefined();
    });
});
