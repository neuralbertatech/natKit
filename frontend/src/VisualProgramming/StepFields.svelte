<script lang="ts">
    // The labelled fields for ONE step.
    //
    // Extracted so the step list and the protocol canvas's inspector render the
    // same controls from one definition — a canvas that re-declared them would
    // drift the moment a field is added.
    //
    // The component knows nothing about the step tree: the parent binds each
    // callback to the step it passed in, so there is no parentId or lookup here.
    import { Dices, Image as ImageIcon, Volume2, Trash2 } from "@lucide/svelte";
    import type {
        ExperimentStep,
        ExperimentStepKind,
        InterleavedRest,
    } from "../StreamViewer/experimentSteps";

    interface Props {
        step: ExperimentStep;
        readOnly: boolean;
        /** The protocol's filler class, shown as the rest label placeholder. */
        restClass: string;
        /** Whether this step's repeat group is collapsed (affects its summary). */
        collapsed?: boolean;
        /** Which media slot is mid-upload for this step, if any. */
        uploadingSlot?: "image" | "audio" | null;
        /** Human-readable summary of a collapsed repeat group. */
        groupSummaryText?: string;
        onPatch: (patch: Record<string, unknown>) => void;
        onReplace: (next: ExperimentStep) => void;
        onPatchInterleave: (patch: Partial<InterleavedRest>) => void;
        onToggleInterleave: (enabled: boolean) => void;
        onUploadMedia: (slot: "image" | "audio", file: File) => void;
        onClearMedia: (slot: "image" | "audio") => void;
        /** Swap a step's kind, keeping whatever still applies. */
        retypeStep: (step: ExperimentStep, kind: ExperimentStepKind) => ExperimentStep;
        rollSeed: () => number;
        stepKindLabels: Record<ExperimentStepKind, string>;
        mediaLabel: (step: ExperimentStep, slot: "image" | "audio") => string;
    }

    let {
        step,
        readOnly,
        restClass,
        collapsed = false,
        uploadingSlot = null,
        groupSummaryText = "",
        onPatch,
        onReplace,
        onPatchInterleave,
        onToggleInterleave,
        onUploadMedia,
        onClearMedia,
        retypeStep,
        rollSeed,
        stepKindLabels: STEP_KIND_LABELS,
        mediaLabel,
    }: Props = $props();

    const uploading = $derived({ [step.id]: uploadingSlot } as Record<
        string,
        "image" | "audio" | null
    >);
    const groupSummary = (_: unknown) => groupSummaryText;
