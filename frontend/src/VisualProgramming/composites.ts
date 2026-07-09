// Composite ("higher-order") node support for the Visual Programming editor.
//
// A composite is a reusable, function-like group of primitive graph nodes. It is
// a FRONTEND-ONLY authoring concept: the backend only understands the four
// primitive node kinds (stream_source, transform, viewer, sink) and rejects any
// other kind. Before a graph is saved / validated / run, every composite instance
// is flattened (inlined) into namespaced primitive nodes via `flattenGraph`, so
// the backend never sees a composite.
//
// These helpers are pure (no Svelte state, no DOM) so they can be unit-tested.
import type {
    StreamGraphDefinition,
    StreamGraphDiagnostic,
    StreamGraphEdge,
    StreamGraphNode,
    StreamGraphPosition,
    StreamGraphViewport,
} from "../StreamViewer/types";
import { sanitizeIdentifier } from "./streamGraph";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// One declared external port on a composite, bound to an internal (node, port) pin.
export interface CompositePortDecl {
    port_id: string;
    label: string;
    internal_node_id: string;
    internal_port: string;
}

// The reusable "function definition". Internal nodes are primitives only (v1).
export interface CompositeTemplate {
    composite_version: 1;
    composite_id: string;
    label: string;
    description?: string;
    author?: string;
    created_at_us?: number;
    updated_at_us?: number;
    nodes: StreamGraphNode[];
    edges: StreamGraphEdge[];
    inputs: CompositePortDecl[];
    outputs: CompositePortDecl[];
    ui?: { viewport?: StreamGraphViewport };
}

// The collapsed node placed on the canvas (editor-only node kind).
export interface CompositeInstanceNode {
    id: string;
    kind: "composite";
    label: string;
    position: StreamGraphPosition;
    input_port_ids?: string[];
    output_port_ids?: string[];
    width?: number;
    height?: number;
    composite_id: string;
    composite_version: 1;
    // Embedded snapshot so a graph is self-contained even without the library entry.
    template?: CompositeTemplate;
}

// A param/input node (Phase 7, part C): an editor-only control whose value
// drives a downstream transform's config field. It is dropped by flattenGraph
// (the value is written into the target's config on change), so the backend
// never sees it — the executed graph is unchanged.
export interface ParamNode {
    id: string;
    kind: "param";
    label: string;
    position: StreamGraphPosition;
    input_port_ids?: string[];
    output_port_ids?: string[];
    width?: number;
    height?: number;
    value: number;
    min: number;
    max: number;
    step: number;
    // Binding: the downstream transform + config field this param drives.
    target_node_id?: string;
    target_field?: string;
}

export type EditorGraphNode =
    | StreamGraphNode
    | CompositeInstanceNode
    | ParamNode;

export interface EditorGraphDefinition
    extends Omit<StreamGraphDefinition, "nodes"> {
    nodes: EditorGraphNode[];
}

// Versioned export/import container for sharing composites between users.
export interface CompositeExportFile {
    file_type: "natkit.composite";
    file_version: 1;
    exported_at_us: number;
    templates: CompositeTemplate[];
}

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------

function deepClone<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T;
}

export function isCompositeInstance(
    node: EditorGraphNode,
): node is CompositeInstanceNode {
    return node.kind === "composite";
}

export function isParamNode(node: EditorGraphNode): node is ParamNode {
    return node.kind === "param";
}

let idCounter = 0;
function uniqueSuffix(): string {
    idCounter += 1;
    return `${Date.now().toString(36)}-${idCounter.toString(36)}`;
}

export function createCompositeId(): string {
    return `composite-${uniqueSuffix()}`;
}

// Deterministic, collision-free prefixing of an inner id with its instance id.
export function namespaceId(instanceId: string, innerId: string): string {
    return `${instanceId}::${innerId}`;
}

// Unique, backend-safe transform output identifier for an expanded inner node.
export function namespaceOutputIdentifier(
    instanceId: string,
    inner: string,
): string {
    return sanitizeIdentifier(`${instanceId}-${inner}`);
}

