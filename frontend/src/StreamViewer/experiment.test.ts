import { describe, it, expect } from "vitest";
import {
    buildCueSchedule,
    buildCueScheduleForProtocol,
    EMG_GESTURE_PROTOCOL,
    type SessionProtocol,
} from "./experiment";

// A generic, non-EMG classification protocol — proves the cue engine has no
// gesture-specific hardcoding.
const DIRECTION_PROTOCOL: SessionProtocol = {
    protocol_id: "cursor-direction-v1",
    label: "Cursor direction",
    classes: ["left", "right", "up"],
    rest_class: "none",
    repetitions: 2,
    hold_s: 2,
    rest_s: 1,
    lead_in_s: 1,
    tail_rest_s: 1,
    seed: 7,
};

describe("buildCueScheduleForProtocol", () => {
    const schedule = buildCueScheduleForProtocol(DIRECTION_PROTOCOL);

    it("emits one hold cue per class per repetition", () => {
        const holds = schedule.filter((cue) => cue.phase === "hold");
        expect(holds.length).toBe(
            DIRECTION_PROTOCOL.classes.length * DIRECTION_PROTOCOL.repetitions,
        );
    });

    it("draws hold-cue labels only from the protocol's class vocabulary", () => {
        const holds = schedule.filter((cue) => cue.phase === "hold");
        for (const cue of holds) {
            expect(DIRECTION_PROTOCOL.classes).toContain(cue.gesture);
        }
    });

    it("uses the protocol's rest_class for filler cues, not a hardcoded 'rest'", () => {
        const fillers = schedule.filter((cue) => cue.phase !== "hold");
        expect(fillers.length).toBeGreaterThan(0);
        for (const cue of fillers) {
            expect(cue.gesture).toBe("none");
        }
        // The gesture-only literals must not leak into a non-gesture protocol.
        expect(schedule.some((cue) => cue.gesture === "rest")).toBe(false);
        expect(schedule.some((cue) => cue.gesture === "fist")).toBe(false);
    });

    it("produces a monotonically increasing, contiguous timeline", () => {
        let prevEnd = 0;
        for (const cue of schedule) {
            expect(cue.end_offset_ms).toBeGreaterThan(cue.start_offset_ms);
            expect(cue.start_offset_ms).toBe(prevEnd);
            prevEnd = cue.end_offset_ms;
        }
    });
});

describe("EMG_GESTURE_PROTOCOL backward compatibility", () => {
    it("reproduces the built-in gesture schedule with 'rest' fillers", () => {
        const schedule = buildCueScheduleForProtocol(EMG_GESTURE_PROTOCOL);
        const holds = schedule.filter((cue) => cue.phase === "hold");
        expect(holds.length).toBe(6 * 3); // 6 gestures x 3 reps
        const fillers = schedule.filter((cue) => cue.phase !== "hold");
        for (const cue of fillers) {
            expect(cue.gesture).toBe("rest");
        }
    });

    it("defaults the filler class to 'rest' when restClass is omitted", () => {
        const schedule = buildCueSchedule({
            gestures: ["a", "b"],
            repetitions: 1,
            holdS: 1,
            restS: 1,
            leadInS: 1,
            tailRestS: 1,
            seed: 1,
        });
        const leadIn = schedule.find((cue) => cue.phase === "lead_in");
        expect(leadIn?.gesture).toBe("rest");
    });
});
