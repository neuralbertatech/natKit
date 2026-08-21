<script lang="ts">
    // Participant-facing run surface for an experiment node. Rendered both inline
    // on the node card (compact) and in a large modal (to actually conduct the
    // experiment — the participant watches the cue prompt). Presentational: the
    // recording state + Record/Stop handlers live in the editor.
    import { CircleDot, Play, Square } from "@lucide/svelte";
    import type { EmgCueEvent } from "../StreamViewer/experiment";
    import {
        instructionForPhase,
        participantCopyOf,
    } from "../StreamViewer/participantCopy";

    interface Props {
        protocolLabel: string;
        /**
         * The protocol itself, for the words the PARTICIPANT sees
         * (TEC-NATKIT-69). Passed rather than resolved by the caller so a caller
         * cannot forget to and silently fall back to a default: absent here means
         * the neutral copy, which is the safe direction, but a caller passing the
         * protocol it already has is the normal case.
         */
        protocol?: unknown;
        classes: string[];
        recording: boolean;
        // True when a DIFFERENT experiment is recording (only one at a time).
        recordingElsewhere?: boolean;
        elapsedMs: number;
        durationMs: number;
        activeCue: EmgCueEvent | null;
        nextCue: EmgCueEvent | null;
        // Progress context so the participant can pace the session.
        totalReps?: number;
        currentRep?: number | null;
        holdsRemaining?: number;
        holdsTotal?: number;
        summary: { holdCues: number; durationS: number };
        // Large = modal presentation (big cue text); false = compact on-node.
        large?: boolean;
        onRecord: () => void;
        onStop: () => void;
        // Releases a wait step. Whoever is at this screen presses it — the
        // operator or the participant; the protocol author decides by wording the
        // step's text and its button label.
        onContinue?: () => void;
    }

    let {
        protocolLabel,
        protocol = null,
        classes,
        recording,
        recordingElsewhere = false,
        elapsedMs,
        durationMs,
        activeCue,
        nextCue,
        totalReps = 0,
        currentRep = null,
        holdsRemaining = 0,
        holdsTotal = 0,
        summary,
        large = false,
        onRecord,
        onStop,
        onContinue,
    }: Props = $props();

    // A "hold" cue is the one the participant performs; everything else is a
    // preparatory/rest phase shown muted.
    const isActivePhase = $derived(activeCue?.phase === "hold");

    // A step protocol can pause the session until someone confirms. The clock is
    // held while this is true, so nothing after it is mis-timed.
    const awaitingInput = $derived(
        recording && activeCue?.wait_for_input === true,
    );

    const promptText = $derived.by(() => {
        if (!activeCue) return recording ? "…" : "Ready";
        if (activeCue.phase === "lead_in") return "Get ready";
        if (activeCue.phase === "rest" || activeCue.phase === "tail_rest")
            return "Rest";
        // instruction and wait steps carry the author's own words, which are the
        // whole point of a user-defined protocol — show them verbatim.
        return activeCue.prompt;
    });

    // A plain-language instruction for the current phase — the "what do I do
    // right now" line above the gesture name.
    // ⚠️ Every participant-facing word here comes from the PROTOCOL, not from
    // this component (TEC-NATKIT-69). It used to say "relax your hand" and "make
    // and hold this gesture", which is EMG's vocabulary; told to someone
    // performing a reach-overhead or trunk task, the first of those is an
    // instruction to do something other than the protocol.
    const copy = $derived(participantCopyOf(protocol));

    const instruction = $derived(
        activeCue
            ? instructionForPhase(
                  activeCue.phase,
                  activeCue.tutorial === true,
                  copy,
              )
            : "",
    );

    const secondsLeftInCue = $derived.by(() => {
        if (!activeCue) return null;
        // A wait has no length until it is released; a countdown would be a lie.
        if (activeCue.wait_for_input) return null;
        return Math.max(0, (activeCue.end_offset_ms - elapsedMs) / 1000);
    });

    const progressPct = $derived(
        durationMs > 0 ? Math.min(100, (elapsedMs / durationMs) * 100) : 0,
    );

    // Time remaining in the whole session, mm:ss.
    const timeLeftLabel = $derived.by(() => {
        const totalSecLeft = Math.max(0, Math.round((durationMs - elapsedMs) / 1000));
        const m = Math.floor(totalSecLeft / 60);
        const s = totalSecLeft % 60;
        return `${m}:${s.toString().padStart(2, "0")}`;
    });

    const nextLabel = $derived.by(() => {
        if (!nextCue) return null;
        if (nextCue.phase === "hold") return nextCue.prompt;
        if (nextCue.phase === "lead_in") return "Get ready";
        return "Rest";
    });