export function instancePortsFromTemplate(template: CompositeTemplate): {
    input_port_ids: string[];
    output_port_ids: string[];
} {
    return {
        input_port_ids: template.inputs.map((port) => port.port_id),
        output_port_ids: template.outputs.map((port) => port.port_id),
    };
}

// ---------------------------------------------------------------------------
// Expansion / flattening
// ---------------------------------------------------------------------------

// Expand a single instance into namespaced primitive nodes + edges.
export function expandInstance(
    instance: CompositeInstanceNode,
    template: CompositeTemplate,
): {
    nodes: StreamGraphNode[];
    edges: StreamGraphEdge[];
    idMap: Record<string, string>;
} {
    const idMap: Record<string, string> = {};
    for (const node of template.nodes) {
        idMap[node.id] = namespaceId(instance.id, node.id);
    }

    const nodes: StreamGraphNode[] = template.nodes.map((node) => {
        const cloned = deepClone(node);
        cloned.id = idMap[node.id];
        cloned.position = {
            x: instance.position.x + node.position.x,
            y: instance.position.y + node.position.y,
        };
        if (cloned.kind === "transform" || cloned.kind === "combine") {
            cloned.output_identifier = namespaceOutputIdentifier(
                instance.id,
                node.kind === "transform" || node.kind === "combine"
                    ? node.output_identifier ?? node.id
                    : node.id,
            );
            cloned.output_stream_id = undefined;
        }
        return cloned;
    });

    const edges: StreamGraphEdge[] = template.edges.map((edge) => ({
        id: namespaceId(instance.id, edge.id),
        source_node_id: idMap[edge.source_node_id] ?? edge.source_node_id,
        source_port: edge.source_port,
        target_node_id: idMap[edge.target_node_id] ?? edge.target_node_id,
        target_port: edge.target_port,
    }));

    return { nodes, edges, idMap };
}

interface BoundaryEntry {
    template: CompositeTemplate;
    idMap: Record<string, string>;
}

// Rewrite the endpoint(s) of an outer edge that reference a composite instance
// to point at the bound internal pin. Returns null if a referenced boundary port
// has no binding (the edge is dropped and a diagnostic is emitted by the caller).
function rewireEdge(
    edge: StreamGraphEdge,
    boundary: Record<string, BoundaryEntry>,
    diagnostics: StreamGraphDiagnostic[],
): StreamGraphEdge | null {
    const next: StreamGraphEdge = { ...edge };

    const sourceEntry = boundary[edge.source_node_id];
    if (sourceEntry) {
        const decl = sourceEntry.template.outputs.find(
            (port) => port.port_id === edge.source_port,
        );
        if (!decl) {
            diagnostics.push({
                severity: "error",
                code: "composite_unbound_output",
                message: `Composite output port '${edge.source_port}' has no binding.`,
            });
            return null;
        }
        next.source_node_id =
            sourceEntry.idMap[decl.internal_node_id] ?? decl.internal_node_id;
        next.source_port = decl.internal_port;
    }

    const targetEntry = boundary[edge.target_node_id];
    if (targetEntry) {
        const decl = targetEntry.template.inputs.find(
            (port) => port.port_id === edge.target_port,
        );
        if (!decl) {
            diagnostics.push({
                severity: "error",
                code: "composite_unbound_input",
                message: `Composite input port '${edge.target_port}' has no binding.`,
            });
            return null;
        }
        next.target_node_id =
            targetEntry.idMap[decl.internal_node_id] ?? decl.internal_node_id;
        next.target_port = decl.internal_port;
    }

    return next;
}

