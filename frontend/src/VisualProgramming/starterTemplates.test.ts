import { describe, expect, it } from "vitest";

import { CONVENTION_PROTOCOL, STARTER_TEMPLATES } from "./starterTemplates";

function template(id: string) {
    const found = STARTER_TEMPLATES.find((t) => t.id === id);
    if (!found) {
        throw new Error(`template ${id} not found`);
    }
    return found;
}

describe("Convention EMG Quick-Start template", () => {
    it("is registered", () => {
        expect(
            STARTER_TEMPLATES.some((t) => t.id === "convention-emg-quick-start"),
        ).toBe(true);
    });

    it("binds the source to the passed stream and pre-wires the whole graph", () => {
        const graph = template("convention-emg-quick-start").build("emg-live-1");
        const source = graph.nodes.find((n) => n.id === "source");
        expect(source && "stream_id" in source ? source.stream_id : null).toBe(
            "emg-live-1",
        );

        // No node needs manual adding/wiring: classifier, viewers, markers, and
        // train node are all present.
        const kinds = graph.nodes.map((n) => n.id).sort();
        expect(kinds).toEqual(
            [
                "classify",
                "classify-viewer",
                "markers",
                "markers-viewer",
                "raw-viewer",
                "source",
                "train",
            ].sort(),
        );

        // Source feeds both the raw viewer (exploration) and the classifier;
        // classifier feeds the prediction viewer; markers feed the cue viewer.
        const dataEdgePairs = graph.edges
            .filter((e) => e.edge_kind !== "provenance")
            .map((e) => `${e.source_node_id}->${e.target_node_id}`)
            .sort();
        expect(dataEdgePairs).toEqual(
            [
                "source->raw-viewer",
                "source->classify",
                "classify->classify-viewer",
                "markers->markers-viewer",
            ].sort(),
        );

        // Only train→classify (the model dropdown) survives as a provenance edge.
        // source→experiment and experiment→train were retired: the experiment owns
        // the whole board, so both are implicit in the binding.
        const provEdgePairs = graph.edges
            .filter((e) => e.edge_kind === "provenance")
            .map((e) => `${e.source_node_id}->${e.target_node_id}`)
            .sort();
        expect(provEdgePairs).toEqual(["train->classify"]);
    });

    it("carries the experiment record the board binds (protocol is not on a node)", () => {
        const tpl = template("convention-emg-quick-start");
        expect(tpl.experiment?.label).toBe("Convention EMG");
        expect(tpl.experiment?.protocol.protocol_id).toBe("convention-emg-v1");
        // The canvas holds only a config-less markers source.
        const graph = tpl.build(null);
        const markers = graph.nodes.find((n) => n.id === "markers");
        expect(markers?.kind).toBe("markers");
        expect(markers && "config" in markers).toBe(false);
    });

    it("pre-places emg_gesture_classify with an empty model path (filled after training)", () => {
        const graph = template("convention-emg-quick-start").build(null);
        const classify = graph.nodes.find((n) => n.id === "classify");
        expect(classify?.kind).toBe("transform");
        if (classify?.kind !== "transform") {
            throw new Error("classify node is not a transform");
        }
        expect(classify.transform_kind).toBe("emg_gesture_classify");
        expect(classify.config.model_path).toBe("");
    });

    it("uses the convention protocol including a fist gesture for calibration", () => {
        const protocol = template("convention-emg-quick-start").experiment
            ?.protocol;
        expect(protocol).toEqual(CONVENTION_PROTOCOL);
        expect(protocol?.protocol_id).toBe("convention-emg-v1");
        // fist doubles as the rest-calibration active gesture.
        expect(protocol?.classes).toContain("fist");
        expect(protocol?.rest_class).toBe("rest");
    });

    it("train node defaults to LDA with fist as the active/calibration gesture", () => {
        const graph = template("convention-emg-quick-start").build(null);
        const train = graph.nodes.find((n) => n.id === "train");
        const config =
            train && "config" in train
                ? (train.config as {
                      families: string[];
                      active_gesture: string;
                      rest_gesture: string;
                  })
                : undefined;
        expect(config?.families).toEqual(["lda"]);
        expect(config?.active_gesture).toBe("fist");
        expect(config?.rest_gesture).toBe("rest");
    });
});
