/**
 * The label a port wears when its channel carries BOTH data and markers.
 *
 * ⚠️ Shared between the node card and the editor's edge renderer on purpose —
 * both compare against it, and a copy in each would let the two drift into
 * disagreeing about whether a port is a bundle.
 */
export const BOTH_LABEL = "data and markers";

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

// Provenance ports carry data lineage / control wiring, not streaming data.
// They are identified purely by an id prefix so the editor can classify an edge
// as provenance from its endpoints (a provenance-typed port on either end makes
// the edge a provenance edge), render them distinctly, and validate connect
// rules.
//
// Only the train → classify pair remains. `prov_source` (source → experiment)
// and `prov_experiment` (experiment → train) were RETIRED
// (experiment-history-snapshots-plan): the experiment owns the whole board now,
// so every source in it is a recorded source and the trainer's runs are scoped by
// the board's binding — that lineage is implicit, and drawing it was busywork.
// A model artifact, by contrast, IS a real handoff between two nodes that nothing
// else expresses.
export const PROVENANCE_PORT_PREFIX = "prov_";
// The train node's outbound lineage port (train → classify): "the models this
// trainer produced".
export const PROVENANCE_PORT_MODELS = "prov_models";
// The classify node's inbound lineage port (train → classify): "classify with a
// model this trainer produced".
export const PROVENANCE_PORT_MODEL = "prov_model";

export function isProvenancePort(portId: string | undefined | null): boolean {
    return typeof portId === "string" && portId.startsWith(PROVENANCE_PORT_PREFIX);
}

export const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 1 };
export const NODE_WIDTH = 220;
// ⚠️ MUST MATCH `.node-header`'s height/flex-basis in StreamGraphNode.svelte.
// Node heights and every port anchor are computed from this, so a header that
// is taller in CSS than here pushes the ports out of their dots.
export const HEADER_HEIGHT = 32;
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

// One marble-strip row's height, including its gap (TEC-NATKIT-106). A card
// reserves this per reported lane so the strips have somewhere to be drawn.
//
// ⚠️ THE STRIPS MUST NOT LIVE INSIDE `.node-meta`. They did at first, and that
// column sits between the two port columns — so with a 2.4rem label and a
// 1.8rem count either side, the track measured TWO PIXELS wide. It rendered all
// 160 density columns into it, correctly, and looked like an empty box: every
// unit test passed and the feature was invisible. They belong in a full-width
// block below the body, which is why this height is added on rather than
// absorbed into the existing slack.
export const MARBLE_ROW_HEIGHT = 14;

export function getNodeHeight(
    node: EditorGraphNode,
    marbleRows = 0,
): number {
    const inputRows = Math.max(node.input_port_ids?.length ?? 0, 0);
    const outputRows = Math.max(node.output_port_ids?.length ?? 0, 0);
    const rows = Math.max(inputRows, outputRows, 1);
    let height = HEADER_HEIGHT + rows * PORT_ROW_HEIGHT + 22;
    if (node.kind === "viewer" && node.inline_graph) {
        height += INLINE_GRAPH_HEIGHT;
    }
    // Ports are anchored to the TOP (see getPortPosition), so growing the card
    // downward never moves one and edges stay attached.
    height += marbleRows * MARBLE_ROW_HEIGHT;
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

/**
 * Filters a node's catalog config fields down to those that apply given its
 * current config, honouring each field's optional `visible_when`.
 *
 * Why this exists rather than per-node conditionals in the inspector: combine's
 * align tolerance is meaningful only under the `zip` join policy and its output
 * rate only under `sample`, and showing all three at once invites setting a
 * value that is silently ignored. Keeping the rule in the field's own
 * advertisement means a future node with mode-dependent config needs no
 * frontend change at all — which is the whole point of the runtime catalog.
 *
 * A field with no `visible_when` is always visible. A guard whose named field is
 * absent from `config` falls back to that field's own default (`default_option`,
 * then `default_value`), so an unsaved node shows the same fields the backend
 * would actually run with rather than hiding everything.
 */
export function visibleConfigFields<
    T extends {
        id: string;
        default_option?: string;
        default_value?: number;
        visible_when?: { field: string; equals: string[] };
    },
>(fields: T[], config: Record<string, unknown> | undefined | null): T[] {
    const resolve = (fieldId: string): string | undefined => {
        const current = config?.[fieldId];
        if (current !== undefined && current !== null) {
            return String(current);
        }
        const declared = fields.find((field) => field.id === fieldId);
        if (declared?.default_option !== undefined) {
            return declared.default_option;
        }
        if (declared?.default_value !== undefined) {
            return String(declared.default_value);
        }
        return undefined;
    };

    return fields.filter((field) => {
        if (!field.visible_when) {
            return true;
        }
        const actual = resolve(field.visible_when.field);
        if (actual === undefined) {
            return false;
        }
        return field.visible_when.equals.includes(actual);
    });
}

/**
 * The label a config-field option should wear in a picker: its positionally
 * matched `option_labels` entry, or the raw wire value when none is advertised.
 */
export function configOptionLabel(
    field: { options?: string[]; option_labels?: string[] },
    option: string,
): string {
    const index = field.options?.indexOf(option) ?? -1;
    if (index < 0) {
        return option;
    }
    return field.option_labels?.[index] ?? option;
}
