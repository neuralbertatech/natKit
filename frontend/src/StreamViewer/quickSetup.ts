// Quick setup: a high-level recipe that GENERATES a step protocol.
//
// The step editor can express far more than most sessions need, and making
// someone learn cues, class labels, rest classes, tutorial flags and repeat
// groups before they can record anything is the steepest part of the learning
// curve. A recipe asks the few questions that actually vary — what are the
// classes, how long is a hold, how many rounds — and compiles the rest.
//
// This is a GENERATOR, not a second protocol shape. It compiles to the same
// ExperimentStep[] a hand-authored protocol uses, so the runner, markers,
// recording, instances and training never learn that quick setup exists. The
// recipe is stored alongside the steps (as `protocol.quick_setup`) only so the
// card can be reopened and re-edited; the steps remain the source of truth.
//
// Editing steps by hand DETACHES the recipe (see the designer): regenerating
// over hand edits would silently destroy them, which is the one behaviour a
// generator must never have.
import type {
    ExperimentStep,
    InterleavedRest,
    RepeatStep,
    CueStep,
    InstructionStep,
} from "./experimentSteps";

/** Which high-level questions the card asks; all produce the same recipe. */
export type QuickSetupTemplate = "image_cues" | "gesture_list";

export interface QuickSetupCue {
    /** The class a trainer learns from. */
    label: string;
    /** Shown to the participant; defaults to the label. */
    text?: string;
    image_url?: string;
    image_name?: string;
    audio_url?: string;
    audio_name?: string;
}

export interface QuickSetupRecipe {
    recipe_version: 1;
    template: QuickSetupTemplate;
    cues: QuickSetupCue[];
    /** Rounds of the main block. */
    repetitions: number;
    hold_s: number;
    /** 0 disables the rest between cues entirely. */
    rest_s: number;
    /** Randomize each rest ±, so cue onsets can't be anticipated. */
    rest_jitter_s?: number;
    /** A "Get ready" instruction before anything else; 0 disables. */
    lead_in_s: number;
    shuffle: boolean;
    /** Shuffle seed for the main block — stored so a run is reproducible. */
    seed?: number;
    /** One tutorial pass through the classes, recorded but not trained on. */
    practice_pass: boolean;
    /** An instruction that holds until someone confirms they're ready. */
    wait_for_ready: boolean;
}

export function defaultQuickSetupRecipe(
    template: QuickSetupTemplate,
): QuickSetupRecipe {
    return {
        recipe_version: 1,
        template,
        cues: [],
        repetitions: 3,
        hold_s: 2,
        rest_s: 2,
        lead_in_s: 3,
        shuffle: true,
        seed: 1,
        practice_pass: true,
        wait_for_ready: true,
    };
}

export function isQuickSetupRecipe(
    value: unknown,
): value is QuickSetupRecipe {
    return (
        !!value &&
        typeof value === "object" &&
        Array.isArray((value as QuickSetupRecipe).cues)
    );
}

/** Classes a recipe collects, in order, ignoring blank rows. */
export function recipeClasses(recipe: QuickSetupRecipe): string[] {
    const seen: string[] = [];
    for (const cue of recipe.cues) {
        const label = cue.label.trim();
        if (label && !seen.includes(label)) {
            seen.push(label);
        }
    }
    return seen;
}

/**
 * Turn a filename into a usable class label: "Fist Closed.PNG" -> "fist_closed".
 * The author can always edit it, but the common case (one well-named image per
 * class) should need no typing at all.
 */
export function labelFromFilename(filename: string): string {
    const withoutExtension = filename.replace(/\.[^.]+$/, "");
    return (
        withoutExtension
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "") || "cue"
    );
}

function cueStepFrom(
    id: string,
    cue: QuickSetupCue,
    holdS: number,
    textPrefix?: string,
): CueStep {
    const shown = cue.text?.trim() || cue.label;
    const step: CueStep = {
        id,
        kind: "cue",
        label: cue.label.trim(),
        text: textPrefix ? `${textPrefix}${shown}` : shown,
        duration_s: holdS,
    };
    if (cue.image_url) {
        step.image_url = cue.image_url;
        step.image_name = cue.image_name;
    }
    if (cue.audio_url) {
        step.audio_url = cue.audio_url;
        step.audio_name = cue.audio_name;
    }
    return step;
}

