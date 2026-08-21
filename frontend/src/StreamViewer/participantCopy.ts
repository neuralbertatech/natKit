// The words a participant is shown, per protocol.
//
// ⚠️ Why this is authored rather than fixed. One component runs both studies:
// the EMG gesture protocol it was written for, and the post-stroke ADL protocol.
// Its copy was EMG's — "make and hold this gesture", "relax your hand" — and for
// an ADL run that is not merely imprecise. Told to someone performing a reach-
// overhead or trunk task, "relax your hand" is an instruction to do something
// other than the protocol, delivered at full size during a recorded run
// (TEC-NATKIT-69).
//
// Replacing it with ADL wording would just move the defect onto the EMG study,
// so the words live on the protocol. Neutral defaults, because a default is what
// every hand-built protocol gets and the safe direction is the one that cannot
// tell anybody to move the wrong body part: a gesture IS a task, but a trunk
// task is not a hand.

export interface ParticipantCopy {
    /** Singular noun for one cue: "task", "gesture", "activity". */
    cue_noun?: string;
    /** Plural, authored rather than derived — "activity" does not take an "s". */
    cue_noun_plural?: string;
    /**
     * The imperative shown above the cue name, and reused mid-sentence in the
     * how-to, so it should read as a standalone sentence: "Perform this task",
     * "Make and hold this gesture".
     */
    cue_instruction?: string;
    /**
     * What to do during Rest and lead-in. ⚠️ The one that matters most; see the
     * note at the top.
     */
    rest_instruction?: string;
}

export interface ResolvedParticipantCopy {
    cueNoun: string;
    cueNounPlural: string;
    cueInstruction: string;
    restInstruction: string;
}

// Deliberately body-part-free, and deliberately not EMG's words even though EMG
// is what shipped first. An EMG protocol that wants "gesture" back says so.
export const DEFAULT_PARTICIPANT_COPY: ResolvedParticipantCopy = {
    cueNoun: "task",
    cueNounPlural: "tasks",
    cueInstruction: "Perform this task",
    restInstruction: "Return to a comfortable resting position",
};

function clean(value: unknown): string | null {
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

/**
 * Resolve a protocol's copy, field by field.
 *
 * Per FIELD, not per object: a protocol that names its noun but not its rest
 * instruction must still get the safe default for the instruction, rather than
 * falling back wholesale and losing the noun — or worse, being treated as fully
 * authored and rendering a blank line where the instruction should be.
 */
export function resolveParticipantCopy(
    copy: ParticipantCopy | null | undefined,
): ResolvedParticipantCopy {
    const noun = clean(copy?.cue_noun) ?? DEFAULT_PARTICIPANT_COPY.cueNoun;
    return {
        cueNoun: noun,
        // Falls back to the DEFAULT plural, not to `${noun}s`: guessing English
        // plurals is how "activitys" reaches a participant's screen.
        cueNounPlural:
            clean(copy?.cue_noun_plural) ?? DEFAULT_PARTICIPANT_COPY.cueNounPlural,
        cueInstruction:
            clean(copy?.cue_instruction) ?? DEFAULT_PARTICIPANT_COPY.cueInstruction,
        restInstruction:
            clean(copy?.rest_instruction) ??
            DEFAULT_PARTICIPANT_COPY.restInstruction,
    };
}

/** Read the copy off either protocol shape, both of which carry it optionally. */
export function participantCopyOf(protocol: unknown): ResolvedParticipantCopy {
    if (protocol && typeof protocol === "object") {
        const field = (protocol as { participant_copy?: ParticipantCopy })
            .participant_copy;
        return resolveParticipantCopy(field);
    }
    return resolveParticipantCopy(null);
}

/**
 * The "what do I do right now" line, per cue phase.
 *
 * A pure function rather than a `$derived` inside the runner, so the exact words
 * a participant reads are covered by tests instead of only by a screenshot of one
 * phase. Every phase this returns for is a phase somebody is looking at during a
 * recorded run.
 */
export function instructionForPhase(
    phase: string,
    tutorial: boolean,
    copy: ResolvedParticipantCopy,
): string {
    switch (phase) {
        case "lead_in":
            return `Get ready — ${copy.restInstruction.toLowerCase()}`;
        case "rest":
            return copy.restInstruction;
        case "tail_rest":
            return `All done — ${copy.restInstruction.toLowerCase()}`;
        case "wait":
            return "Waiting for you";
        // An instruction step carries the author's own words in its prompt, so a
        // second line above it would be this component talking over the author.
        case "instruction":
            return "";
        default:
            return tutorial
                ? "Practice — this is not kept for training"
                : copy.cueInstruction;
    }
}
