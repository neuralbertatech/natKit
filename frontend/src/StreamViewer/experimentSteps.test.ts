import { describe, expect, it } from "vitest";
import {
    compileStepProtocol,
    exampleStepProtocol,
    protocolClasses,
    resolveScheduleWaits,
    stepProtocolDurationMs,
    stepsFromLegacyProtocol,
    type StepProtocol,
} from "./experimentSteps";
import { buildCueMarkerPayloads, buildCueSchedule } from "./experiment";

function protocol(steps: StepProtocol["steps"]): StepProtocol {
    return {
        protocol_version: 1,
        protocol_id: "p",
        label: "p",
        rest_class: "rest",
        steps,
    };
}

describe("compileStepProtocol", () => {
    it("lays steps end to end and carries the author's text as the prompt", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "a", kind: "instruction", text: "Welcome", duration_s: 5 },
                { id: "b", kind: "cue", label: "fist", text: "Squeeze", duration_s: 2 },
                { id: "c", kind: "rest", text: "Relax", duration_s: 1 },
            ]),
        );
        expect(schedule.map((c) => [c.phase, c.prompt, c.start_offset_ms, c.end_offset_ms]))
            .toEqual([
                ["instruction", "Welcome", 0, 5000],
                ["hold", "Squeeze", 5000, 7000],
                ["rest", "Relax", 7000, 8000],
            ]);
        // The class label is what a trainer keys on, separate from display text.
        expect(schedule[1].gesture).toBe("fist");
        expect(schedule[2].gesture).toBe("rest");
    });

    it("expands a repeat group and advances rep_index per pass", () => {
        const schedule = compileStepProtocol(
            protocol([
                {
                    id: "r",
                    kind: "repeat",
                    times: 3,
                    steps: [{ id: "c", kind: "cue", label: "open", duration_s: 1 }],
                },
            ]),
        );
        expect(schedule).toHaveLength(3);
        expect(schedule.map((c) => c.rep_index)).toEqual([0, 1, 2]);
        expect(schedule.map((c) => c.start_offset_ms)).toEqual([0, 1000, 2000]);
    });

    it("shuffles a repeat group deterministically for a given seed", () => {
        const build = (seed: number) =>
            compileStepProtocol(
                protocol([
                    {
                        id: "r",
                        kind: "repeat",
                        times: 4,
                        shuffle: true,
                        seed,
                        steps: [
                            { id: "1", kind: "cue", label: "a", duration_s: 1 },
                            { id: "2", kind: "cue", label: "b", duration_s: 1 },
                            { id: "3", kind: "cue", label: "c", duration_s: 1 },
                        ],
                    },
                ]),
            ).map((c) => c.gesture);
        expect(build(7)).toEqual(build(7));
        // A different seed should generally reorder; assert it is still the same
        // multiset so shuffling can never drop or duplicate a cue.
        const sorted = (labels: string[]) => [...labels].sort().join("");
        expect(sorted(build(7))).toEqual(sorted(build(8)));
    });

    it("marks every cue produced inside a tutorial block", () => {
        const schedule = compileStepProtocol(
            protocol([
                {
                    id: "t",
                    kind: "repeat",
                    times: 2,
                    tutorial: true,
                    steps: [{ id: "c", kind: "cue", label: "fist", duration_s: 1 }],
                },
                { id: "m", kind: "cue", label: "fist", duration_s: 1 },
            ]),
        );
        expect(schedule.map((c) => c.tutorial === true)).toEqual([true, true, false]);
    });

    it("excludes tutorial-only labels from the protocol's class list", () => {
        const p = protocol([
            {
                id: "t",
                kind: "repeat",
                times: 1,
                tutorial: true,
                steps: [{ id: "c1", kind: "cue", label: "practice_only", duration_s: 1 }],
            },
            { id: "c2", kind: "cue", label: "fist", duration_s: 1 },
            { id: "c3", kind: "cue", label: "fist", duration_s: 1 },
        ]);
        expect(protocolClasses(p)).toEqual(["fist"]);
    });

    it("emits a wait as a zero-length barrier flagged for input", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "a", kind: "cue", label: "fist", duration_s: 2 },
                { id: "w", kind: "wait", text: "Ready?", continue_label: "Go" },
                { id: "b", kind: "cue", label: "open", duration_s: 2 },
            ]),
        );
        expect(schedule[1]).toMatchObject({
            phase: "wait",
            wait_for_input: true,
            continue_label: "Go",
            start_offset_ms: 2000,
            end_offset_ms: 2000,
        });
        // Nothing after the wait is displaced until it is released.
        expect(schedule[2].start_offset_ms).toBe(2000);
    });
});