// Inline every composite instance into primitives. Returns a backend-safe graph.
export function flattenGraph(
    graph: EditorGraphDefinition,
    resolveTemplate: (compositeId: string) => CompositeTemplate | undefined,
): { graph: StreamGraphDefinition; diagnostics: StreamGraphDiagnostic[] } {
    const diagnostics: StreamGraphDiagnostic[] = [];
    const boundary: Record<string, BoundaryEntry> = {};
    const missingInstances = new Set<string>();

    const primitiveNodes: StreamGraphNode[] = [];
    const innerEdges: StreamGraphEdge[] = [];
    const paramNodeIds = new Set<string>();

    for (const node of graph.nodes) {
        if (isParamNode(node)) {
            // Editor-only control node — its value is already written into the
            // target transform's config, so it's dropped from the executed graph.
            paramNodeIds.add(node.id);
            continue;
        }
        if (!isCompositeInstance(node)) {
            primitiveNodes.push(deepClone(node) as StreamGraphNode);
            continue;
        }
        const template = node.template ?? resolveTemplate(node.composite_id);
        if (!template) {
            missingInstances.add(node.id);
            diagnostics.push({
                severity: "error",
                code: "composite_template_missing",
                message: `Composite '${node.label}' has no available template definition.`,
            });
            continue;
        }
        if (
            node.template &&
            node.composite_version !== template.composite_version
        ) {
            diagnostics.push({
                severity: "warning",
                code: "composite_version_drift",
                message: `Composite '${node.label}' version differs from its template.`,
            });
        }
        const expanded = expandInstance(node, template);
        primitiveNodes.push(...expanded.nodes);
        innerEdges.push(...expanded.edges);
        boundary[node.id] = { template, idMap: expanded.idMap };
    }

    const outerEdges: StreamGraphEdge[] = [];
    for (const edge of graph.edges) {
        if (
            missingInstances.has(edge.source_node_id) ||
            missingInstances.has(edge.target_node_id) ||
            paramNodeIds.has(edge.source_node_id) ||
            paramNodeIds.has(edge.target_node_id)
        ) {
            continue;
        }
        const rewired = rewireEdge(edge, boundary, diagnostics);
        if (rewired) {
            outerEdges.push(rewired);
        }
    }

    const flattened: StreamGraphDefinition = {
        ...graph,
        nodes: primitiveNodes,
        edges: [...outerEdges, ...innerEdges],
    };
    return { graph: flattened, diagnostics };
}

// ---------------------------------------------------------------------------
// Authoring: create a composite from selected nodes, and ungroup an instance
// ---------------------------------------------------------------------------

function centroid(nodes: EditorGraphNode[]): StreamGraphPosition {
    if (nodes.length === 0) {
        return { x: 0, y: 0 };
    }
    const sum = nodes.reduce(
        (acc, node) => ({
            x: acc.x + node.position.x,
            y: acc.y + node.position.y,
        }),
        { x: 0, y: 0 },
    );
    return {
        x: Math.round(sum.x / nodes.length),
        y: Math.round(sum.y / nodes.length),
    };
}

