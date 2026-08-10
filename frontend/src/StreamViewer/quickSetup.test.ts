import { describe, expect, it } from "vitest";
import {
    compileQuickSetupSteps,
    defaultQuickSetupRecipe,
    labelFromFilename,
    quickSetupBlockedReason,
    recipeClasses,
    type QuickSetupRecipe,
} from "./quickSetup";
import {
    compileStepProtocol,
    protocolClasses,
    type StepProtocol,
} from "./experimentSteps";

function recipe(patch: Partial<QuickSetupRecipe> = {}): QuickSetupRecipe {
    return {
        ...defaultQuickSetupRecipe("image_cues"),
        cues: [{ label: "fist" }, { label: "open" }],
        ...patch,
    };
}

/** Wrap generated steps the way the designer stores them. */
function asProtocol(r: QuickSetupRecipe): StepProtocol {
    return {
        protocol_version: 1,
        protocol_id: "quick",
        label: "Quick",
        rest_class: "rest",
        seed: 1,
        steps: compileQuickSetupSteps(r),
    };
}

describe("labelFromFilename", () => {
    it("turns a filename into a usable class label", () => {
        expect(labelFromFilename("Fist Closed.PNG")).toBe("fist_closed");
        expect(labelFromFilename("count-1.jpg")).toBe("count_1");
        expect(labelFromFilename("thumbs_up.jpeg")).toBe("thumbs_up");
    });

    it("never returns an empty label", () => {
        expect(labelFromFilename(".png")).toBe("cue");
        expect(labelFromFilename("___.png")).toBe("cue");
    });
});

describe("compileQuickSetupSteps", () => {
    it("builds get-ready, practice, gate and main block in that order", () => {
        const steps = compileQuickSetupSteps(recipe());
        expect(steps.map((s) => [s.kind, s.id])).toEqual([
            ["instruction", "quick-lead-in"],
            ["repeat", "quick-practice"],
            ["instruction", "quick-ready"],
            ["repeat", "quick-main"],
        ]);
        // Practice is rehearsal, so it precedes the ready gate.
        expect(steps.findIndex((s) => s.id === "quick-practice")).toBeLessThan(
            steps.findIndex((s) => s.id === "quick-ready"),
        );
    });

    it("omits each optional part when its knob is off", () => {
        const steps = compileQuickSetupSteps(
            recipe({ lead_in_s: 0, practice_pass: false, wait_for_ready: false }),
        );
        expect(steps.map((s) => s.id)).toEqual(["quick-main"]);
    });

    it("expresses cue/rest alternation with interleave, not rest rows", () => {
        const steps = compileQuickSetupSteps(recipe({ rest_s: 1.5 }));
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        // N cue rows, not 2N — the rests are compiled in.
        expect(main.steps.every((s) => s.kind === "cue")).toBe(true);
        expect(main.steps).toHaveLength(2);
        expect(main.interleave_rest).toEqual({ duration_s: 1.5 });
    });

    it("drops the interleaved rest when rest time and jitter are both zero", () => {
        const steps = compileQuickSetupSteps(recipe({ rest_s: 0 }));
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main.interleave_rest).toBeUndefined();
    });

    it("carries rest jitter through so cue onsets can't be anticipated", () => {
        const steps = compileQuickSetupSteps(
            recipe({ rest_s: 2, rest_jitter_s: 0.5 }),
        );
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main.interleave_rest).toEqual({ duration_s: 2, jitter_s: 0.5 });
    });

    it("stores the shuffle seed so a shuffled block is reproducible", () => {
        const steps = compileQuickSetupSteps(recipe({ shuffle: true, seed: 99 }));
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main).toMatchObject({ shuffle: true, seed: 99 });
    });

    it("does not set a seed when shuffle is off", () => {
        const steps = compileQuickSetupSteps(recipe({ shuffle: false }));
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main.shuffle).toBeUndefined();
        expect(main.seed).toBeUndefined();
    });

    it("regenerating an unchanged recipe produces an identical protocol", () => {
        // Ids are positional, not generated, so the steps must be stable.
        expect(compileQuickSetupSteps(recipe())).toEqual(
            compileQuickSetupSteps(recipe()),
        );
    });

    it("skips blank labels and passes media onto the cues", () => {
        const steps = compileQuickSetupSteps(
            recipe({
                cues: [
                    { label: "  ", image_url: "/api/media/ignored" },
                    {
                        label: "fist",
                        image_url: "/api/media/a",
                        image_name: "fist.png",
                    },
                ],
            }),
        );
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main.steps).toHaveLength(1);
        expect(main.steps[0]).toMatchObject({
            label: "fist",
            image_url: "/api/media/a",
            image_name: "fist.png",
        });
    });

    it("shows the author's own text when given, and the label otherwise", () => {
        const steps = compileQuickSetupSteps(
            recipe({ cues: [{ label: "fist", text: "Squeeze hard" }] }),
        );
        const main = steps.find((s) => s.id === "quick-main");
        if (main?.kind !== "repeat") throw new Error("expected a repeat group");
        expect(main.steps[0]).toMatchObject({
            label: "fist",
            text: "Squeeze hard",
        });
    });
});

describe("a generated protocol behaves like a hand-authored one", () => {
    it("compiles to a runnable schedule with the expected cue count", () => {
        // 2 classes x 3 rounds = 6 real cues, plus 2 practice cues.
        const schedule = compileStepProtocol(asProtocol(recipe()));
        const holds = schedule.filter((c) => c.phase === "hold");
        expect(holds.filter((c) => !c.tutorial)).toHaveLength(6);
        expect(holds.filter((c) => c.tutorial)).toHaveLength(2);
    });

    it("keeps practice out of the trained class list", () => {
        const protocol = asProtocol(
            recipe({ cues: [{ label: "fist" }, { label: "open" }] }),
        );
        expect(protocolClasses(protocol)).toEqual(["fist", "open"]);
    });

    it("holds at the ready gate as a zero-length barrier", () => {
        const schedule = compileStepProtocol(asProtocol(recipe()));
        const gate = schedule.find((c) => c.wait_for_input);
        expect(gate).toBeDefined();
        expect(gate?.end_offset_ms).toBe(gate?.start_offset_ms);
        expect(gate?.continue_label).toBe("I'm ready");
    });

    it("is reproducible: the same recipe yields the same schedule", () => {
        expect(compileStepProtocol(asProtocol(recipe()))).toEqual(
            compileStepProtocol(asProtocol(recipe())),
        );
    });
});

describe("quickSetupBlockedReason", () => {
    it("requires at least one class, worded for the template", () => {
        expect(quickSetupBlockedReason(recipe({ cues: [] }))).toMatch(/image/);
        expect(
            quickSetupBlockedReason(
                recipe({ cues: [], template: "gesture_list" }),
            ),
        ).toMatch(/class/);
    });

    it("rejects a zero hold and duplicate labels", () => {
        expect(quickSetupBlockedReason(recipe({ hold_s: 0 }))).toMatch(/Hold/);
        expect(
            quickSetupBlockedReason(
                recipe({ cues: [{ label: "fist" }, { label: "fist" }] }),
            ),
        ).toMatch(/share a class label/);
    });

    it("passes a usable recipe", () => {
        expect(quickSetupBlockedReason(recipe())).toBeNull();
    });
});

describe("recipeClasses", () => {
    it("lists distinct labels in order, ignoring blanks", () => {
        expect(
            recipeClasses(
                recipe({
                    cues: [
                        { label: "b" },
                        { label: " " },
                        { label: "a" },
                        { label: "b" },
                    ],
                }),
            ),
        ).toEqual(["b", "a"]);
    });
});
