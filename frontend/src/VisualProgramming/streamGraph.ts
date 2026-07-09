// Pure helpers for the Stream Graph editor. Kept free of Svelte state so they
// stay unit-testable without a browser.
import type {
    DataSchemaDescriptor,
    SchemaFieldDescriptor,
    SchemaFieldValueType,
    StreamGraphDefinition,
    TransformCapability,
} from "../StreamViewer/types";
import type { EditorGraphNode } from "./composites";

export interface GraphStreamOption {
    streamId: string;
    schemaName: string;
    descriptor?: DataSchemaDescriptor;
    live: boolean;
}

export const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 1 };
export const NODE_WIDTH = 220;
export const HEADER_HEIGHT = 42;
export const PORT_ROW_HEIGHT = 28;
// Extra height a viewer node reserves below its ports to host an inline live
// chart. Ports are anchored to the top (see getPortPosition), so growing the
// card downward never moves a port and edges stay attached.
export const INLINE_GRAPH_HEIGHT = 210;

export function createEmptyGraph(): StreamGraphDefinition {
    const nowUs = Date.now() * 1000;
    return {
        graph_version: 1,
        graph_id: `stream-graph-${Date.now()}`,
        label: "Untitled graph",
        description: "",
        created_at_us: nowUs,
        updated_at_us: nowUs,
        ui: {
            viewport: { ...DEFAULT_VIEWPORT },
            selected_node_id: null,
        },
        nodes: [],
        edges: [],
        notes: [],
    };
}

export function cloneGraph<T>(graph: T): T {
    return JSON.parse(JSON.stringify(graph)) as T;
}

export function sanitizeIdentifier(value: string): string {
    return value
        .replace(/[^A-Za-z0-9_-]/g, "-")
        .replace(/--+/g, "-")
        .replace(/^-+/, "")
        .slice(0, 64);
}

export function getNodeHeight(node: EditorGraphNode): number {
    const inputRows = Math.max(node.input_port_ids?.length ?? 0, 0);
    const outputRows = Math.max(node.output_port_ids?.length ?? 0, 0);
    const rows = Math.max(inputRows, outputRows, 1);
    let height = HEADER_HEIGHT + rows * PORT_ROW_HEIGHT + 22;
    if (node.kind === "viewer" && node.inline_graph) {
        height += INLINE_GRAPH_HEIGHT;
    }
    return height;
}

export function getPortPosition(
    node: EditorGraphNode,
    portId: string,
    side: "input" | "output",
): { x: number; y: number } {
    const ports =
        side === "input"
            ? node.input_port_ids ?? []
            : node.output_port_ids ?? [];
    const portIndex = Math.max(0, ports.indexOf(portId));
    return {
        x: node.position.x + (side === "input" ? 0 : NODE_WIDTH),
        y:
            node.position.y +
            HEADER_HEIGHT +
            PORT_ROW_HEIGHT * portIndex +
            PORT_ROW_HEIGHT / 2,
    };
}

export function buildDefaultTransformConfig(
    capability: TransformCapability,
): Record<string, number | string | boolean> {
    const config: Record<string, number | string | boolean> = {};
    for (const field of capability.config_fields) {
        if (field.default_value !== undefined) {
            config[field.id] = field.default_value;
        } else if (field.default_option !== undefined) {
            config[field.id] = field.default_option;
        }
    }
    return config;
}

export function getOutputDescriptorForNode(
    node: EditorGraphNode | undefined,
    availableStreams: GraphStreamOption[],
): DataSchemaDescriptor | undefined {
    if (!node) {
        return undefined;
    }
    if (node.kind === "stream_source") {
        return availableStreams.find(
            (stream) => stream.streamId === node.stream_id,
        )?.descriptor;
    }
    if (node.kind === "transform" || node.kind === "combine") {
        // A transform/combine emits a canonical numeric channel frame. Return a
        // descriptor with the actual channel-frame fields (not an empty stub) so
        // downstream compatibility checks — descriptorSupportsNumericChannelFrames,
        // input-mapping auto-pick, and the Phase-8 "recommended next" list —
        // resolve correctly.
        const field = (
            id: string,
            type: SchemaFieldValueType,
            extra: Partial<SchemaFieldDescriptor> = {},
        ): SchemaFieldDescriptor => ({
            id,
            label: id,
            type,
            optional: false,
            ...extra,
        });
        return {
            schema_name: "NatSignalFrameDataSchemaV1",
            descriptor_version: 1,
            root: field("root", "object", {
                fields: {
                    device_id: field("device_id", "string"),
                    seq_no: field("seq_no", "uint64"),
                    device_ts_us: field("device_ts_us", "uint64"),
                    sample_rate_hz: field("sample_rate_hz", "uint32"),
                    channels: field("channels", "array", {
                        items: field("channel", "object", {
                            fields: {
                                label: field("label", "string"),
                                samples: field("samples", "array", {
                                    items: field("sample", "float32"),
                                }),
                            },
                        }),
                    }),
                },
            }),
        };
    }
    return undefined;
}

export function graphRunStateClass(
    state: string | undefined,
): "ok" | "error" | "muted" {
    if (state === "running" || state === "valid") {
        return "ok";
    }
    if (state === "error" || state === "stalled") {
        return "error";
    }
    return "muted";
}
