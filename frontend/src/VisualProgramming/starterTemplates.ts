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

// Convention-tuned protocol (Phase 3): a short session sized for the 1–5 min
// walk-up budget and for accuracy. Few, well-separated gestures + rest; includes
// `fist`, which doubles as the rest-calibration active gesture (a strong
// full-forearm contraction) and is classified like any other class. ~9 cues *
// (2s hold + 2s rest) + lead-in/tail ≈ 45 s.
export const CONVENTION_PROTOCOL = {
    protocol_id: "convention-emg-v1",
    label: "Convention EMG",
    classes: ["fist", "open_hand", "point"],
    rest_class: "rest",
    repetitions: 3,
    hold_s: 2,
    rest_s: 2,
    lead_in_s: 3,
    tail_rest_s: 2,
    seed: 1,
};

export const STARTER_TEMPLATES: StarterTemplate[] = [
    {
        id: "convention-emg-quick-start",
        label: "Convention EMG Quick-Start",
        description:
            "Walk-up EMG gesture flow: live source, a short convention protocol, per-stage viewers, a train node, and a pre-placed gesture classifier.",
        build(streamId) {
            const s = suffix();
            const graph = baseGraph(
                "Convention EMG Quick-Start",
                "1) Check the live signal + electrode placement in the raw viewer. " +
                    "2) Press Record on the experiment to run the gesture cues. " +
                    "3) In the timeline's Experiments library, pick the just-recorded " +
                    "run for the Train node, then Submit. 4) The trained bundle " +
                    "auto-fills the classifier — press Start to classify live.",
            );
            graph.nodes = [
                source(streamId),
                // Raw live viewer — signal quality + electrode placement check.
                {
                    id: "raw-viewer",
                    kind: "viewer",
                    label: "Raw EMG",
                    position: { x: 360, y: 80 },
                    input_port_ids: ["input"],
                },
                // The self-contained gesture classifier. model_path starts empty
                // and is auto-filled from the completed train job's bundle; the
                // node only needs a valid path at Start time, not at load.
                {
                    id: "classify",
                    kind: "transform",
                    label: "EMG Gesture Classify",
                    position: { x: 360, y: 300 },
                    transform_kind: "emg_gesture_classify",
                    input_mapping_id: "canonical_channel_frame",
                    config: { model_path: "" },
                    output_identifier: `starter-clf-${s}`,
                    input_port_ids: ["input"],
                    output_port_ids: ["output"],
                },
                // Live classification readout (predicted class + confidences).
                {
                    id: "classify-viewer",
                    kind: "viewer",
                    label: "Prediction",
                    position: { x: 700, y: 300 },
                    input_port_ids: ["input"],
                },
                // Standalone marker timeline for the gesture cues.
                {
                    id: "experiment",
                    kind: "experiment",
                    label: "Gesture session",
                    position: { x: 40, y: 520 },
                    input_port_ids: [],
                    output_port_ids: ["markers"],
                    config: {
                        protocol: { ...CONVENTION_PROTOCOL },
                        experiment_id: "convention-emg-session",
                        participant_id: "",
                        notes: "",
                    },
                },
                {
                    id: "markers-viewer",
                    kind: "viewer",
                    label: "Cues",
                    position: { x: 360, y: 520 },
                    input_port_ids: ["input"],
                },
                // Train node: after recording, select the run in the Experiments
                // library and Submit. LDA is the only live-deployable family.
                {
                    id: "train",
                    kind: "train",
                    label: "Train",
                    position: { x: 700, y: 520 },
                    input_port_ids: [],
                    output_port_ids: [],
                    config: {
                        families: ["lda"],
                        train_runs: [],
                        eval_runs: [],
                        selected_fields: [],
                        window_ms: 200,
                        hop_ms: 50,
                        vote_windows: 1,
                        confidence_threshold: 0,
                        min_hold_windows: 1,
                        rest_gesture: "rest",
                        active_gesture: "fist",
                    },
                },
            ];
            graph.edges = [
                edge("source", "data", "raw-viewer", "input"),
                edge("source", "data", "classify", "input"),
                edge("classify", "output", "classify-viewer", "input"),
                edge("experiment", "markers", "markers-viewer", "input"),
            ];
            return graph;
        },
    },
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
        id: "record-an-experiment",
        label: "Record an experiment",
        description:
            "A finger-counting experiment emitting a marker timeline into a viewer.",
        build() {
            const graph = baseGraph(
                "Record an experiment",
                "A source-like experiment that cues finger-counting gestures (1–5) and emits a labeled marker timeline; press Record, then watch the markers.",
            );
            graph.nodes = [
                {
                    id: "experiment",
                    kind: "experiment",
                    label: "Experiment",
                    position: { x: 120, y: 200 },
                    input_port_ids: [],
                    output_port_ids: ["markers"],
                    config: {
                        protocol: {
                            protocol_id: "finger-counting-v1",
                            label: "Finger counting",
                            classes: [
                                "count_1",
                                "count_2",
                                "count_3",
                                "count_4",
                                "count_5",
                            ],
                            rest_class: "rest",
                            repetitions: 3,
                            hold_s: 2,
                            rest_s: 2,
                            lead_in_s: 3,
                            tail_rest_s: 2,
                            seed: 1,
                        },
                        experiment_id: "finger-counting-experiment",
                        participant_id: "",
                        notes: "",
                    },
                },
                {
                    id: "viewer",
                    kind: "viewer",
                    label: "Markers",
                    position: { x: 460, y: 200 },
                    input_port_ids: ["input"],
                },
            ];
            graph.edges = [edge("experiment", "markers", "viewer", "input")];
            return graph;
        },
    },
];
