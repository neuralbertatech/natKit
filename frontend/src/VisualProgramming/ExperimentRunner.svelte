<script lang="ts">
    // Participant-facing run surface for an experiment node. Rendered both inline
    // on the node card (compact) and in a large modal (to actually conduct the
    // experiment — the participant watches the cue prompt). Presentational: the
    // recording state + Record/Stop handlers live in the editor.
    import { CircleDot, Play, Square } from "@lucide/svelte";
    import type { EmgCueEvent } from "../StreamViewer/experiment";

    interface Props {
        protocolLabel: string;
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
    const instruction = $derived.by(() => {
        if (!activeCue) return "";
        if (activeCue.phase === "lead_in") return "Get ready — relax your hand";
        if (activeCue.phase === "rest") return "Relax";
        if (activeCue.phase === "tail_rest") return "All done — relax";
        if (activeCue.phase === "wait") return "Waiting for you";
        if (activeCue.phase === "instruction") return "";
        return activeCue.tutorial
            ? "Practice — this is not kept for training"
            : "Make and hold this gesture";
    });

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
                <span>{holdsRemaining} of {holdsTotal} gestures left</span>
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
                {summary.holdCues} gestures{totalReps > 0
                    ? ` · ${totalReps} rounds`
                    : ""} · ~{timeLeftLabel}
            </span>
            {#if large}
                <ol class="how-to">
                    <li>
                        Press <strong>Record</strong>, then follow the big prompt.
                    </li>
                    <li>
                        When a gesture name appears, <strong
                            >make and hold it</strong
                        > steadily until the countdown reaches 0.
                    </li>
                    <li>On <strong>Rest</strong>, relax your hand fully.</li>
                    <li>
                        Each gesture repeats {totalReps || "several"} times in a shuffled
                        order — keep contractions consistent for the best accuracy.
                    </li>
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
