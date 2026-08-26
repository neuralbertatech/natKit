import { describe, expect, it } from "vitest";

import { CONVENTION_PROTOCOL, STARTER_TEMPLATES } from "./starterTemplates";
import { ADL_PROTOCOL_ID } from "../AdlExperiment/tasks";

function template(id: string) {
    const found = STARTER_TEMPLATES.find((t) => t.id === id);
    if (!found) {
        throw new Error(`template ${id} not found`);
    }
    return found;
}

describe("every starter template with no stream to bind", () => {
    // ⚠️ THE REGRESSION THIS EXISTS FOR (TEC-NATKIT-66): `stream_id: ""` made the
    // whole board unsavable, because the backend parses stream_id only when the key
    // is PRESENT and then demands a non-negative integer. The board appeared on the
    // canvas, its save was rejected, and the experiment save then failed with
    // "Unknown graph" — pointing at a symptom rather than the cause.
    //
    // The previous tests all called build(null) and passed, because they asserted
    // the graph's SHAPE and an empty stream_id is a legitimate shape. Only the
    // backend had an opinion, and only on a rig that was not streaming.
    for (const template of STARTER_TEMPLATES) {
        it(`omits stream_id rather than sending "" — ${template.id}`, () => {
            const graph = template.build(null);
            for (const node of graph.nodes) {
                if (node.kind !== "stream_source") continue;
                expect(
                    Object.prototype.hasOwnProperty.call(node, "stream_id") &&
                        (node as { stream_id?: string }).stream_id === "",
                ).toBe(false);
            }
        });
    }

    // ⚠️ THE ADL TEMPLATE DELIBERATELY DOES NOT BIND, and this replaces a test
    // that asserted it did. Its eight nodes are PLACEMENTS — Left Hand, Trunk,
    // Base — and binding a passed stream would attach an arbitrary sensor to
    // whichever placement happened to be first. A wrong mapping that looks
    // deliberate is worse than an empty one the operator must fill in, because
    // the empty one is visible and the wrong one is not.
    it("leaves every ADL placement unbound, even when a stream is offered", () => {
        const graph = template("imu-adl-session").build("13793649670644");
        const sources = graph.nodes.filter((n) => n.kind === "stream_source");
        expect(sources).toHaveLength(8);
        for (const node of sources) {
            expect(
                Object.prototype.hasOwnProperty.call(node, "stream_id"),
            ).toBe(false);
        }
    });
});

describe("IMU ADL session template", () => {
    it("is registered and names a workspace", () => {
        const adl = template("imu-adl-session");
        // The workspace is what makes this a study rather than a board: without it
        // the experiment and board land in Unfiled and disappear from the scoped
        // lists the moment the user switches workspace.
        expect(adl.workspace?.label).toBe("ADL study");
    });

    it("carries the ADL protocol, with its cue labels intact", () => {
        const adl = template("imu-adl-session");
        const protocol = adl.experiment?.protocol as unknown as {
            protocol_id: string;
            steps: { kind: string; label?: string }[];
        };
        expect(protocol.protocol_id).toBe(ADL_PROTOCOL_ID);
        // The cue labels ARE the class labels a classifier would learn, so they
        // have to survive the trip through the template.
        const cueLabels = protocol.steps
            .filter((step) => step.kind === "cue")
            .map((step) => step.label);
        expect(cueLabels).toContain("drink_cup");
        expect(cueLabels).toContain("brush_teeth");
    });

    it("gives every cue a visual and a verbal stimulus, both marked as placeholders", () => {
        const adl = template("imu-adl-session");
        const protocol = adl.experiment?.protocol as unknown as {
            steps: {
                kind: string;
                label?: string;
                image_url?: string;
                audio_url?: string;
            }[];
        };
        const cues = protocol.steps.filter((step) => step.kind === "cue");
        expect(cues.length).toBeGreaterThan(0);
        for (const cue of cues) {
            expect(cue.image_url).toBe(`/media/placeholder-${cue.label}.png`);
            expect(cue.audio_url).toBe(`/media/placeholder-${cue.label}.wav`);
        }
        // ⚠️ "placeholder" in the path is the only thing that makes a session
        // recorded against stand-ins detectable from the recorded data alone — the
        // url lands in the marker attributes. If the real assets are ever wired in
        // by editing these paths, this assertion is the reminder to also stop
        // calling them placeholders.
        expect(cues.every((c) => c.image_url?.includes("placeholder-"))).toBe(true);
    });

    it("wires every sensor AND the markers into combine, and combine into export", () => {
        const graph = template("imu-adl-session").build(null);

        const sources = graph.nodes
            .filter((n) => n.kind === "stream_source")
            .map((n) => n.id)
            .sort();
        expect(sources).toHaveLength(8);

        const pairs = graph.edges
            .filter((e) => e.edge_kind !== "provenance")
            .map((e) => `${e.source_node_id}->${e.target_node_id}`);

        // ⚠️ EVERY sensor reaches the combine. Wiring only the first would export
        // one limb out of eight and still produce a file that looks complete.
        for (const id of sources) {
            expect(pairs).toContain(`${id}->combine`);
        }
        // ⚠️ …and the markers with them. That bundle IS the join the exporter
        // needs; drop it and the Parquet comes back with an empty label column,
        // which reads as a successful export.
        expect(pairs).toContain("markers->combine");
        expect(pairs).toContain("combine->export");

        // The calibration and live readouts hang off ONE device's own frames.
        // Pointed at the combine they would see a bundle and report no
        // calibration at all.
        expect(pairs).toContain("source-0->calibration");
        expect(pairs).toContain("source-0->live");

        // ⚠️ The combine must have a port per incoming edge. A fixed in1/in2
        // would silently drop six of the eight sensors.
        const combine = graph.nodes.find((n) => n.id === "combine");
        const ports = (combine as { input_port_ids?: string[] })?.input_port_ids;
        expect(ports).toHaveLength(sources.length + 1);
    });

    it("exports parquet with the label column named", () => {
        const graph = template("imu-adl-session").build(null);
        const exportNode = graph.nodes.find((n) => n.id === "export");
        const config = (exportNode as { config?: Record<string, unknown> })
            ?.config;
        expect(config?.format).toBe("parquet");
        expect(config?.label_field).toBe("label");
    });

    it("shows the calibration readout without needing the inline-graph toggle", () => {
        const graph = template("imu-adl-session").build(null);
        const calibration = graph.nodes.find((n) => n.id === "calibration") as {
            display_mode?: string;
            inline_graph?: boolean;
        };
        // A setup routine whose calibration check is hidden behind a toggle is not
        // a setup routine.
        expect(calibration.display_mode).toBe("imu_calibration");
        expect(calibration.inline_graph).toBe(true);
    });
});

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