export function extractCompositeFromSelection(
    graph: EditorGraphDefinition,
    selectedIds: Set<string>,
    label: string,
): {
    template: CompositeTemplate;
    instance: CompositeInstanceNode;
    nextGraph: EditorGraphDefinition;
} | null {
    const selected = graph.nodes.filter((node) => selectedIds.has(node.id));
    if (selected.length === 0) {
        return null;
    }
    // v1: composites may not contain other composites.
    if (selected.some((node) => isCompositeInstance(node))) {
        return null;
    }
    const selectedPrimitives = selected as StreamGraphNode[];

    const isInternal = (edge: StreamGraphEdge) =>
        selectedIds.has(edge.source_node_id) &&
        selectedIds.has(edge.target_node_id);

    const internalEdges = graph.edges.filter(isInternal);

    // Boundary pins, deduped by (node, port).
    const inputMap = new Map<string, CompositePortDecl>();
    const outputMap = new Map<string, CompositePortDecl>();
    for (const edge of graph.edges) {
        const sourceInside = selectedIds.has(edge.source_node_id);
        const targetInside = selectedIds.has(edge.target_node_id);
        if (targetInside && !sourceInside) {
            const key = `${edge.target_node_id}:${edge.target_port}`;
            if (!inputMap.has(key)) {
                inputMap.set(key, {
                    port_id: `in${inputMap.size + 1}`,
                    label: `Input ${inputMap.size + 1}`,
                    internal_node_id: edge.target_node_id,
                    internal_port: edge.target_port,
                });
            }
        }
        if (sourceInside && !targetInside) {
            const key = `${edge.source_node_id}:${edge.source_port}`;
            if (!outputMap.has(key)) {
                outputMap.set(key, {
                    port_id: `out${outputMap.size + 1}`,
                    label: `Output ${outputMap.size + 1}`,
                    internal_node_id: edge.source_node_id,
                    internal_port: edge.source_port,
                });
            }
        }
    }
    const inputs = [...inputMap.values()];
    const outputs = [...outputMap.values()];

    // Normalize template node positions to the selection bounding-box origin.
    const minX = Math.min(...selectedPrimitives.map((node) => node.position.x));
    const minY = Math.min(...selectedPrimitives.map((node) => node.position.y));
    const templateNodes: StreamGraphNode[] = selectedPrimitives.map((node) => {
        const cloned = deepClone(node);
        cloned.position = {
            x: node.position.x - minX,
            y: node.position.y - minY,
        };
        return cloned;
    });
    const templateEdges = internalEdges.map((edge) => deepClone(edge));

    const nowUs = Date.now() * 1000;
    const template: CompositeTemplate = {
        composite_version: 1,
        composite_id: createCompositeId(),
        label,
        description: "",
        created_at_us: nowUs,
        updated_at_us: nowUs,
        nodes: templateNodes,
        edges: templateEdges,
        inputs,
        outputs,
    };

    const ports = instancePortsFromTemplate(template);
    const instance: CompositeInstanceNode = {
        id: `composite/${sanitizeIdentifier(label) || "group"}-${uniqueSuffix()}`,
        kind: "composite",
        label,
        position: centroid(selectedPrimitives),
        composite_id: template.composite_id,
        composite_version: 1,
        input_port_ids: ports.input_port_ids,
        output_port_ids: ports.output_port_ids,
        template: deepClone(template),
    };

    // Reindex external edges onto the instance boundary; drop internal edges.
    const declForInternalInput = new Map(
        inputs.map((decl) => [
            `${decl.internal_node_id}:${decl.internal_port}`,
            decl,
        ]),
    );
    const declForInternalOutput = new Map(
        outputs.map((decl) => [
            `${decl.internal_node_id}:${decl.internal_port}`,
            decl,
        ]),
    );

    const nextEdges: StreamGraphEdge[] = [];
    for (const edge of graph.edges) {
        if (isInternal(edge)) {
            continue;
        }
        const sourceInside = selectedIds.has(edge.source_node_id);
        const targetInside = selectedIds.has(edge.target_node_id);
        if (!sourceInside && !targetInside) {
            nextEdges.push(edge);
            continue;
        }
        const next: StreamGraphEdge = { ...edge };
        if (sourceInside) {
            const decl = declForInternalOutput.get(
                `${edge.source_node_id}:${edge.source_port}`,
            );
            if (!decl) {
                continue;
            }
            next.source_node_id = instance.id;
            next.source_port = decl.port_id;
        }
        if (targetInside) {
            const decl = declForInternalInput.get(
                `${edge.target_node_id}:${edge.target_port}`,
            );
            if (!decl) {
                continue;
            }
            next.target_node_id = instance.id;
            next.target_port = decl.port_id;
        }
        nextEdges.push(next);
    }

    const nextNodes: EditorGraphNode[] = graph.nodes
        .filter((node) => !selectedIds.has(node.id))
        .concat(instance);

    const nextGraph: EditorGraphDefinition = {
        ...graph,
        nodes: nextNodes,
        edges: nextEdges,
    };

    return { template, instance, nextGraph };
}

