import { describe, it, expect } from "vitest";
import type {
    StreamGraphEdge,
    StreamGraphNode,
} from "../StreamViewer/types";
import {
    extractCompositeFromSelection,
    flattenGraph,
    parseCompositeExportFile,
    serializeCompositeExport,
    ungroupInstance,
    type CompositeInstanceNode,
    type CompositeTemplate,
    type EditorGraphDefinition,
    type ParamNode,
} from "./composites";

function sourceNode(id: string, streamId = "stream-a"): StreamGraphNode {
    return {
        id,
        kind: "stream_source",
        label: `Source ${id}`,
        position: { x: 0, y: 0 },
        stream_id: streamId,
        output_port_ids: ["data"],
    };
}

function transformNode(id: string, outputId: string): StreamGraphNode {
    return {
        id,
        kind: "transform",
        label: `Transform ${id}`,
        position: { x: 100, y: 0 },
        transform_kind: "rectify",
        config: {},
        output_identifier: outputId,
        input_port_ids: ["input"],
        output_port_ids: ["output"],
    };
}

function viewerNode(id: string): StreamGraphNode {
    return {
        id,
        kind: "viewer",
        label: `Viewer ${id}`,
        position: { x: 200, y: 0 },
        input_port_ids: ["input"],
    };
}

function edge(
    id: string,
    source: string,
    sourcePort: string,
    target: string,
    targetPort: string,
): StreamGraphEdge {
    return {
        id,
        source_node_id: source,
        source_port: sourcePort,
        target_node_id: target,
        target_port: targetPort,
    };
}

function baseGraph(
    nodes: EditorGraphDefinition["nodes"],
    edges: StreamGraphEdge[],
): EditorGraphDefinition {
    return {
        graph_version: 1,
        graph_id: "graph-1",
        label: "Test graph",
        nodes,
        edges,
    };
}

describe("extractCompositeFromSelection", () => {
    it("derives boundary ports and replaces the selection with one instance", () => {
        // source -> transform -> viewer; group the transform only.
        const graph = baseGraph(
            [
                sourceNode("src"),
                transformNode("tx", "rectified"),
                viewerNode("view"),
            ],
            [
                edge("e1", "src", "data", "tx", "input"),
                edge("e2", "tx", "output", "view", "input"),
            ],
        );

        const result = extractCompositeFromSelection(
            graph,
            new Set(["tx"]),
            "My Filter",
        );
        expect(result).not.toBeNull();
        const { template, instance, nextGraph } = result!;

        // One input (from src) and one output (to view).
        expect(template.inputs).toHaveLength(1);
        expect(template.outputs).toHaveLength(1);
        expect(template.nodes).toHaveLength(1);

        // The graph now has source, composite instance, viewer.
        expect(nextGraph.nodes).toHaveLength(3);
        const compositeNodes = nextGraph.nodes.filter(
            (n) => n.kind === "composite",
        );
        expect(compositeNodes).toHaveLength(1);

        // External edges are rewired onto the instance boundary ports.
        const intoInstance = nextGraph.edges.find(
            (e) => e.target_node_id === instance.id,
        );
        const outOfInstance = nextGraph.edges.find(
            (e) => e.source_node_id === instance.id,
        );
        expect(intoInstance?.source_node_id).toBe("src");
        expect(intoInstance?.target_port).toBe(template.inputs[0].port_id);
        expect(outOfInstance?.target_node_id).toBe("view");
        expect(outOfInstance?.source_port).toBe(template.outputs[0].port_id);
    });
});