/**
 * Compile a recipe into steps.
 *
 * Shape: [get ready] -> [practice pass, tutorial] -> [ready gate] -> main block.
 * Practice comes before the gate deliberately — you rehearse, then confirm you
 * are ready to record for real. This mirrors exampleStepProtocol().
 *
 * The cue/rest alternation is expressed with a repeat group's `interleave_rest`
 * rather than emitted rest rows, so a regenerated protocol stays as short as
 * the recipe (N cue rows, not 2N) and the rests land correctly even when the
 * group is shuffled.
 *
 * Step ids are derived from position, not generated, so regenerating an
 * unchanged recipe produces an identical protocol.
 */
export function compileQuickSetupSteps(
    recipe: QuickSetupRecipe,
): ExperimentStep[] {
    const steps: ExperimentStep[] = [];
    const cues = recipe.cues.filter((cue) => cue.label.trim().length > 0);
    const holdS = Math.max(0, recipe.hold_s ?? 0);
    const restS = Math.max(0, recipe.rest_s ?? 0);
    const restJitterS = Math.max(0, recipe.rest_jitter_s ?? 0);

    const interleaveRest: InterleavedRest | null =
        restS > 0 || restJitterS > 0
            ? {
                  duration_s: restS,
                  ...(restJitterS > 0 ? { jitter_s: restJitterS } : {}),
              }
            : null;

    if ((recipe.lead_in_s ?? 0) > 0) {
        const leadIn: InstructionStep = {
            id: "quick-lead-in",
            kind: "instruction",
            text: "Get ready",
            duration_s: recipe.lead_in_s,
        };
        steps.push(leadIn);
    }

    if (recipe.practice_pass && cues.length > 0) {
        const practice: RepeatStep = {
            id: "quick-practice",
            kind: "repeat",
            times: 1,
            tutorial: true,
            steps: cues.map((cue, index) =>
                cueStepFrom(`quick-practice-cue-${index}`, cue, holdS, "Practice: "),
            ),
        };
        if (interleaveRest) practice.interleave_rest = { ...interleaveRest };
        steps.push(practice);
    }

    if (recipe.wait_for_ready) {
        const gate: InstructionStep = {
            id: "quick-ready",
            kind: "instruction",
            text: "Ready to start the recording?",
            // Ignored while wait_for_input holds, but the type requires it.
            duration_s: 0,
            wait_for_input: true,
            continue_label: "I'm ready",
        };
        steps.push(gate);
    }

    if (cues.length > 0) {
        const main: RepeatStep = {
            id: "quick-main",
            kind: "repeat",
            times: Math.max(1, Math.floor(recipe.repetitions ?? 1)),
            steps: cues.map((cue, index) =>
                cueStepFrom(`quick-cue-${index}`, cue, holdS),
            ),
        };
        if (recipe.shuffle) {
            main.shuffle = true;
            main.seed = recipe.seed ?? 1;
        }
        if (interleaveRest) main.interleave_rest = { ...interleaveRest };
        steps.push(main);
    }

    return steps;
}

/** Why a recipe cannot be recorded yet, or null when it can. */
export function quickSetupBlockedReason(
    recipe: QuickSetupRecipe,
): string | null {
    const cues = recipe.cues.filter((cue) => cue.label.trim().length > 0);
    if (cues.length === 0) {
        return recipe.template === "image_cues"
            ? "Add at least one image to collect a class."
            : "Add at least one class.";
    }
    if ((recipe.hold_s ?? 0) <= 0) {
        return "Hold time must be longer than 0s.";
    }
    const labels = cues.map((cue) => cue.label.trim());
    if (new Set(labels).size !== labels.length) {
        return "Two cues share a class label — merge them or rename one.";
    }
    return null;
}
