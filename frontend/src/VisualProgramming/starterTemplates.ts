// Starter template library (Phase 8): one-click preset boards so a first-time
// user reaches a working pipeline without authoring it node-by-node. Each
// builder returns a fresh EditorGraphDefinition; the source is bound to an
// available stream when one is passed, else left blank for the user to pick.

import type { EditorGraphDefinition } from "./composites";

export interface StarterTemplate {
    id: string;
    label: string;
    description: string;
    build: (sourceStreamId: string | null) => EditorGraphDefinition;
}

function baseGraph(label: string, description: string): EditorGraphDefinition {
    const nowUs = Date.now() * 1000;
    return {
        graph_version: 1,
        graph_id: `starter-${Date.now()}`,
        label,
        description,
        created_at_us: nowUs,
        updated_at_us: nowUs,
        ui: { viewport: { x: 0, y: 0, zoom: 1 }, selected_node_id: null },
        nodes: [],
        edges: [],
        notes: [],
    };
}

function suffix(): string {
    return `${Date.now()}`;
}

function source(streamId: string | null): EditorGraphDefinition["nodes"][number] {
    return {
        id: "source",
        kind: "stream_source",
        label: "Stream source",
        position: { x: 40, y: 200 },
        stream_id: streamId ?? "",
        output_port_ids: ["data"],
    };
}

function edge(from: string, fromPort: string, to: string, toPort: string) {
    return {
        id: `edge-${from}-${to}`,
        source_node_id: from,
        source_port: fromPort,
        target_node_id: to,
        target_port: toPort,
    };
}

export const STARTER_TEMPLATES: StarterTemplate[] = [
    {
        id: "view-a-stream",
        label: "View a stream",
        description: "A source wired straight into a live viewer.",
        build(streamId) {
            const graph = baseGraph(
                "View a stream",
                "A source wired to a viewer — pick a stream and press Start.",
            );
            graph.nodes = [
                source(streamId),
                {
                    id: "viewer",
                    kind: "viewer",
                    label: "Viewer",
                    position: { x: 340, y: 200 },
                    input_port_ids: ["input"],
                },
            ];
            graph.edges = [edge("source", "data", "viewer", "input")];
            return graph;
        },
    },
    {
        id: "filter-envelope",
        label: "Filter + envelope",
        description: "Band-pass → rectify → low-pass envelope → viewer.",
        build(streamId) {
            const s = suffix();
            const graph = baseGraph(
                "Filter + envelope",
                "Band-pass, rectify, and smooth a channel-frame stream, then view it.",
            );
            graph.nodes = [
                source(streamId),
                {
                    id: "bandpass",
                    kind: "transform",
                    label: "Band-pass IIR",
                    position: { x: 300, y: 200 },
                    transform_kind: "bandpass_iir",
                    input_mapping_id: "canonical_channel_frame",
                    config: {
                        low_cutoff_hz: 20,
                        high_cutoff_hz: 450,
                        iir_method: "butterworth",
                        butterworth_order: 2,
                        biquad_q: 0.7071,
                    },
                    output_identifier: `starter-bp-${s}`,
                    input_port_ids: ["input"],
                    output_port_ids: ["output"],
                },
                {
                    id: "rectify",
                    kind: "transform",
                    label: "Rectify",
                    position: { x: 560, y: 200 },
                    transform_kind: "rectify",
                    input_mapping_id: "canonical_channel_frame",
                    config: {},
                    output_identifier: `starter-rect-${s}`,
                    input_port_ids: ["input"],
                    output_port_ids: ["output"],
                },
                {
                    id: "envelope",
                    kind: "transform",
                    label: "Low-pass envelope",
                    position: { x: 820, y: 200 },
                    transform_kind: "lowpass_envelope",
                    input_mapping_id: "canonical_channel_frame",
                    config: { cutoff_hz: 5 },
                    output_identifier: `starter-env-${s}`,
                    input_port_ids: ["input"],
                    output_port_ids: ["output"],
                },
                {
                    id: "viewer",
                    kind: "viewer",
                    label: "Viewer",
                    position: { x: 1080, y: 200 },
                    input_port_ids: ["input"],
                },
            ];
            graph.edges = [
                edge("source", "data", "bandpass", "input"),
                edge("bandpass", "output", "rectify", "input"),
                edge("rectify", "output", "envelope", "input"),
                edge("envelope", "output", "viewer", "input"),
            ];
            return graph;
        },
    },
    {
        id: "record-a-session",
        label: "Record a session",
        description: "A source feeding a 2-class recording session.",
        build(streamId) {
            const graph = baseGraph(
                "Record a session",
                "Record a labeled 2-class session from a stream, ready to train.",
            );
            graph.nodes = [
                source(streamId),
                {
                    id: "session",
                    kind: "session",
                    label: "Session",
                    position: { x: 340, y: 200 },
                    input_port_ids: ["in1"],
                    config: {
                        protocol: {
                            protocol_id: "starter-2class",
                            label: "Two-class starter",
                            classes: ["rest", "active"],
                            rest_class: "rest",
                            repetitions: 5,
                            hold_s: 3,
                            rest_s: 2,
                            lead_in_s: 3,
                            tail_rest_s: 2,
                            seed: 1,
                        },
                        participant_id: "",
                        notes: "",
                    },
                },
            ];
            graph.edges = [edge("source", "data", "session", "in1")];
            return graph;
        },
    },
];
