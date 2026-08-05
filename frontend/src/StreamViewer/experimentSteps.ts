// User-authored experiment protocols.
//
// The original protocol was a fixed shape — N classes x R repetitions with
// hold/rest/lead-in/tail timings — which cannot express "explain the task, let
// them practise, wait until they say they are ready, then collect real data".
// A step protocol is instead an ordered list of steps the author writes:
//
//   instruction  show text for a fixed time
//   cue          show text and hold a labelled class (this is the real data)
//   rest         show text and rest
//   wait         hold until someone presses Continue (unknown duration)
//   repeat       run a group of steps N times, optionally shuffled per pass
//
// Any step (or a whole repeat group) can be marked `tutorial`, which flows onto
// every cue it produces so a trainer can exclude practice data.
//
// Everything compiles down to the existing EmgCueEvent[] timeline, so the runner,
// the marker payloads, the recorded session and the timeline strip all keep
// working unchanged. The one thing offsets cannot express is a wait, whose length
// is only known once it is released — see resolveScheduleWaits().
import { buildCueScheduleForProtocol } from "./experiment";
import type { EmgCueEvent, EmgCuePhase } from "./experiment";
import type { SessionProtocol } from "./types";

export type ExperimentStepKind =
    | "instruction"
    | "cue"
    | "rest"
    | "wait"
    | "repeat";

interface StepCommon {
    /** Stable id so the editor can reorder/patch without positional confusion. */
    id: string;
    kind: ExperimentStepKind;
    /** Shown to the participant while the step runs. */
    text?: string;
    /** Practice: recorded, flagged, excluded from training. */
    tutorial?: boolean;
    // Media stimulus shown/played for this step. Either an absolute URL or a
    // site-root path — files under frontend/public are served from the root, so
    // frontend/public/media/fist.png is "/media/fist.png".
    //
    // Both are recorded in the cue's marker attributes: what the participant was
    // shown or heard is part of the experimental record, not just presentation.
    image_url?: string;
    /** Played once when the step begins. */
    audio_url?: string;
}

export interface InstructionStep extends StepCommon {
    kind: "instruction";
    text: string;
    duration_s: number;
}

export interface CueStep extends StepCommon {
    kind: "cue";
    /** The class label this cue collects — what a classifier learns. */
    label: string;
    duration_s: number;
}

export interface RestStep extends StepCommon {
    kind: "rest";
    duration_s: number;
    /** Defaults to the protocol's rest class. */
    label?: string;
}

export interface WaitStep extends StepCommon {
    kind: "wait";
    text: string;
    /** Button text; defaults to "Continue". */
    continue_label?: string;
}

export interface RepeatStep extends StepCommon {
    kind: "repeat";
    times: number;
    steps: ExperimentStep[];
    /** Shuffle the child order on each pass (per-pass, seeded, reproducible). */
    shuffle?: boolean;
    seed?: number;
}

export type ExperimentStep =
    | InstructionStep
    | CueStep
    | RestStep
    | WaitStep
    | RepeatStep;

export interface StepProtocol {
    protocol_version: 1;
    protocol_id: string;
    label: string;
    /** Filler class for rest steps that do not name their own. */
    rest_class: string;
    steps: ExperimentStep[];
}

export function isStepProtocol(protocol: unknown): protocol is StepProtocol {
    return (
        !!protocol &&
        typeof protocol === "object" &&
        Array.isArray((protocol as StepProtocol).steps)
    );
}

/** Distinct class labels a protocol collects, ignoring tutorial-only cues. */
export function protocolClasses(protocol: StepProtocol): string[] {
    const labels = new Set<string>();
    const walk = (steps: ExperimentStep[], tutorial: boolean) => {
        for (const step of steps) {
            const isTutorial = tutorial || step.tutorial === true;
            if (step.kind === "repeat") {
                walk(step.steps, isTutorial);
            } else if (step.kind === "cue" && !isTutorial && step.label) {
                labels.add(step.label);
            }
        }
    };
    walk(protocol.steps, false);
    return [...labels];
}

const PHASE_BY_KIND: Record<
    Exclude<ExperimentStepKind, "repeat">,
    EmgCuePhase
> = {
    instruction: "instruction",
    cue: "hold",
    rest: "rest",
    wait: "wait",
};

