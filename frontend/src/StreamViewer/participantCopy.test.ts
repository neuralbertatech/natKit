import { describe, expect, it } from "vitest";
import {
    DEFAULT_PARTICIPANT_COPY,
    instructionForPhase,
    participantCopyOf,
    resolveParticipantCopy,
} from "./participantCopy";

describe("resolveParticipantCopy", () => {
    // ⚠️ The line the ticket is really about. A protocol that says nothing must
    // not inherit "relax your hand", because a trunk task is not a hand.
    it("defaults to wording that names no body part", () => {
        const copy = resolveParticipantCopy(undefined);
        expect(copy.restInstruction).toBe("Return to a comfortable resting position");
        expect(copy.restInstruction).not.toMatch(/hand|arm|shoulder|wrist/i);
        expect(copy.cueInstruction).not.toMatch(/hand|arm|shoulder|wrist/i);
    });

    it("defaults away from EMG vocabulary", () => {
        const copy = resolveParticipantCopy(null);
        expect(copy.cueNoun).toBe("task");
        expect(copy.cueInstruction).not.toMatch(/gesture|contraction/i);
    });

    it("lets a protocol have its own words back", () => {
        const copy = resolveParticipantCopy({
            cue_noun: "gesture",
            cue_noun_plural: "gestures",
            cue_instruction: "Make and hold this gesture",
            rest_instruction: "Relax your hand fully",
        });
        expect(copy.cueNoun).toBe("gesture");
        expect(copy.cueInstruction).toBe("Make and hold this gesture");
        expect(copy.restInstruction).toBe("Relax your hand fully");
    });

    // Per field, not per object: a partially authored protocol must not lose its
    // own noun, nor end up with a blank instruction.
    it("fills only what is missing", () => {
        const copy = resolveParticipantCopy({ cue_noun: "activity", cue_noun_plural: "activities" });
        expect(copy.cueNoun).toBe("activity");
        expect(copy.cueNounPlural).toBe("activities");
        expect(copy.cueInstruction).toBe(DEFAULT_PARTICIPANT_COPY.cueInstruction);
        expect(copy.restInstruction).toBe(DEFAULT_PARTICIPANT_COPY.restInstruction);
    });

    // Blank and whitespace are how an empty text input arrives, and a blank line
    // shown to a participant is worse than the default one.
    it("treats blank and whitespace as absent", () => {
        const copy = resolveParticipantCopy({
            cue_noun: "",
            rest_instruction: "   ",
            cue_instruction: "\n",
        });
        expect(copy.cueNoun).toBe(DEFAULT_PARTICIPANT_COPY.cueNoun);
        expect(copy.restInstruction).toBe(DEFAULT_PARTICIPANT_COPY.restInstruction);
        expect(copy.cueInstruction).toBe(DEFAULT_PARTICIPANT_COPY.cueInstruction);
    });

    // ⚠️ Never `${noun}s`: that is how "activitys" reaches a participant's screen.
    it("does not guess a plural from a singular", () => {
        const copy = resolveParticipantCopy({ cue_noun: "activity" });
        expect(copy.cueNounPlural).toBe(DEFAULT_PARTICIPANT_COPY.cueNounPlural);
        expect(copy.cueNounPlural).not.toBe("activitys");
    });

    it("trims what it keeps", () => {
        expect(resolveParticipantCopy({ cue_noun: "  gesture  " }).cueNoun).toBe("gesture");
    });
});

describe("participantCopyOf", () => {
    it("reads the field off either protocol shape", () => {
        expect(
            participantCopyOf({ steps: [], participant_copy: { cue_noun: "activity" } }).cueNoun,
        ).toBe("activity");
        expect(
            participantCopyOf({ classes: [], participant_copy: { cue_noun: "gesture" } }).cueNoun,
        ).toBe("gesture");
    });

    it("survives a null, a string and a protocol with no copy at all", () => {
        expect(participantCopyOf(null).cueNoun).toBe(DEFAULT_PARTICIPANT_COPY.cueNoun);
        expect(participantCopyOf("nonsense").cueNoun).toBe(DEFAULT_PARTICIPANT_COPY.cueNoun);
        expect(participantCopyOf({ steps: [] }).cueNoun).toBe(DEFAULT_PARTICIPANT_COPY.cueNoun);
    });
});

describe("instructionForPhase", () => {
    const adl = resolveParticipantCopy({
        cue_noun: "activity",
        cue_noun_plural: "activities",
        cue_instruction: "Perform this activity",
        rest_instruction: "Return to a comfortable resting position",
    });
    const emg = resolveParticipantCopy({
        cue_noun: "gesture",
        cue_noun_plural: "gestures",
        cue_instruction: "Make and hold this gesture",
        rest_instruction: "Relax your hand",
    });

    // ⚠️ The exact strings a post-stroke participant reads at full size during a
    // recorded ADL run. None of them may name a body part.
    it("gives the ADL protocol body-part-free wording in every phase", () => {
        for (const phase of ["lead_in", "rest", "tail_rest", "hold", "wait"]) {
            expect(instructionForPhase(phase, false, adl)).not.toMatch(
                /hand|arm|wrist|shoulder|finger/i,
            );
        }
        expect(instructionForPhase("lead_in", false, adl)).toBe(
            "Get ready — return to a comfortable resting position",
        );
        expect(instructionForPhase("rest", false, adl)).toBe(
            "Return to a comfortable resting position",
        );
        expect(instructionForPhase("tail_rest", false, adl)).toBe(
            "All done — return to a comfortable resting position",
        );
        expect(instructionForPhase("hold", false, adl)).toBe("Perform this activity");
    });

    // The other half of the fix: the EMG study keeps the words it was written
    // for, so this is not a defect moved rather than removed.
    it("leaves the EMG protocol saying what it always said", () => {
        expect(instructionForPhase("hold", false, emg)).toBe("Make and hold this gesture");
        expect(instructionForPhase("rest", false, emg)).toBe("Relax your hand");
        expect(instructionForPhase("lead_in", false, emg)).toBe("Get ready — relax your hand");
    });

    it("marks a tutorial cue as not kept, whatever the vocabulary", () => {
        expect(instructionForPhase("hold", true, adl)).toContain("not kept for training");
        expect(instructionForPhase("hold", true, emg)).toContain("not kept for training");
    });

    // An instruction step's prompt IS the author's words; a second line above it
    // would be the component talking over them.
    it("says nothing over an author's own instruction step", () => {
        expect(instructionForPhase("instruction", false, adl)).toBe("");
    });

    it("falls through to the cue instruction for an unknown phase", () => {
        expect(instructionForPhase("something_new", false, adl)).toBe("Perform this activity");
    });
});
