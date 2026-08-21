// Starter template library (Phase 8): one-click preset boards so a first-time
// user reaches a working pipeline without authoring it node-by-node. Each
// builder returns a fresh EditorGraphDefinition; the source is bound to an
// available stream when one is passed, else left blank for the user to pick.

import type { SessionProtocol } from "../StreamViewer/types";
// The ADL task list lives with the page it came from. Imported rather than copied:
// two task lists that drift is exactly the failure the retirement ticket (#412)
// exists to avoid while both paths are alive.
import { adlStepProtocol } from "../AdlExperiment/tasks";
import type { EditorGraphDefinition } from "./composites";
import { PROVENANCE_PORT_MODELS, PROVENANCE_PORT_MODEL } from "./streamGraph";

export interface StarterTemplate {
    id: string;
    label: string;
    description: string;
    build: (sourceStreamId: string | null) => EditorGraphDefinition;
    // A template that records also needs an EXPERIMENT, not just a board: the
    // protocol lives in the experiment record now, and the board's `markers` node
    // resolves its topic from whichever experiment is bound
    // (experiment-history-snapshots-plan). The loader creates + binds this one.
    experiment?: { label: string; protocol: SessionProtocol };
    // A template that is a whole study, not just a board, also names a WORKSPACE
    // (TEC-NATKIT-56). The loader creates it and switches to it, so the experiment
    // and board it makes are filed there rather than dropped into Unfiled — where
    // they would immediately vanish from the lists the user is looking at.
    workspace?: { label: string };
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
        // ⚠️ OMITTED, not "", when there is no stream to bind (TEC-NATKIT-66).
        //
        // The backend parses `stream_id` only `if (json.contains("stream_id"))` and
        // then demands a non-negative integer, so an empty string makes the whole
        // board unsavable — and a rig that is not currently streaming has no stream
        // to offer, which is its normal resting state. Every template shares this
        // helper, so `?? ""` broke all five of them there: the board appeared on the
        // canvas, its save was rejected, and the experiment save then failed with
        // "Unknown graph" because its live_graph_id had never been persisted.
        //
        // An absent stream_id is exactly what "pick a stream later" should serialize
        // to, which is what the source inspector's dropdown is for.
        ...(streamId ? { stream_id: streamId } : {}),
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

// A provenance (lineage/control) edge — dropped from the executed graph. Only
// train→classify remains: it feeds the classify node's model dropdown. The
// source→experiment and experiment→train edges were retired once the experiment
// came to own the whole board.
function provEdge(from: string, fromPort: string, to: string, toPort: string) {
    return {
        id: `prov-${from}-${to}`,
        source_node_id: from,
        source_port: fromPort,
        target_node_id: to,
        target_port: toPort,
        edge_kind: "provenance" as const,
    };
}

// Convention-tuned protocol (Phase 3): few, well-separated gestures + rest;
// includes `fist`, which doubles as the rest-calibration active gesture (a
// strong full-forearm contraction) and is classified like any other class.
// Sized to ~2 min of samples for accuracy: 8 reps × 3 gestures × (3s hold + 2s
// rest) + lead-in/tail ≈ 125 s (24 holds/gesture-set, 72 s of gesture data —
// ~4× the earlier 3-rep/2s version, which trained noticeably worse). More
// repetitions matter more than longer holds for generalization, so we scaled
// reps; bump `hold_s` if a longer steady contraction per cue is preferred.
export const CONVENTION_PROTOCOL: SessionProtocol = {
    protocol_id: "convention-emg-v1",
    label: "Convention EMG",
    classes: ["fist", "open_hand", "point"],
    rest_class: "rest",
    repetitions: 8,
    hold_s: 3,
    rest_s: 2,
    lead_in_s: 3,
    tail_rest_s: 2,
    seed: 1,
    // Its own words back (TEC-NATKIT-69): the neutral default would read
    // "task", and for an isometric EMG protocol the HOLD is the instruction.
    participant_copy: {
        cue_noun: "gesture",
        cue_noun_plural: "gestures",
        cue_instruction: "Make and hold this gesture",
        rest_instruction: "Relax your hand",
    },
};

// The finger-counting protocol the "Record an experiment" starter binds.
export const FINGER_COUNTING_STARTER_PROTOCOL: SessionProtocol = {
    protocol_id: "finger-counting-v1",
    label: "Finger counting",
    classes: ["count_1", "count_2", "count_3", "count_4", "count_5"],
    rest_class: "rest",
    repetitions: 3,
    hold_s: 2,
    rest_s: 2,
    lead_in_s: 3,
    tail_rest_s: 2,
    seed: 1,
    // Its own words back (TEC-NATKIT-69): the neutral default would read
    // "task", and for an isometric EMG protocol the HOLD is the instruction.
    participant_copy: {
        cue_noun: "gesture",
        cue_noun_plural: "gestures",
        cue_instruction: "Make and hold this gesture",
        rest_instruction: "Relax your hand",
    },
};

export const STARTER_TEMPLATES: StarterTemplate[] = [
    {
        id: "convention-emg-quick-start",
        label: "Convention EMG Quick-Start",
        description:
            "Walk-up EMG gesture flow: live source, a short convention protocol, per-stage viewers, a train node, and a pre-placed gesture classifier.",
        experiment: {
            label: "Convention EMG",
            protocol: { ...CONVENTION_PROTOCOL },
        },
        build(streamId) {
            const s = suffix();
            const graph = baseGraph(
                "Convention EMG Quick-Start",
                "1) Check the live signal + electrode placement in the raw viewer. " +
                    "2) Press Record in the Experiment panel (or double-click the " +
                    "Markers node) to run the gesture cues — follow the prompts, " +
                    "~2 min. 3) In the timeline's Experiments library, pick the " +
                    "just-recorded run for the Train node, then Submit. 4) The " +
                    "trained bundle auto-fills the classifier — press Start to " +
                    "classify live.",
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
                    input_port_ids: ["input", PROVENANCE_PORT_MODEL],
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
                // The bound experiment's cue timeline as a stream.
                {
                    id: "markers",
                    kind: "markers",
                    label: "Markers",
                    position: { x: 40, y: 520 },
                    input_port_ids: [],
                    output_port_ids: ["markers"],
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
                    output_port_ids: [PROVENANCE_PORT_MODELS],
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
                edge("markers", "markers", "markers-viewer", "input"),
                // The one surviving lineage edge: the trainer whose models the
                // classifier serves. Source→experiment and experiment→train are
                // implicit now that the experiment owns the board.
                provEdge("train", PROVENANCE_PORT_MODELS, "classify", PROVENANCE_PORT_MODEL),
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
        id: "imu-adl-session",
        label: "IMU ADL session",
        description:
            "The post-stroke ADL study, ready to run: a workspace, the ADL protocol, and a board wired IMU → combine → export with a calibration readout.",
        workspace: { label: "ADL study" },
        experiment: {
            label: "ADL tasks",
            // The ADL task list as an authorable step protocol. Declared
            // SessionProtocol on this interface but a StepProtocol is equally
            // legitimate (see the Experiment type) — the step editor stores these
            // and `isStepProtocol` discriminates at the read sites.
            protocol: adlStepProtocol() as unknown as SessionProtocol,
        },
        build(sourceStreamId) {
            const graph = baseGraph(
                "IMU ADL session",
                "Pick the participant when you press Record. The combine node bundles the IMU data with the experiment's marker timeline, which is what makes the exported Parquet carry label / label_phase / label_cue_id per row.",
            );
            // ⚠️ Laid out for the state this template LANDS IN, which has the
            // experiment panel open as well as the board library — so the usable
            // canvas is a narrow middle column, not the full width. Spread these
            // out like the other templates and half the board sits behind a panel
            // with its titles clipped, which is not "ready to run".
            graph.nodes = [
                { ...source(sourceStreamId), position: { x: 360, y: 180 } },
                {
                    id: "markers",
                    kind: "markers",
                    label: "Markers",
                    position: { x: 360, y: 560 },
                    input_port_ids: [],
                    output_port_ids: ["markers"],
                },
                // The calibration readout hangs off the raw source: it reads the
                // per-sensor accuracy the device reports, so it must see the
                // device's own frames rather than anything derived.
                {
                    id: "calibration",
                    kind: "viewer",
                    label: "IMU Calibration",
                    position: { x: 700, y: 40 },
                    input_port_ids: ["input"],
                    inline_graph: true,
                    display_mode: "imu_calibration",
                },
                {
                    id: "live",
                    kind: "viewer",
                    label: "Live IMU",
                    position: { x: 700, y: 300 },
                    input_port_ids: ["input"],
                },
                // Data + markers into ONE channel. That bundle IS the join the
                // exporter needs; without it the Parquet comes back unlabelled.
                {
                    id: "combine",
                    kind: "combine",
                    label: "Combine",
                    position: { x: 700, y: 560 },
                    input_port_ids: ["in1", "in2"],
                    output_port_ids: ["data"],
                    output_identifier: `adl-session-combine-${suffix()}`,
                },
                {
                    id: "export",
                    kind: "export",
                    label: "Export",
                    position: { x: 700, y: 800 },
                    input_port_ids: ["in1", "in2"],
                    output_port_ids: [],
                    config: {
                        format: "parquet",
                        label_field: "label",
                        run_index: null,
                    },
                },
            ];
            graph.edges = [
                edge("source", "data", "calibration", "input"),
                edge("source", "data", "live", "input"),
                edge("source", "data", "combine", "in1"),
                edge("markers", "markers", "combine", "in2"),
                edge("combine", "data", "export", "in1"),
            ];
            return graph;
        },
    },
    {
        id: "record-an-experiment",
        label: "Record an experiment",
        description:
            "A finger-counting experiment emitting a marker timeline into a viewer.",
        experiment: {
            label: "Finger counting",
            protocol: { ...FINGER_COUNTING_STARTER_PROTOCOL },
        },
        build() {
            const graph = baseGraph(
                "Record an experiment",
                "The bound experiment cues finger-counting gestures (1–5) and emits a labeled marker timeline; press Record in the Experiment panel, then watch the markers.",
            );
            graph.nodes = [
                {
                    id: "markers",
                    kind: "markers",
                    label: "Markers",
                    position: { x: 120, y: 200 },
                    input_port_ids: [],
                    output_port_ids: ["markers"],
                },
                {
                    id: "viewer",
                    kind: "viewer",
                    label: "Markers",
                    position: { x: 460, y: 200 },
                    input_port_ids: ["input"],
                },
            ];
            graph.edges = [edge("markers", "markers", "viewer", "input")];
            return graph;
        },
    },
];