</script>

<div class="experiment-runner" class:large>
    {#if recording}
        {#if instruction}
            <span class="cue-instruction" class:active={isActivePhase}
                >{instruction}</span
            >
        {/if}
        {#if activeCue?.image_url}
            <img
                class="cue-image"
                class:large
                src={activeCue.image_url}
                alt={promptText}
            />
        {/if}
        <div class="cue-stage" class:active={isActivePhase}>
            <span class="cue-prompt">{promptText}</span>
            {#if secondsLeftInCue !== null}
                <span class="cue-countdown">{secondsLeftInCue.toFixed(1)}s</span>
            {/if}
        </div>
        {#if nextLabel}
            <div class="cue-next">
                Next: <strong>{nextLabel}</strong>
            </div>
        {/if}
        <div class="progress-track">
            <div class="progress-fill" style={`width:${progressPct}%`}></div>
        </div>
        <div class="cue-progress">
            {#if currentRep && totalReps > 0}
                <span>Round {currentRep} of {totalReps}</span>
            {/if}
            {#if holdsTotal > 0}
                <span>{holdsRemaining} of {holdsTotal} {copy.cueNounPlural} left</span>
            {/if}
            <span>{timeLeftLabel} remaining</span>
        </div>
        <div class="run-footer">
            <span class="elapsed"
                >{(elapsedMs / 1000).toFixed(1)}s / {(durationMs / 1000).toFixed(0)}s</span
            >
            {#if awaitingInput}
                <button
                    type="button"
                    class="run-btn continue"
                    onmousedown={(e) => e.stopPropagation()}
                    onclick={(e) => {
                        e.stopPropagation();
                        onContinue?.();
                    }}
                >
                    <Play size={large ? 18 : 14} />
                    {activeCue?.continue_label || "Continue"}
                </button>
            {/if}
            <button
                type="button"
                class="run-btn stop"
                onmousedown={(e) => e.stopPropagation()}
                onclick={(e) => {
                    e.stopPropagation();
                    onStop();
                }}
            >
                <Square size={large ? 18 : 14} />
                Stop
            </button>
        </div>
    {:else}
        <div class="ready-stage">
            <span class="ready-title">{protocolLabel}</span>
            <div class="class-chips">
                {#each classes as cls}
                    <span class="chip">{cls}</span>
                {/each}
            </div>
            <span class="ready-meta">
                {summary.holdCues} {copy.cueNounPlural}{totalReps > 0
                    ? ` · ${totalReps} rounds`
                    : ""} · ~{timeLeftLabel}
            </span>
            {#if large}
                <ol class="how-to">
                    <li>
                        Press <strong>Record</strong>, then follow the big prompt.
                    </li>
                    <li>
                        <strong>{copy.cueInstruction}</strong> when its name
                        appears, until the countdown reaches 0.
                    </li>
                    <li>On <strong>Rest</strong>, {copy.restInstruction.toLowerCase()}.</li>
                    <li>
                        Each {copy.cueNoun} repeats {totalReps || "several"} times in a
                        shuffled order.
                    </li>
                    <!-- The EMG advice that used to sit here ("keep contractions
                         consistent for the best accuracy") is gone rather than
                         reworded: "contractions" is EMG vocabulary, and the advice
                         does not transfer to an activity of daily living. -->
                </ol>
            {/if}
        </div>
        <button
            type="button"
            class="run-btn record"
            disabled={recordingElsewhere}
            title={recordingElsewhere
                ? "Another experiment is recording"
                : "Start recording this experiment"}
            onmousedown={(e) => e.stopPropagation()}
            onclick={(e) => {
                e.stopPropagation();
                onRecord();
            }}
        >
            <CircleDot size={large ? 18 : 14} />
            Record
        </button>
    {/if}
</div>

<style>
    .experiment-runner {
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: #cbd5e1;
    }

    .cue-instruction {
        text-align: center;
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .cue-instruction.active {
        color: #34d399;
        font-weight: 600;
    }

    .cue-stage {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        padding: 12px;
        border-radius: 8px;
        background: rgba(100, 116, 139, 0.12);
        border: 1px solid #24313f;
    }

    .cue-stage.active {
        background: rgba(52, 211, 153, 0.14);
        border-color: rgba(52, 211, 153, 0.5);
    }

    .cue-prompt {
        font-weight: 700;
        font-size: 1.5rem;
        line-height: 1.1;
        text-align: center;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .cue-stage.active .cue-prompt {
        color: #34d399;
    }

    .cue-countdown {
        font-variant-numeric: tabular-nums;
        color: #64748b;
        font-size: 0.9rem;
    }

    .cue-next {
        text-align: center;
        color: #64748b;
        font-size: 0.8rem;
    }

    .cue-next strong {
        color: #94a3b8;
    }

    .cue-progress {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 4px 14px;
        color: #7c8aa0;
        font-size: 0.78rem;
        font-variant-numeric: tabular-nums;
    }

    .progress-track {
        height: 8px;
        border-radius: 999px;
        background: rgba(100, 116, 139, 0.2);
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background: #34d399;
        border-radius: 999px;
    }

    .run-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .elapsed {
        font-variant-numeric: tabular-nums;
        color: #94a3b8;
        font-size: 0.85rem;
    }

    .ready-stage {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .ready-title {
        font-weight: 600;
        color: #e2e8f0;
    }

    .class-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }

    .chip {
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(96, 165, 250, 0.15);
        color: #93c5fd;
        font-size: 0.75rem;
    }

    .ready-meta {
        color: #64748b;
        font-size: 0.8rem;
    }

    .how-to {
        margin: 6px 0 0;
        padding-left: 1.2rem;
        display: flex;
        flex-direction: column;
        gap: 6px;
        color: #9fb0c6;
        font-size: 0.9rem;
        line-height: 1.4;
        text-align: left;
    }
    .how-to strong {
        color: #e2e8f0;
    }

    .run-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        border-radius: 6px;
        padding: 6px 12px;
        cursor: pointer;
        border: 1px solid #334155;
        font-weight: 600;
    }

    .run-btn.record {
        background: #0f766e;
        color: #ecfdf5;
        border-color: #0f766e;
    }

    .run-btn.record:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    /* Image stimulus. Capped so a large asset cannot push the controls off the
       node card; the modal presentation gets more room. */
    .cue-image {
        display: block;
        max-width: 100%;
        max-height: 90px;
        margin: 0 auto 0.3rem;
        border-radius: 6px;
        object-fit: contain;
        background: #0a0f1e;
    }

    .cue-image.large {
        max-height: 320px;
        margin-bottom: 0.6rem;
    }

    .run-btn.stop {
        background: #7f1d1d;
        color: #fee2e2;
        border-color: #7f1d1d;
    }

    /* A wait step blocks the session, so its release is the primary action. */
    .run-btn.continue {
        background: #1d4ed8;
        color: #eff6ff;
        border-color: #1d4ed8;
        font-weight: 700;
    }

    /* Large modal presentation: blow the cue prompt up for the participant. */
    .experiment-runner.large {
        gap: 18px;
        width: min(1100px, 90vw);
    }

    .experiment-runner.large .cue-stage {
        padding: 48px 24px;
    }

    .experiment-runner.large .cue-prompt {
        font-size: clamp(3rem, 12vw, 8rem);
    }

    .experiment-runner.large .cue-countdown {
        font-size: 2rem;
    }

    /* --- Large view WITH an image stimulus (TEC-NATKIT-68) -------------------
     *
     * Decision (Zach, 2026-08-20): when there is an image, the IMAGE is the primary
     * cue and the prompt becomes its caption. The ADL study presents each activity
     * visually and verbally, so the picture is the stimulus rather than decoration.
     *
     * ⚠️ Before this, the modal body (flex, align-items: center) centred a runner
     * taller than itself, so the overflow spilled off BOTH ends: the image started
     * at y = -126 with only its bottom third visible, and the countdown was cut off
     * the bottom. A participant was being shown a different stimulus from the one
     * the marker recorded.
     *
     * The prompt shrinks only when an image is present (adjacent-sibling selector),
     * so an image-less protocol — EMG gesture cues, say — keeps its full-size text.
     */
    .experiment-runner.large {
        /* ⚠️ NOT `max-height: 100%`.
         *
         * That was the obvious way to say "never taller than your box", and it made
         * things worse: a percentage max-height resolved against a flex parent whose
         * own height is indefinite is circular, and the browser settled it by
         * sizing the modal body to its CONTENT -- 432px of a 608px budget, measured.
         * So the box the runner was told to fit inside had itself shrunk to fit the
         * runner, and 176px of usable height simply vanished.
         *
         * `height: 100%` is definite in this context (the body is flex: 1 1 0% inside
         * a 100vh panel), so the runner fills its budget and its children divide a
         * known number. */
        /* ⚠️ NO PERCENTAGE HEIGHT, in either direction.
         *
         * `max-height: 100%` and `height: 100%` both resolve against a flex parent
         * whose own height is indefinite, which is circular — the browser settled it
         * by sizing the modal body to its CONTENT (432px of a 608px budget, measured
         * twice), so the box the runner was told to fit inside had itself shrunk to
         * fit the runner and 176px of usable height vanished.
         *
         * The body is `display: flex; align-items: center`, so the runner is a flex
         * item: stretching it fills the cross axis with no percentage involved. */
        align-self: stretch;
        min-height: 0;
    }

    .experiment-runner.large .cue-image {
        /* ⚠️ A height BUDGET, not `flex: 1 1 auto`.
         *
         * The first attempt let the image take the slack and shrink freely. It
         * stopped clipping and then collapsed to 15px tall at 1280x720, because the
         * prompt block is fixed-size and the image absorbed every bit of shrinkage
         * -- the opposite of "the image is the primary cue". Measured, not guessed.
         *
         * So it claims its share up front and may only give ground as a last resort
         * (flex-shrink 1, flex-grow 0). 55vh leaves room for the caption, countdown
         * and padding at both 720 and 1050 tall. */
        max-height: none;
        /* Takes the remaining space now that the parent's height is definite, with a
         * floor so it can never be squeezed to the 15px it collapsed to on the first
         * attempt. */
        flex: 1 1 auto;
        /* A floor so it can never be squeezed to the 15px it collapsed to on an
         * earlier attempt, set just low enough that the whole column fits the
         * (now un-capped) body at 720px tall — measured, not chosen by feel. Above
         * that height flex-grow gives the image everything spare, which is the
         * point of "the image is the primary cue". */
        min-height: 24vh;
        width: 100%;
    }

    .experiment-runner.large .cue-image + .cue-stage {
        flex: 0 0 auto;
        padding: 16px 24px;
    }

    .experiment-runner.large .cue-image + .cue-stage .cue-prompt {
        /* A caption, not the stimulus: still legible across a room, no longer
         * three lines of 8rem competing with the picture above it. */
        font-size: clamp(1.4rem, 3vw, 2.4rem);
        letter-spacing: 0.02em;
    }

    .experiment-runner.large .cue-next {
        font-size: 1.4rem;
    }

    .experiment-runner.large .cue-instruction {
        font-size: 1.4rem;
    }

    .experiment-runner.large .cue-progress {
        font-size: 1.05rem;
        gap: 6px 24px;
    }

    .experiment-runner.large .how-to {
        font-size: 1.05rem;
        gap: 8px;
        max-width: 640px;
        margin: 10px auto 0;
    }

    .experiment-runner.large .ready-meta {
        font-size: 1.05rem;
    }

    .experiment-runner.large .ready-stage {
        align-items: center;
        text-align: center;
        gap: 10px;
    }

    .experiment-runner.large .ready-title {
        font-size: 1.5rem;
    }

    .experiment-runner.large .chip {
        font-size: 0.95rem;
        padding: 4px 12px;
    }

    .experiment-runner.large .elapsed {
        font-size: 1.2rem;
    }

    .experiment-runner.large .run-btn {
        padding: 12px 24px;
        font-size: 1.1rem;
    }
</style>