</script>

    <label class="field kind-field">
        <span>Step type</span>
        <select
            class="step-kind"
            disabled={readOnly}
            value={step.kind}
            onchange={(event) => {
                const kind = (
                    event.currentTarget as HTMLSelectElement
                ).value as ExperimentStepKind;
                onReplace(retypeStep(step, kind));
            }}
        >
            {#each Object.entries(STEP_KIND_LABELS).filter(([kind]) => kind !== "wait" || step.kind === "wait") as [kind, kindLabel]}
                <option value={kind}>{kindLabel}</option>
            {/each}
        </select>
    </label>

    {#if step.kind === "repeat"}
        <label class="field num-field">
            <span>Times</span>
            <input
                type="number"
                min="1"
                disabled={readOnly}
                value={step.times}
                oninput={(event) =>
                    onPatch({
                        times: Number(
                            (
                                event.currentTarget as HTMLInputElement
                            ).value,
                        ),
                    })}
            />
        </label>
        {#if step.shuffle === true}
            <label
                class="field num-field"
                title="Shuffle seed — the same seed reproduces the same order on every run"
            >
                <span>Seed</span>
                <input
                    type="number"
                    min="1"
                    disabled={readOnly}
                    value={step.seed ?? 1}
                    oninput={(event) =>
                        onPatch({
                            seed: Number(
                                (
                                    event.currentTarget as HTMLInputElement
                                ).value,
                            ),
                        })}
                />
            </label>
            <button
                type="button"
                class="icon-btn dice-btn"
                disabled={readOnly}
                title="Reroll the shuffle seed — a new order, still reproducible"
                onclick={() =>
                    onPatch({
                        seed: rollSeed(),
                    })}
            >
                <Dices size={12} />
            </button>
        {/if}
        {#if step.interleave_rest}
            <!-- The interleaved rest's own timing. It is
                 not an editable row, so its duration and
                 jitter live on the group. -->
            <label
                class="field num-field"
                title="Length of each inserted rest"
            >
                <span>Rest (s)</span>
                <input
                    type="number"
                    min="0"
                    step="0.5"
                    disabled={readOnly}
                    value={step.interleave_rest.duration_s}
                    oninput={(event) =>
                        onPatchInterleave({
                            duration_s: Number(
                                (
                                    event.currentTarget as HTMLInputElement
                                ).value,
                            ),
                        })}
                />
            </label>
            <label
                class="field num-field"
                title="Randomize each inserted rest by up to ± this many seconds, from the protocol's timing seed. Stops participants anticipating the next cue."
            >
                <span>± Jitter (s)</span>
                <input
                    type="number"
                    min="0"
                    step="0.5"
                    disabled={readOnly}
                    value={step.interleave_rest.jitter_s ?? 0}
                    oninput={(event) => {
                        const value = Number(
                            (
                                event.currentTarget as HTMLInputElement
                            ).value,
                        );
                        onPatchInterleave({
                            jitter_s:
                                value > 0 ? value : undefined,
                        });
                    }}
                />
            </label>
        {/if}
        {#if collapsed}
            <span class="group-summary">
                {groupSummary(step)}
            </span>
        {/if}
    {:else}
        <label class="field grow">
            <span>Shown to participant</span>
            <input
                placeholder="e.g. Make a fist"
                disabled={readOnly}
                value={step.text ?? ""}
                oninput={(event) =>
                    onPatch({
                        text: (
                            event.currentTarget as HTMLInputElement
                        ).value,
                    })}
            />
        </label>
    {/if}

    {#if step.kind === "cue" || step.kind === "rest"}
        <label
            class="field label-field"
            title={step.kind === "cue"
                ? "The class a trainer learns from — recorded on this cue's markers"
                : "Optional — defaults to the protocol's rest class"}
        >
            <span>
                {step.kind === "cue"
                    ? "Class label (trained on)"
                    : "Class label (optional)"}
            </span>
            <input
                placeholder={step.kind === "rest"
                    ? restClass
                    : "e.g. fist"}
                disabled={readOnly}
                value={(step as { label?: string }).label ??
                    ""}
                oninput={(event) =>
                    onPatch({
                        label: (
                            event.currentTarget as HTMLInputElement
                        ).value,
                    })}
            />
        </label>
    {/if}

    {#if step.kind === "cue" || step.kind === "rest" || (step.kind === "instruction" && step.wait_for_input !== true)}
        <label class="field num-field">
            <span>
                {step.kind === "cue"
                    ? "Hold (s)"
                    : "Duration (s)"}
            </span>
            <input
                type="number"
                min="0"
                step="0.5"
                disabled={readOnly}
                value={(step as { duration_s?: number })
                    .duration_s ?? 0}
                oninput={(event) =>
                    onPatch({
                        duration_s: Number(
                            (
                                event.currentTarget as HTMLInputElement
                            ).value,
                        ),
                    })}
            />
        </label>
        <label
            class="field num-field"
            title="Randomize this duration by up to ± this many seconds — drawn from the protocol's timing seed, so the same seed recreates the same schedule. 0 = fixed."
        >
            <span>± Jitter (s)</span>
            <input
                type="number"
                min="0"
                step="0.5"
                disabled={readOnly}
                value={(step as { jitter_s?: number })
                    .jitter_s ?? 0}
                oninput={(event) => {
                    const value = Number(
                        (
                            event.currentTarget as HTMLInputElement
                        ).value,
                    );
                    // 0 means "fixed" — keep the JSON
                    // clean rather than storing it.
                    onPatch({
                        jitter_s:
                            value > 0
                                ? value
                                : undefined,
                    });
                }}
            />
        </label>
    {/if}

    {#if step.kind === "wait" || (step.kind === "instruction" && step.wait_for_input === true)}
        <label class="field label-field">
            <span>Continue-button text</span>
            <input
                placeholder="Continue"
                disabled={readOnly}
                value={step.continue_label ?? ""}
                oninput={(event) =>
                    onPatch({
                        continue_label: (
                            event.currentTarget as HTMLInputElement
                        ).value,
                    })}
            />
        </label>
    {/if}

    <div class="card-flags">
        {#if step.kind === "instruction"}
            <label
                class="field check"
                title="Hold the session at this instruction until someone presses the button, instead of running for a fixed time"
            >
                <input
                    type="checkbox"
                    disabled={readOnly}
                    checked={step.wait_for_input === true}
                    onchange={(event) => {
                        const checked = (
                            event.currentTarget as HTMLInputElement
                        ).checked;
                        onPatch({
                            wait_for_input:
                                checked || undefined,
                            continue_label: checked
                                ? step.continue_label ||
                                  "Continue"
                                : undefined,
                        });
                    }}
                />
                <span>Wait for input</span>
            </label>
        {/if}
        {#if step.kind === "repeat"}
            <label
                class="field check"
                title="Shuffle the group's order on each pass (seeded, so a run is reproducible)"
            >
                <input
                    type="checkbox"
                    disabled={readOnly}
                    checked={step.shuffle === true}
                    onchange={(event) =>
                        onPatch({
                            shuffle: (
                                event.currentTarget as HTMLInputElement
                            ).checked,
                        })}
                />
                <span>Shuffle each pass</span>
            </label>
            <label
                class="field check"
                title="Insert a rest after every step in this group (including the last, so passes are separated too). Added at compile time and after shuffling, so the rests never end up back to back."
            >
                <input
                    type="checkbox"
                    disabled={readOnly}
                    checked={step.interleave_rest != null}
                    onchange={(event) =>
                        onToggleInterleave(
                            (event.currentTarget as HTMLInputElement).checked,
                        )}
                />
                <span>Rest between steps</span>
            </label>
        {/if}
        <label
            class="field check"
            title="Practice: recorded and flagged, but excluded from training"
        >
            <input
                type="checkbox"
                disabled={readOnly}
                checked={step.tutorial === true}
                onchange={(event) =>
                    onPatch({
                        tutorial: (
                            event.currentTarget as HTMLInputElement
                        ).checked,
                    })}
            />
            <span>Tutorial</span>
        </label>
    </div>

<style>
    .field {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
    }

    .field > span {
        font-size: 0.6rem;
        letter-spacing: 0.02em;
        color: #7f91c8;
        white-space: nowrap;
    }

    .field.grow {
        flex: 1 1 10rem;
        min-width: 8rem;
    }

    .field.label-field {
        flex: 0 1 11rem;
        min-width: 7rem;
    }

    .field.num-field {
        width: 5rem;
    }

    .field.kind-field {
        width: 10.5rem;
    }

    .field.check {
        flex-direction: row;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.66rem;
        color: #7f91c8;
        cursor: pointer;
        white-space: nowrap;
    }

    .field.check > span {
        font-size: 0.66rem;
    }

    .field.check input[type="checkbox"] {
        width: auto;
        margin: 0;
    }

    input,
    select {
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(12, 18, 28, 0.75);
        color: #e6ecf5;
        padding: 0.35rem 0.45rem;
        font-size: 0.78rem;
    }

    .step-kind {
        font-size: 0.7rem;
        padding: 0.28rem 0.25rem;
    }

    .card-flags {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        align-self: center;
        margin-left: 0.2rem;
    }

    .group-summary {
        align-self: center;
        font-size: 0.68rem;
        color: #9fb0d8;
    }

    .dice-btn {
        align-self: flex-end;
    }

    .icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.05);
        color: #e6ecf5;
        padding: 0.28rem;
        cursor: pointer;
    }

    .icon-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
</style>