describe("flattenGraph", () => {
    it("inlines a composite into primitives and rewires the boundary", () => {
        const graph = baseGraph(
            [
                sourceNode("src"),
                transformNode("tx", "rectified"),
                viewerNode("view"),
            ],
            [
                edge("e1", "src", "data", "tx", "input"),
                edge("e2", "tx", "output", "view", "input"),
            ],
        );
        const extracted = extractCompositeFromSelection(
            graph,
            new Set(["tx"]),
            "My Filter",
        )!;

        const { graph: flat, diagnostics } = flattenGraph(
            extracted.nextGraph,
            () => undefined,
        );

        expect(diagnostics).toHaveLength(0);
        // No composite nodes survive flattening (only primitive kinds remain).
        expect(
            flat.nodes.every((n) =>
                ["stream_source", "transform", "viewer", "sink"].includes(
                    n.kind,
                ),
            ),
        ).toBe(true);
        // src, expanded transform, view.
        expect(flat.nodes).toHaveLength(3);

        // The chain is reconnected end-to-end through the expanded transform.
        const expandedTx = flat.nodes.find((n) => n.kind === "transform")!;
        const intoTx = flat.edges.find(
            (e) => e.target_node_id === expandedTx.id,
        );
        const outOfTx = flat.edges.find(
            (e) => e.source_node_id === expandedTx.id,
        );
        expect(intoTx?.source_node_id).toBe("src");
        expect(outOfTx?.target_node_id).toBe("view");
    });

    it("gives distinct output identifiers when the same composite is used twice", () => {
        const template: CompositeTemplate = {
            composite_version: 1,
            composite_id: "cmp-1",
            label: "Rectifier",
            nodes: [transformNode("tx", "rectified")],
            edges: [],
            inputs: [
                {
                    port_id: "in1",
                    label: "In",
                    internal_node_id: "tx",
                    internal_port: "input",
                },
            ],
            outputs: [
                {
                    port_id: "out1",
                    label: "Out",
                    internal_node_id: "tx",
                    internal_port: "output",
                },
            ],
        };
        const instanceA: CompositeInstanceNode = {
            id: "composite/a",
            kind: "composite",
            label: "Rectifier A",
            position: { x: 0, y: 0 },
            composite_id: "cmp-1",
            composite_version: 1,
            input_port_ids: ["in1"],
            output_port_ids: ["out1"],
            template,
        };
        const instanceB: CompositeInstanceNode = {
            ...instanceA,
            id: "composite/b",
            label: "Rectifier B",
            position: { x: 400, y: 0 },
        };

        const graph = baseGraph([instanceA, instanceB], []);
        const { graph: flat } = flattenGraph(graph, () => undefined);

        const transforms = flat.nodes.filter((n) => n.kind === "transform");
        expect(transforms).toHaveLength(2);
        const ids = transforms.map((n) =>
            n.kind === "transform" ? n.output_identifier : "",
        );
        expect(new Set(ids).size).toBe(2);
        // Ids are also globally unique node ids.
        expect(new Set(flat.nodes.map((n) => n.id)).size).toBe(2);
    });

    it("emits a diagnostic and drops edges when a template is missing", () => {
        const orphan: CompositeInstanceNode = {
            id: "composite/orphan",
            kind: "composite",
            label: "Orphan",
            position: { x: 0, y: 0 },
            composite_id: "missing",
            composite_version: 1,
            input_port_ids: ["in1"],
            output_port_ids: ["out1"],
            // no embedded template
        };
        const graph = baseGraph(
            [sourceNode("src"), orphan],
            [edge("e1", "src", "data", "composite/orphan", "in1")],
        );
        const { graph: flat, diagnostics } = flattenGraph(
            graph,
            () => undefined,
        );
        expect(
            diagnostics.some((d) => d.code === "composite_template_missing"),
        ).toBe(true);
        expect(flat.edges).toHaveLength(0);
    });
});

describe("ungroupInstance", () => {
    it("restores the primitives and reconnects the boundary", () => {
        const graph = baseGraph(
            [
                sourceNode("src"),
                transformNode("tx", "rectified"),
                viewerNode("view"),
            ],
            [
                edge("e1", "src", "data", "tx", "input"),
                edge("e2", "tx", "output", "view", "input"),
            ],
        );
        const extracted = extractCompositeFromSelection(
            graph,
            new Set(["tx"]),
            "My Filter",
        )!;
        const restored = ungroupInstance(
            extracted.nextGraph,
            extracted.instance.id,
        );
        expect(restored.nodes.every((n) => n.kind !== "composite")).toBe(true);
        expect(restored.nodes).toHaveLength(3);
        const tx = restored.nodes.find((n) => n.kind === "transform")!;
        expect(
            restored.edges.some(
                (e) =>
                    e.source_node_id === "src" && e.target_node_id === tx.id,
            ),
        ).toBe(true);
        expect(
            restored.edges.some(
                (e) =>
                    e.source_node_id === tx.id && e.target_node_id === "view",
            ),
        ).toBe(true);
    });
});

describe("export / import", () => {
    it("round-trips composite templates through the file format", () => {
        const template: CompositeTemplate = {
            composite_version: 1,
            composite_id: "cmp-1",
            label: "Rectifier",
            nodes: [transformNode("tx", "rectified")],
            edges: [],
            inputs: [],
            outputs: [],
        };
        const file = serializeCompositeExport([template]);
        const text = JSON.stringify(file);
        const { templates, errors } = parseCompositeExportFile(text);
        expect(errors).toHaveLength(0);
        expect(templates).toHaveLength(1);
        expect(templates[0].composite_id).toBe("cmp-1");
    });

    it("rejects a file with the wrong type", () => {
        const { templates, errors } = parseCompositeExportFile(
            JSON.stringify({ file_type: "something-else" }),
        );
        expect(templates).toHaveLength(0);
        expect(errors.length).toBeGreaterThan(0);
    });

    it("reports invalid JSON", () => {
        const { errors } = parseCompositeExportFile("{not json");
        expect(errors.length).toBeGreaterThan(0);
    });
});

describe("flattenGraph param nodes (Phase 7)", () => {
    it("drops editor-only param nodes and their binding edges", () => {
        const param: ParamNode = {
            id: "param/1",
            kind: "param",
            label: "Cutoff",
            position: { x: 0, y: 0 },
            value: 30,
            min: 0,
            max: 100,
            step: 1,
            target_node_id: "tf",
            target_field: "cutoff_hz",
            output_port_ids: ["value"],
        };
        const graph = baseGraph(
            [sourceNode("src"), transformNode("tf", "tf-out"), param],
            [
                edge("e1", "src", "data", "tf", "input"),
                edge("e2", "param/1", "value", "tf", "input"),
            ],
        );
        const { graph: flat } = flattenGraph(graph, () => undefined);
        // The param node (and its binding edge) are gone; only primitives remain.
        expect(flat.nodes.map((n) => n.id).sort()).toEqual(["src", "tf"]);
        expect(flat.edges).toHaveLength(1);
        expect(flat.edges[0].id).toBe("e1");
    });
});