// Deterministic shuffle, same generator the fixed protocol uses, so a seeded
// repeat group produces the same order every run.
function mulberry32(seed: number): () => number {
    let value = seed >>> 0;
    return () => {
        value += 0x6d2b79f5;
        let t = value;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function shuffled<T>(items: T[], seed: number): T[] {
    const next = [...items];
    const rand = mulberry32(seed);
    for (let index = next.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(rand() * (index + 1));
        [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
    }
    return next;
}

/**
 * Flatten a step protocol into the timeline the runner and marker builders use.
 *
 * A `wait` step becomes a zero-length event flagged `wait_for_input`: the author
 * cannot know how long a participant will take, so the schedule carries the
 * barrier and resolveScheduleWaits() applies the real duration afterwards.
 */
export function compileStepProtocol(protocol: StepProtocol): EmgCueEvent[] {
    const restClass = protocol.rest_class || "rest";
    const schedule: EmgCueEvent[] = [];
    let offsetMs = 0;
    let cueId = 0;
    // Advances once per completed pass of a repeat group, so recorded cues keep
    // the rep_index that downstream featurisation and reporting expect.
    let repIndex = -1;

    const emit = (
        step: Exclude<ExperimentStep, RepeatStep>,
        tutorial: boolean,
    ) => {
        const phase = PHASE_BY_KIND[step.kind];
        const durationMs =
            step.kind === "wait"
                ? 0
                : Math.max(0, Math.round((step.duration_s ?? 0) * 1000));
        const label =
            step.kind === "cue"
                ? step.label
                : step.kind === "rest"
                  ? (step.label || restClass)
                  : restClass;
        const event: EmgCueEvent = {
            cue_id: cueId,
            rep_index: repIndex,
            phase,
            gesture: label,
            prompt: step.text || label,
            start_offset_ms: offsetMs,
            end_offset_ms: offsetMs + durationMs,
        };
        if (tutorial || step.tutorial === true) {
            event.tutorial = true;
        }
        if (step.kind === "wait") {
            event.wait_for_input = true;
            event.continue_label = step.continue_label || "Continue";
        }
        if (step.image_url) {
            event.image_url = step.image_url;
        }
        if (step.audio_url) {
            event.audio_url = step.audio_url;
        }
        schedule.push(event);
        cueId += 1;
        offsetMs += durationMs;
    };

    const walk = (steps: ExperimentStep[], tutorial: boolean) => {
        for (const step of steps) {
            const isTutorial = tutorial || step.tutorial === true;
            if (step.kind === "repeat") {
                const times = Math.max(0, Math.floor(step.times ?? 0));
                for (let pass = 0; pass < times; pass += 1) {
                    repIndex += 1;
                    const children = step.shuffle
                        ? shuffled(step.steps, (step.seed ?? 1) + pass)
                        : step.steps;
                    walk(children, isTutorial);
                }
                continue;
            }
            walk_leaf(step, isTutorial);
        }
    };
    const walk_leaf = (
        step: Exclude<ExperimentStep, RepeatStep>,
        tutorial: boolean,
    ) => emit(step, tutorial);

    walk(protocol.steps, false);
    return schedule;
}

/**
 * Apply the real duration of each wait to everything after it.
 *
 * Markers are stamped as sessionStart + offset, so without this every event after
 * a wait would be reported earlier than it happened — the recorded timeline would
 * disagree with the data. `pausesMsByCueId` is what the runner measured.
 */
export function resolveScheduleWaits(
    schedule: EmgCueEvent[],
    pausesMsByCueId: Record<number, number>,
): EmgCueEvent[] {
    let shiftMs = 0;
    return schedule.map((event) => {
        const shifted: EmgCueEvent = {
            ...event,
            start_offset_ms: event.start_offset_ms + shiftMs,
            end_offset_ms: event.end_offset_ms + shiftMs,
        };
        if (event.wait_for_input) {
            const heldMs = Math.max(0, pausesMsByCueId[event.cue_id] ?? 0);
            shifted.end_offset_ms = shifted.start_offset_ms + heldMs;
            shiftMs += heldMs;
        }
        return shifted;
    });
}

/**
 * Compile whichever protocol shape an experiment happens to carry. Experiments
 * saved before step protocols existed keep their fixed classes x repetitions
 * form, and both compile to the same timeline, so every caller can stay shape
 * agnostic.
 */
export function scheduleForProtocol(protocol: unknown): EmgCueEvent[] {
    if (isStepProtocol(protocol)) {
        return compileStepProtocol(protocol);
    }
    return buildCueScheduleForProtocol(protocol as SessionProtocol);
}

/** Nominal duration, treating unreleased waits as zero. */
export function stepProtocolDurationMs(schedule: EmgCueEvent[]): number {
    return schedule.reduce(
        (total, event) => Math.max(total, event.end_offset_ms),
        0,
    );
}

let stepIdCounter = 0;
export function newStepId(prefix = "step"): string {
    stepIdCounter += 1;
    return `${prefix}-${stepIdCounter}-${Math.floor(Math.random() * 1e6)}`;
}

/**
 * Convert a legacy fixed protocol (classes x repetitions) into steps, so existing
 * experiments open in the step editor instead of appearing empty, and so the two
 * shapes produce the same timeline.
 */
export function stepsFromLegacyProtocol(protocol: {
    protocol_id?: string;
    label?: string;
    classes?: string[];
    rest_class?: string;
    repetitions?: number;
    hold_s?: number;
    rest_s?: number;
    lead_in_s?: number;
    tail_rest_s?: number;
    seed?: number;
}): StepProtocol {
    const classes = (protocol.classes ?? []).filter(Boolean);
    const restClass = protocol.rest_class || "rest";
    const holdS = protocol.hold_s ?? 2;
    const restS = protocol.rest_s ?? 2;
    const steps: ExperimentStep[] = [];

    if ((protocol.lead_in_s ?? 0) > 0) {
        steps.push({
            id: newStepId("lead-in"),
            kind: "instruction",
            text: "Prepare",
            duration_s: protocol.lead_in_s as number,
        });
    }

    const pass: ExperimentStep[] = [];
    for (const label of classes) {
        pass.push({
            id: newStepId("cue"),
            kind: "cue",
            label,
            text: label,
            duration_s: holdS,
        });
        if (restS > 0) {
            pass.push({
                id: newStepId("rest"),
                kind: "rest",
                label: restClass,
                text: "Rest",
                duration_s: restS,
            });
        }
    }
    if (pass.length > 0) {
        steps.push({
            id: newStepId("reps"),
            kind: "repeat",
            times: Math.max(1, protocol.repetitions ?? 1),
            shuffle: true,
            seed: protocol.seed ?? 1,
            steps: pass,
        });
    }

    if ((protocol.tail_rest_s ?? 0) > 0) {
        steps.push({
            id: newStepId("tail-rest"),
            kind: "rest",
            label: restClass,
            text: "Rest",
            duration_s: protocol.tail_rest_s as number,
        });
    }

    return {
        protocol_version: 1,
        protocol_id: protocol.protocol_id || "custom",
        label: protocol.label || "Custom protocol",
        rest_class: restClass,
        steps,
    };
}

/** A starting point that demonstrates every step kind, including a tutorial. */
export function exampleStepProtocol(): StepProtocol {
    return {
        protocol_version: 1,
        protocol_id: "custom",
        label: "Custom protocol",
        rest_class: "rest",
        steps: [
            {
                id: newStepId("intro"),
                kind: "instruction",
                text: "We will record a few hand gestures. Follow the prompts.",
                duration_s: 5,
            },
            {
                id: newStepId("tutorial"),
                kind: "repeat",
                times: 1,
                tutorial: true,
                steps: [
                    {
                        id: newStepId("practice-cue"),
                        kind: "cue",
                        label: "fist",
                        text: "Practice: make a fist",
                        duration_s: 3,
                    },
                    {
                        id: newStepId("practice-rest"),
                        kind: "rest",
                        text: "Relax",
                        duration_s: 2,
                    },
                ],
            },
            {
                id: newStepId("ready"),
                kind: "wait",
                text: "Ready to start the real recording?",
                continue_label: "I'm ready",
            },
            {
                id: newStepId("main"),
                kind: "repeat",
                times: 3,
                shuffle: true,
                seed: 1,
                steps: [
                    {
                        id: newStepId("cue"),
                        kind: "cue",
                        label: "fist",
                        text: "Make a fist",
                        duration_s: 2,
                    },
                    {
                        id: newStepId("rest"),
                        kind: "rest",
                        text: "Rest",
                        duration_s: 2,
                    },
                ],
            },
        ],
    };
}