describe("resolveScheduleWaits", () => {
    it("shifts everything after a wait by how long it actually held", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "a", kind: "cue", label: "fist", duration_s: 2 },
                { id: "w", kind: "wait", text: "Ready?" },
                { id: "b", kind: "cue", label: "open", duration_s: 2 },
            ]),
        );
        const waitCueId = schedule[1].cue_id;
        const resolved = resolveScheduleWaits(schedule, { [waitCueId]: 9000 });
        expect(resolved[0]).toMatchObject({ start_offset_ms: 0, end_offset_ms: 2000 });
        expect(resolved[1]).toMatchObject({ start_offset_ms: 2000, end_offset_ms: 11000 });
        expect(resolved[2]).toMatchObject({ start_offset_ms: 11000, end_offset_ms: 13000 });
    });

    it("accumulates across several waits", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "w1", kind: "wait", text: "one" },
                { id: "a", kind: "cue", label: "fist", duration_s: 1 },
                { id: "w2", kind: "wait", text: "two" },
                { id: "b", kind: "cue", label: "open", duration_s: 1 },
            ]),
        );
        const resolved = resolveScheduleWaits(schedule, {
            [schedule[0].cue_id]: 3000,
            [schedule[2].cue_id]: 5000,
        });
        expect(resolved.map((c) => c.start_offset_ms)).toEqual([0, 3000, 4000, 9000]);
        expect(resolved.at(-1)!.end_offset_ms).toBe(10000);
    });

    it("treats an unreleased wait as zero so a cancelled run still resolves", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "w", kind: "wait", text: "never released" },
                { id: "a", kind: "cue", label: "fist", duration_s: 2 },
            ]),
        );
        const resolved = resolveScheduleWaits(schedule, {});
        expect(resolved.map((c) => c.start_offset_ms)).toEqual([0, 0]);
    });

    it("keeps marker timestamps consistent with the resolved timeline", () => {
        const schedule = compileStepProtocol(
            protocol([
                { id: "w", kind: "wait", text: "Ready?" },
                { id: "a", kind: "cue", label: "fist", duration_s: 2 },
            ]),
        );
        const startedAtUs = 1_000_000_000;
        const resolved = resolveScheduleWaits(schedule, { [schedule[0].cue_id]: 4000 });
        const markers = buildCueMarkerPayloads({
            sessionId: "s",
            cues: resolved,
            sessionStartedAtUs: startedAtUs,
        });
        // The cue after a 4s wait must be reported 4s in, not at t=0.
        const cueStart = markers.find(
            (m) => m.attributes.phase === "hold" && m.event === "start",
        );
        expect(cueStart?.emitted_at_us).toBe(startedAtUs + 4_000_000);
    });
});

describe("stepsFromLegacyProtocol", () => {
    it("produces the same timeline the fixed builder produces", () => {
        const legacy = {
            protocol_id: "finger",
            label: "Finger counting",
            classes: ["count_1", "count_2"],
            rest_class: "rest",
            repetitions: 2,
            hold_s: 2,
            rest_s: 1,
            lead_in_s: 3,
            tail_rest_s: 2,
            seed: 1,
        };
        const fromSteps = compileStepProtocol(stepsFromLegacyProtocol(legacy));
        const fromFixed = buildCueSchedule({
            gestures: legacy.classes,
            repetitions: legacy.repetitions,
            holdS: legacy.hold_s,
            restS: legacy.rest_s,
            leadInS: legacy.lead_in_s,
            tailRestS: legacy.tail_rest_s,
            seed: legacy.seed,
            restClass: legacy.rest_class,
        });
        // Same total length and the same number of labelled holds — the two shapes
        // describe the same session even though phases are named differently for
        // the lead-in (instruction vs lead_in).
        expect(stepProtocolDurationMs(fromSteps)).toBe(
            stepProtocolDurationMs(fromFixed),
        );
        const holds = (s: typeof fromSteps) => s.filter((c) => c.phase === "hold");
        expect(holds(fromSteps)).toHaveLength(holds(fromFixed).length);
        expect(new Set(holds(fromSteps).map((c) => c.gesture))).toEqual(
            new Set(holds(fromFixed).map((c) => c.gesture)),
        );
    });

    it("round-trips a protocol with no lead-in or tail", () => {
        const steps = stepsFromLegacyProtocol({
            classes: ["a"],
            repetitions: 1,
            hold_s: 1,
            rest_s: 0,
            lead_in_s: 0,
            tail_rest_s: 0,
        });
        const schedule = compileStepProtocol(steps);
        expect(schedule).toHaveLength(1);
        expect(schedule[0]).toMatchObject({ phase: "hold", gesture: "a" });
    });
});

describe("exampleStepProtocol", () => {
    it("demonstrates a tutorial, a wait barrier and a real block", () => {
        const schedule = compileStepProtocol(exampleStepProtocol());
        expect(schedule.some((c) => c.tutorial === true)).toBe(true);
        expect(schedule.some((c) => c.wait_for_input === true)).toBe(true);
        // Real (non-tutorial) holds exist and come after the wait.
        const waitAt = schedule.findIndex((c) => c.wait_for_input);
        const realHolds = schedule.filter(
            (c) => c.phase === "hold" && !c.tutorial,
        );
        expect(realHolds.length).toBeGreaterThan(0);
        expect(schedule.indexOf(realHolds[0])).toBeGreaterThan(waitAt);
        expect(protocolClasses(exampleStepProtocol())).toEqual(["fist"]);
    });
});