// Inline one composite instance back into editor primitives (keeps other composites).
export function ungroupInstance(
    graph: EditorGraphDefinition,
    instanceId: string,
): EditorGraphDefinition {
    const instance = graph.nodes.find(
        (node) => node.id === instanceId && isCompositeInstance(node),
    ) as CompositeInstanceNode | undefined;
    if (!instance || !instance.template) {
        return graph;
    }
    const template = instance.template;
    const expanded = expandInstance(instance, template);
    const boundary: Record<string, BoundaryEntry> = {
        [instance.id]: { template, idMap: expanded.idMap },
    };

    const outerEdges: StreamGraphEdge[] = [];
    for (const edge of graph.edges) {
        const rewired = rewireEdge(edge, boundary, []);
        if (rewired) {
            outerEdges.push(rewired);
        }
    }

    const nextNodes: EditorGraphNode[] = graph.nodes
        .filter((node) => node.id !== instanceId)
        .concat(expanded.nodes);

    return {
        ...graph,
        nodes: nextNodes,
        edges: [...outerEdges, ...expanded.edges],
    };
}

// Instantiate a library template as a fresh instance node on the canvas.
export function instantiateComposite(
    template: CompositeTemplate,
    position: StreamGraphPosition,
): CompositeInstanceNode {
    const ports = instancePortsFromTemplate(template);
    return {
        id: `composite/${sanitizeIdentifier(template.label) || "composite"}-${uniqueSuffix()}`,
        kind: "composite",
        label: template.label,
        position: { ...position },
        composite_id: template.composite_id,
        composite_version: template.composite_version,
        input_port_ids: ports.input_port_ids,
        output_port_ids: ports.output_port_ids,
        template: deepClone(template),
    };
}

// ---------------------------------------------------------------------------
// Validation + export/import
// ---------------------------------------------------------------------------

export function validateCompositeTemplate(
    template: CompositeTemplate,
): StreamGraphDiagnostic[] {
    const diagnostics: StreamGraphDiagnostic[] = [];
    const nodeIds = new Set(template.nodes.map((node) => node.id));
    for (const decl of [...template.inputs, ...template.outputs]) {
        if (!nodeIds.has(decl.internal_node_id)) {
            diagnostics.push({
                severity: "error",
                code: "composite_dangling_boundary",
                message: `Boundary port '${decl.port_id}' references a missing internal node.`,
            });
        }
    }
    if (template.nodes.length === 0) {
        diagnostics.push({
            severity: "error",
            code: "composite_empty",
            message: "Composite has no internal nodes.",
        });
    }
    return diagnostics;
}

export function serializeCompositeExport(
    templates: CompositeTemplate[],
): CompositeExportFile {
    return {
        file_type: "natkit.composite",
        file_version: 1,
        exported_at_us: Date.now() * 1000,
        templates: templates.map((template) => deepClone(template)),
    };
}

export function parseCompositeExportFile(text: string): {
    templates: CompositeTemplate[];
    errors: string[];
} {
    const errors: string[] = [];
    let parsed: unknown;
    try {
        parsed = JSON.parse(text);
    } catch {
        return { templates: [], errors: ["File is not valid JSON."] };
    }
    const file = parsed as Partial<CompositeExportFile>;
    if (file?.file_type !== "natkit.composite") {
        errors.push("Not a natKit composite file (missing file_type).");
        return { templates: [], errors };
    }
    if (file.file_version !== 1) {
        errors.push(`Unsupported composite file version: ${file.file_version}.`);
        return { templates: [], errors };
    }
    if (!Array.isArray(file.templates)) {
        errors.push("Composite file has no templates array.");
        return { templates: [], errors };
    }
    const templates: CompositeTemplate[] = [];
    for (const candidate of file.templates) {
        if (
            candidate &&
            typeof candidate.composite_id === "string" &&
            Array.isArray(candidate.nodes) &&
            Array.isArray(candidate.edges) &&
            Array.isArray(candidate.inputs) &&
            Array.isArray(candidate.outputs)
        ) {
            templates.push(candidate);
        } else {
            errors.push("Skipped a malformed composite template.");
        }
    }
    return { templates, errors };
}
