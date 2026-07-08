// Built-in composite templates that ship with the app, independent of any
// user's localStorage library (see compositeLibrary.ts, which merges these
// in). Each entry is a plain CompositeTemplate literal — no runtime graph
// authoring involved.
import type { CompositeTemplate } from "./composites";

const SQRT_HALF = Math.SQRT1_2;

// Assumes a 1000 Hz EMG sample rate: 200ms windows (window_samples=200) with
// 50% overlap (step_samples=100), per the 150-250ms/50%-overlap guidance for
// gesture-recognition EMG pipelines. If your acquisition hardware samples at
// a different rate, ungroup this composite and edit the "Sliding window"
// node's window_samples/step_samples to match (window_samples = rate_hz *
// window_seconds, step_samples = window_samples / 2 for 50% overlap).
export const EMG_PREPROCESSING_COMPOSITE: CompositeTemplate = {
    composite_version: 1,
    composite_id: "composite-default-emg-preprocessing",
    label: "EMG Preprocessing",
    description:
        "3-channel sEMG pipeline: bandpass -> notch -> detrend -> rectify -> " +
        "windowing -> linear envelope -> Hudgins-style per-window features " +
        "(MAV, RMS, WL, ZC, SSC, AR coefficients) -> concatenated feature " +
        "vector. Assumes a 1000 Hz sample rate for the 200ms/50%-overlap " +
        "sliding window; ungroup and edit if your hardware samples at a " +
        "different rate. Feed the 'Feature vector' output into a standalone " +
        "LDA Classify transform node (add it from the node palette) to " +
        "classify gestures — it requires a trained LDA model file (see " +
        "natVR/src/natvr/model.py's LdaModel.save_json) set as its model_path.",
    nodes: [
        {
            id: "bandpass",
            kind: "transform",
            label: "Band-pass IIR",
            position: { x: 0, y: 0 },
            transform_kind: "bandpass_iir",
            config: {
                low_cutoff_hz: 20,
                high_cutoff_hz: 450,
                iir_method: "butterworth",
                butterworth_order: 4,
                biquad_q: SQRT_HALF,
            },
            output_identifier: "bandpass",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "notch",
            kind: "transform",
            label: "Notch IIR",
            position: { x: 260, y: 0 },
            transform_kind: "notch_iir",
            config: {
                notch_hz: 60,
                notch_q: 30,
                harmonic_count: 0,
            },
            output_identifier: "notch",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "detrend",
            kind: "transform",
            label: "Detrend (High-pass IIR)",
            position: { x: 520, y: 0 },
            transform_kind: "highpass_iir",
            config: {
                cutoff_hz: 5,
                iir_method: "butterworth",
                butterworth_order: 2,
                biquad_q: SQRT_HALF,
            },
            output_identifier: "detrend",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "rectify",
            kind: "transform",
            label: "Full-wave Rectify",
            position: { x: 780, y: 0 },
            transform_kind: "rectify",
            config: {},
            output_identifier: "rectify",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "window",
            kind: "transform",
            label: "Sliding Window",
            position: { x: 1040, y: 0 },
            transform_kind: "sliding_window",
            config: {
                window_samples: 200,
                step_samples: 100,
            },
            output_identifier: "window",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "envelope",
            kind: "transform",
            label: "Linear Envelope",
            position: { x: 1300, y: 0 },
            transform_kind: "lowpass_envelope",
            config: {
                cutoff_hz: 5,
            },
            output_identifier: "envelope",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_mav",
            kind: "transform",
            label: "MAV",
            position: { x: 1560, y: -300 },
            transform_kind: "mav",
            config: {},
            output_identifier: "feat-mav",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_rms",
            kind: "transform",
            label: "RMS",
            position: { x: 1560, y: -180 },
            transform_kind: "rms",
            config: {},
            output_identifier: "feat-rms",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_wl",
            kind: "transform",
            label: "Waveform Length",
            position: { x: 1560, y: -60 },
            transform_kind: "wl",
            config: {},
            output_identifier: "feat-wl",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_zc",
            kind: "transform",
            label: "Zero Crossings",
            position: { x: 1560, y: 60 },
            transform_kind: "zc",
            config: {
                zc_threshold: 0,
            },
            output_identifier: "feat-zc",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_ssc",
            kind: "transform",
            label: "Slope Sign Changes",
            position: { x: 1560, y: 180 },
            transform_kind: "ssc",
            config: {
                ssc_threshold: 0,
            },
            output_identifier: "feat-ssc",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "feat_ar",
            kind: "transform",
            label: "AR Coefficients",
            position: { x: 1560, y: 300 },
            transform_kind: "ar_coeffs",
            config: {
                ar_order: 4,
            },
            output_identifier: "feat-ar",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        {
            id: "combine",
            kind: "combine",
            label: "Combine Features",
            position: { x: 1820, y: 0 },
            input_port_ids: ["in1", "in2", "in3", "in4", "in5", "in6"],
            output_port_ids: ["data"],
            output_identifier: "combine",
        },
    ],
    edges: [
        edge("bandpass", "output", "notch", "input"),
        edge("notch", "output", "detrend", "input"),
        edge("detrend", "output", "rectify", "input"),
        edge("rectify", "output", "window", "input"),
        edge("window", "output", "envelope", "input"),
        edge("envelope", "output", "feat_mav", "input"),
        edge("envelope", "output", "feat_rms", "input"),
        edge("envelope", "output", "feat_wl", "input"),
        edge("envelope", "output", "feat_zc", "input"),
        edge("envelope", "output", "feat_ssc", "input"),
        edge("envelope", "output", "feat_ar", "input"),
        edge("feat_mav", "output", "combine", "in1"),
        edge("feat_rms", "output", "combine", "in2"),
        edge("feat_wl", "output", "combine", "in3"),
        edge("feat_zc", "output", "combine", "in4"),
        edge("feat_ssc", "output", "combine", "in5"),
        edge("feat_ar", "output", "combine", "in6"),
    ],
    inputs: [
        {
            port_id: "in1",
            label: "Raw EMG (3ch)",
            internal_node_id: "bandpass",
            internal_port: "input",
        },
    ],
    outputs: [
        {
            port_id: "out1",
            label: "Feature vector",
            internal_node_id: "combine",
            internal_port: "data",
        },
        {
            port_id: "out2",
            label: "Linear envelope",
            internal_node_id: "envelope",
            internal_port: "output",
        },
    ],
};

// Destructures a concatenated feature vector (e.g. the "Feature vector" output
// of EMG Preprocessing) into one sub-stream per Hudgins-style feature family.
// A passthrough "all" Select acts as the fan-out hub (a composite input maps to
// a single internal node, so the hub is what lets one source feed every
// per-family Select), and each family Select keeps the channels whose label
// contains that family's suffix. Feed any output into its own viewer, or into a
// downstream transform, to work with just that feature family.
const SPLIT_FAMILIES: { id: string; label: string; match: string }[] = [
    { id: "sel_mav", label: "MAV", match: "mav" },
    { id: "sel_rms", label: "RMS", match: "rms" },
    { id: "sel_wl", label: "Waveform Length", match: "wl" },
    { id: "sel_zc", label: "Zero Crossings", match: "zc" },
    { id: "sel_ssc", label: "Slope Sign Changes", match: "ssc" },
    { id: "sel_ar", label: "AR Coefficients", match: "ar" },
];

export const FEATURE_FAMILY_SPLIT_COMPOSITE: CompositeTemplate = {
    composite_version: 1,
    composite_id: "composite-default-feature-family-split",
    label: "Split by Feature Family",
    description:
        "Destructures a concatenated feature vector into six sub-streams — MAV, " +
        "RMS, WL, ZC, SSC and AR coefficients — using Select / Split channels " +
        "nodes that match each feature's label suffix. Attach a viewer to any " +
        "output to inspect one family, or route it into a downstream transform. " +
        "Assumes the standard EMG Preprocessing label scheme; ungroup and edit " +
        "the Select nodes' 'selection' if your labels differ.",
    nodes: [
        {
            id: "hub",
            kind: "transform",
            label: "Feature vector in",
            position: { x: 0, y: 0 },
            transform_kind: "channel_select",
            config: { select_mode: "all", selection: "all" },
            output_identifier: "split-hub",
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        },
        ...SPLIT_FAMILIES.map((family, index) => ({
            id: family.id,
            kind: "transform" as const,
            label: family.label,
            position: { x: 320, y: (index - 2.5) * 130 },
            transform_kind: "channel_select" as const,
            config: { select_mode: "label", selection: family.match },
            output_identifier: `split-${family.match}`,
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        })),
    ],
    edges: SPLIT_FAMILIES.map((family) =>
        edge("hub", "output", family.id, "input"),
    ),
    inputs: [
        {
            port_id: "in1",
            label: "Feature vector",
            internal_node_id: "hub",
            internal_port: "input",
        },
    ],
    outputs: SPLIT_FAMILIES.map((family, index) => ({
        port_id: `out${index + 1}`,
        label: family.label,
        internal_node_id: family.id,
        internal_port: "output",
    })),
};

function edge(
    sourceNodeId: string,
    sourcePort: string,
    targetNodeId: string,
    targetPort: string,
) {
    return {
        id: `${sourceNodeId}.${sourcePort}->${targetNodeId}.${targetPort}`,
        source_node_id: sourceNodeId,
        source_port: sourcePort,
        target_node_id: targetNodeId,
        target_port: targetPort,
    };
}

export const DEFAULT_COMPOSITES: CompositeTemplate[] = [
    EMG_PREPROCESSING_COMPOSITE,
    FEATURE_FAMILY_SPLIT_COMPOSITE,
];
