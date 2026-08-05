<script lang="ts">
    // Experiment-level UI (experiment-history-snapshots-plan, Phase 1).
    //
    // The experiment used to be a node you dropped on the canvas and configured
    // in the node inspector. It is now a first-class object that OWNS this board,
    // so its authoring surface belongs to the board, not to a node: bind an
    // experiment here, author its protocol here, and Record from here. What
    // stays on the canvas is a config-less `markers` node that republishes this
    // experiment's marker timeline.
    import {
        ChevronDown,
        ChevronUp,
        CircleDot,
        Image as ImageIcon,
        Volume2,
        Plus,
        Square,
        Trash2,
        Unlink,
    } from "@lucide/svelte";
    import type {
        Experiment,
        SessionProtocol,
        StreamGraphDefinition,
    } from "../StreamViewer/types";
    import type { EmgCueEvent } from "../StreamViewer/experiment";
    import {
        compileStepProtocol,
        isStepProtocol,
        newStepId,
        protocolClasses,
        stepProtocolDurationMs,
        stepsFromLegacyProtocol,
        type ExperimentStep,
        type ExperimentStepKind,
        type StepProtocol,
    } from "../StreamViewer/experimentSteps";

    interface Props {
        experiments: Experiment[];
        // The experiment bound to the current board, if any.
        bound: Experiment | null;
        boardId: string;
        // Whether the board is savable at all (an immutable instance is not).
        readOnly: boolean;
        // Cue-schedule preview for the bound protocol.
        summary: { holdCues: number; durationS: number } | null;
        // Sources in this board — every one of them is a recorded source now that
        // the experiment owns the whole graph, so this is informational rather
        // than something to wire.
        recordedDevices: string[];
        // Live recording state; null when this board isn't recording.
        recording: {
            sessionId: string;
            elapsedMs: number;
            durationMs: number;
            activeCue: EmgCueEvent | null;
        } | null;
        // True when SOME other board/experiment holds the recorder.
        recordingElsewhere: boolean;
        message: string | null;
        // This experiment's recorded instances, newest first. An instance is an
        // immutable snapshot of the board welded to the data captured in its window.
        instances: StreamGraphDefinition[];
        onDeleteInstance: (graphId: string, immutable: boolean) => void;
        onBind: (experimentId: string) => void;
        onCreate: () => void;
        onPatch: (patch: Partial<Experiment>) => void;
        onPatchProtocol: (patch: Partial<SessionProtocol>) => void;
        onDelete: () => void;
        onRecord: () => void;
        onStop: () => void;
        // Releases a wait step that is holding the session.
        onContinue: () => void;
    }

    let {
        experiments,
        bound,
        boardId,
        readOnly,
        summary,
        recordedDevices,
        recording,
        recordingElsewhere,
        message,
        instances,
        onDeleteInstance,
        onBind,
        onCreate,
        onPatch,
        onPatchProtocol,
        onDelete,
        onRecord,
        onStop,
        onContinue,
    }: Props = $props();

    // --- User-authored step protocols -------------------------------------
    // A step protocol replaces the fixed classes x repetitions shape with an
    // ordered list the author writes: instructions, labelled cues, rests, a
    // wait-for-input barrier, and repeat groups. Any step (or group) can be
    // marked as tutorial, which flags its cues as practice.
    const stepProtocol = $derived(
        bound && isStepProtocol(bound.protocol)
            ? (bound.protocol as StepProtocol)
            : null,
    );

    const stepSummary = $derived.by(() => {
        if (!stepProtocol) return null;
        const schedule = compileStepProtocol(stepProtocol);
        return {
            steps: schedule.length,
            durationS: Math.round(stepProtocolDurationMs(schedule) / 1000),
            classes: protocolClasses(stepProtocol),
            tutorialCues: schedule.filter((c) => c.tutorial).length,
            waits: schedule.filter((c) => c.wait_for_input).length,
        };
    });

    function commitSteps(steps: ExperimentStep[]) {
        onPatchProtocol({ steps } as Partial<SessionProtocol>);
    }

    // Steps are edited as a plain tree; a repeat group is the only container, and
    // `parentId` addresses "inside that group" so one set of handlers covers both
    // levels.
    function mapSteps(
        steps: ExperimentStep[],
        parentId: string | null,
        change: (list: ExperimentStep[]) => ExperimentStep[],
    ): ExperimentStep[] {
        if (parentId === null) return change(steps);
        return steps.map((step) =>
            step.kind === "repeat" && step.id === parentId
                ? { ...step, steps: change(step.steps) }
                : step,
        );
    }

    function patchStep(
        parentId: string | null,
        stepId: string,
        patch: Record<string, unknown>,
    ) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) =>
                list.map((step) =>
                    step.id === stepId
                        ? ({ ...step, ...patch } as ExperimentStep)
                        : step,
                ),
            ),
        );
    }

    function removeStep(parentId: string | null, stepId: string) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) =>
                list.filter((step) => step.id !== stepId),
            ),
        );
    }

    function moveStep(parentId: string | null, stepId: string, delta: number) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) => {
                const index = list.findIndex((step) => step.id === stepId);
                const target = index + delta;
                if (index < 0 || target < 0 || target >= list.length) return list;
                const next = [...list];
                [next[index], next[target]] = [next[target], next[index]];
                return next;
            }),
        );
    }

    function blankStep(kind: ExperimentStepKind): ExperimentStep {
        const id = newStepId(kind);
        if (kind === "cue")
            return { id, kind, label: "gesture", text: "Do the thing", duration_s: 2 };
        if (kind === "rest") return { id, kind, text: "Rest", duration_s: 2 };
        if (kind === "wait")
            return { id, kind, text: "Ready to continue?", continue_label: "Continue" };
        if (kind === "repeat")
            return { id, kind, times: 3, shuffle: true, seed: 1, steps: [] };
        return { id, kind: "instruction", text: "Explain the task", duration_s: 5 };
    }

    function addStep(parentId: string | null, kind: ExperimentStepKind) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) => [
                ...list,
                blankStep(kind),
            ]),
        );
    }

    // Bring a legacy fixed protocol into the step editor without losing it: the
    // conversion produces the same timeline.
    function convertToSteps() {
        if (!bound?.protocol) return;
        const converted = stepsFromLegacyProtocol(bound.protocol as never);
        onPatchProtocol(converted as unknown as Partial<SessionProtocol>);
    }


    function parseClassList(raw: string): string[] {
        return raw
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function instanceStatusLabel(graph: StreamGraphDefinition): string {
        const recording = graph.recording;
        const status = recording?.status ?? "unknown";
        const rows = recording?.artifacts?.total_rows;
        if (status === "complete") {
            return `${rows ?? 0} rows`;
        }
        if (status === "failed") {
            return "failed";
        }
        return status;
    }

    // Why Record is unavailable, or null when it is.
    const recordBlockedReason = $derived.by(() => {
        if (!bound) return "Bind an experiment to this board first.";
        if (readOnly)
            return "This is an immutable recorded instance. Fork it to record again.";
        if (recordingElsewhere) return "Another experiment is recording.";
        if (!bound.protocol) return "Bind a protocol to this experiment first.";
        // A step protocol has no `classes` field — its classes are whatever its
        // (non-tutorial) cue steps collect.
        const classes = stepProtocol
            ? protocolClasses(stepProtocol)
            : (bound.protocol.classes ?? []);
        if (classes.length === 0)
            return stepProtocol
                ? "Add at least one cue step that is not marked tutorial."
                : "Add at least one class to the protocol.";
        if (!summary || summary.holdCues === 0)
            return "The protocol produces no cues — check the timing.";
        return null;
    });
</script>

<div class="experiment-panel">
    <div class="panel-header">
        <div>
            <p class="eyebrow">Experiment</p>
            <h3>{bound ? bound.label || bound.experiment_id : "No experiment"}</h3>
        </div>
        <div class="header-actions">
            <button
                type="button"
                class="icon-btn"
                onclick={onCreate}
                title="Create a new experiment bound to this board"
            >
                <Plus size={16} />
            </button>
            {#if bound}
                <button
                    type="button"
                    class="icon-btn"
                    onclick={() => onBind("")}
                    title="Unbind this experiment from the board"
                >
                    <Unlink size={16} />
                </button>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={onDelete}
                    title="Delete this experiment"
                >
                    <Trash2 size={14} />
                </button>
            {/if}
        </div>
    </div>

    <label>
        <span>Bound experiment</span>
        <select
            value={bound?.experiment_id ?? ""}
            onchange={(event) =>
                onBind((event.currentTarget as HTMLSelectElement).value)}
        >
            <option value="">— none —</option>
            {#each experiments as experiment}
                <option value={experiment.experiment_id}>
                    {experiment.label || experiment.experiment_id}
                    {experiment.live_graph_id &&
                    experiment.live_graph_id !== boardId
                        ? ` (on ${experiment.live_graph_id})`
                        : ""}
                </option>
            {/each}
        </select>
    </label>

    {#if !bound}
        <p class="muted-text">
            An experiment owns this board and its recorded history. Bind one (or
            create a new one) to author a protocol and record; a
            <code>markers</code> node on the canvas then carries its cue timeline
            into viewers, combine, and export.
        </p>
    {:else}
        {@const protocol = bound.protocol}
        <p class="panel-id">{bound.experiment_id}</p>
        <label>
            <span>Experiment name</span>
            <input
                value={bound.label}
                oninput={(event) =>
                    onPatch({
                        label: (event.currentTarget as HTMLInputElement).value,
                    })}
            />
        </label>
        <label>
            <span>Participant id</span>
            <input
                value={bound.participant_id}
                oninput={(event) =>
                    onPatch({
                        participant_id: (event.currentTarget as HTMLInputElement)
                            .value,
                    })}
            />
        </label>
        <label>
            <span>Notes</span>
            <input
                value={bound.notes}
                oninput={(event) =>
                    onPatch({
                        notes: (event.currentTarget as HTMLInputElement).value,
                    })}
            />
        </label>

        {#if protocol}
            <p class="eyebrow section-label">Protocol</p>
            <label>
                <span>Protocol name</span>
                <input
                    value={protocol.label}
                    oninput={(event) =>
                        onPatchProtocol({
                            label: (event.currentTarget as HTMLInputElement)
                                .value,
                        })}
                />
            </label>
            <!-- The fixed classes x repetitions form. A step protocol replaces
                 it with an ordered step list, so only one shape is editable. -->
            {#if !stepProtocol}
            <label>
                <span>Classes (comma-separated labels)</span>
                <input
                    value={protocol.classes.join(", ")}
                    oninput={(event) =>
                        onPatchProtocol({
                            classes: parseClassList(
                                (event.currentTarget as HTMLInputElement).value,
                            ),
                        })}
                />
            </label>
            <label>
                <span>Rest / idle class</span>
                <input
                    value={protocol.rest_class}
                    oninput={(event) =>
                        onPatchProtocol({
                            rest_class: (event.currentTarget as HTMLInputElement)
                                .value,
                        })}
                />
            </label>
            <div class="field-grid">
                <label>
                    <span>Repetitions</span>
                    <input
                        type="number"
                        min="1"
                        step="1"
                        value={protocol.repetitions}
                        oninput={(event) =>
                            onPatchProtocol({
                                repetitions: Number(
                                    (event.currentTarget as HTMLInputElement)
                                        .value,
                                ),
                            })}
                    />
                </label>
                <label>
                    <span>Hold (s)</span>
                    <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={protocol.hold_s}
                        oninput={(event) =>
                            onPatchProtocol({
                                hold_s: Number(
                                    (event.currentTarget as HTMLInputElement)
                                        .value,
                                ),
                            })}
                    />
                </label>
                <label>
                    <span>Rest (s)</span>
                    <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={protocol.rest_s}
                        oninput={(event) =>
                            onPatchProtocol({
                                rest_s: Number(
                                    (event.currentTarget as HTMLInputElement)
                                        .value,
                                ),
                            })}
                    />
                </label>
                <label>
                    <span>Lead-in (s)</span>
                    <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={protocol.lead_in_s}
                        oninput={(event) =>
                            onPatchProtocol({
                                lead_in_s: Number(
                                    (event.currentTarget as HTMLInputElement)
                                        .value,
                                ),
                            })}
                    />
                </label>
                <label>
                    <span>Tail rest (s)</span>
                    <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={protocol.tail_rest_s}
                        oninput={(event) =>
                            onPatchProtocol({
                                tail_rest_s: Number(
                                    (event.currentTarget as HTMLInputElement)
                                        .value,
                                ),
                            })}
                    />
                </label>
            </div>
            {/if}
        {/if}

        {#snippet stepRow(
            step: ExperimentStep,
            parentId: string | null,
            depth: number,
        )}
            <div class="step-row" class:tutorial={step.tutorial} style={`margin-left:${depth * 0.8}rem`}>
                <div class="step-head">
                    <select
                        class="step-kind"
                        disabled={readOnly}
                        value={step.kind}
                        onchange={(event) => {
                            const kind = (event.currentTarget as HTMLSelectElement)
                                .value as ExperimentStepKind;
                            // Swap in a fresh step of the new kind but keep the id
                            // and position, so the row does not jump around.
                            patchStep(parentId, step.id, {
                                ...blankStep(kind),
                                id: step.id,
                                tutorial: step.tutorial,
                            });
                        }}
                    >
                        <option value="instruction">Instruction</option>
                        <option value="cue">Cue (recorded class)</option>
                        <option value="rest">Rest</option>
                        <option value="wait">Wait for input</option>
                        <option value="repeat">Repeat group</option>
                    </select>

                    {#if step.kind === "repeat"}
                        <label class="step-inline">
                            <span>×</span>
                            <input
                                class="step-num"
                                type="number"
                                min="1"
                                disabled={readOnly}
                                value={step.times}
                                oninput={(event) =>
                                    patchStep(parentId, step.id, {
                                        times: Number(
                                            (event.currentTarget as HTMLInputElement).value,
                                        ),
                                    })}
                            />
                        </label>
                        <label class="step-inline" title="Shuffle the group's order each pass">
                            <input
                                type="checkbox"
                                disabled={readOnly}
                                checked={step.shuffle === true}
                                onchange={(event) =>
                                    patchStep(parentId, step.id, {
                                        shuffle: (event.currentTarget as HTMLInputElement)
                                            .checked,
                                    })}
                            />
                            <span>shuffle</span>
                        </label>
                    {:else}
                        <input
                            class="step-text"
                            placeholder="What the participant sees"
                            disabled={readOnly}
                            value={step.text ?? ""}
                            oninput={(event) =>
                                patchStep(parentId, step.id, {
                                    text: (event.currentTarget as HTMLInputElement).value,
                                })}
                        />
                    {/if}

                    {#if step.kind === "cue" || step.kind === "rest"}
                        <input
                            class="step-label"
                            placeholder="class label"
                            title="The marker label recorded for this step"
                            disabled={readOnly}
                            value={(step as { label?: string }).label ?? ""}
                            oninput={(event) =>
                                patchStep(parentId, step.id, {
                                    label: (event.currentTarget as HTMLInputElement).value,
                                })}
                        />
                    {/if}

                    {#if step.kind !== "wait" && step.kind !== "repeat"}
                        <label class="step-inline">
                            <input
                                class="step-num"
                                type="number"
                                min="0"
                                step="0.5"
                                disabled={readOnly}
                                value={(step as { duration_s?: number }).duration_s ?? 0}
                                oninput={(event) =>
                                    patchStep(parentId, step.id, {
                                        duration_s: Number(
                                            (event.currentTarget as HTMLInputElement).value,
                                        ),
                                    })}
                            />
                            <span>s</span>
                        </label>
                    {/if}

                    {#if step.kind === "wait"}
                        <input
                            class="step-label"
                            placeholder="button text"
                            disabled={readOnly}
                            value={step.continue_label ?? ""}
                            oninput={(event) =>
                                patchStep(parentId, step.id, {
                                    continue_label: (
                                        event.currentTarget as HTMLInputElement
                                    ).value,
                                })}
                        />
                    {/if}

                    <label
                        class="step-inline"
                        title="Practice: recorded and flagged, but excluded from training"
                    >
                        <input
                            type="checkbox"
                            disabled={readOnly}
                            checked={step.tutorial === true}
                            onchange={(event) =>
                                patchStep(parentId, step.id, {
                                    tutorial: (event.currentTarget as HTMLInputElement)
                                        .checked,
                                })}
                        />
                        <span>tutorial</span>
                    </label>

                    <div class="step-actions">
                        <button
                            type="button"
                            class="icon-btn"
                            disabled={readOnly}
                            title="Move up"
                            onclick={() => moveStep(parentId, step.id, -1)}
                        >
                            <ChevronUp size={12} />
                        </button>
                        <button
                            type="button"
                            class="icon-btn"
                            disabled={readOnly}
                            title="Move down"
                            onclick={() => moveStep(parentId, step.id, 1)}
                        >
                            <ChevronDown size={12} />
                        </button>
                        <button
                            type="button"
                            class="icon-btn"
                            disabled={readOnly}
                            title="Remove this step"
                            onclick={() => removeStep(parentId, step.id)}
                        >
                            <Trash2 size={12} />
                        </button>
                    </div>
                </div>

                {#if step.kind !== "repeat"}
                    <!-- Media on its own line: the head row is already dense, and
                         a URL needs room to be readable. -->
                    <div class="step-media">
                        <label class="step-inline" title="Image shown for this step">
                            <ImageIcon size={11} />
                            <input
                                class="step-media-url"
                                placeholder="/media/fist.png"
                                disabled={readOnly}
                                value={step.image_url ?? ""}
                                oninput={(event) =>
                                    patchStep(parentId, step.id, {
                                        image_url:
                                            (event.currentTarget as HTMLInputElement)
                                                .value || undefined,
                                    })}
                            />
                        </label>
                        <label class="step-inline" title="Sound played once when this step begins">
                            <Volume2 size={11} />
                            <input
                                class="step-media-url"
                                placeholder="/media/beep.wav"
                                disabled={readOnly}
                                value={step.audio_url ?? ""}
                                oninput={(event) =>
                                    patchStep(parentId, step.id, {
                                        audio_url:
                                            (event.currentTarget as HTMLInputElement)
                                                .value || undefined,
                                    })}
                            />
                        </label>
                    </div>
                {/if}

                {#if step.kind === "repeat"}
                    {#each step.steps as child (child.id)}
                        {@render stepRow(child, step.id, depth + 1)}
                    {/each}
                    <div class="step-add nested">
                        {#each ["instruction", "cue", "rest", "wait"] as kind}
                            <button
                                type="button"
                                class="add-step-btn"
                                disabled={readOnly}
                                onclick={() => addStep(step.id, kind as ExperimentStepKind)}
                            >
                                <Plus size={11} />{kind}
                            </button>
                        {/each}
                    </div>
                {/if}
            </div>
        {/snippet}

        {#if stepProtocol}
            <p class="eyebrow section-label">Steps</p>
            <p class="hint-text">
                Each step is shown to the participant in order. A <strong>cue</strong>
                records its class label; <strong>wait for input</strong> holds the
                session until someone presses the button; anything marked
                <strong>tutorial</strong> is recorded but kept out of training.
            </p>
            <div class="step-list">
                {#each stepProtocol.steps as step (step.id)}
                    {@render stepRow(step, null, 0)}
                {/each}
                {#if stepProtocol.steps.length === 0}
                    <p class="hint-text">No steps yet — add one below.</p>
                {/if}
            </div>
            <div class="step-add">
                {#each ["instruction", "cue", "rest", "wait", "repeat"] as kind}
                    <button
                        type="button"
                        class="add-step-btn"
                        disabled={readOnly}
                        onclick={() => addStep(null, kind as ExperimentStepKind)}
                    >
                        <Plus size={11} />{kind}
                    </button>
                {/each}
            </div>
            {#if stepSummary}
                <div class="summary-row">
                    <span>Timeline</span>
                    <strong>
                        {stepSummary.steps} steps · ~{stepSummary.durationS}s{stepSummary.waits >
                        0
                            ? ` · ${stepSummary.waits} wait${stepSummary.waits > 1 ? "s" : ""}`
                            : ""}
                    </strong>
                </div>
                <div class="summary-row">
                    <span>Classes</span>
                    <strong>{stepSummary.classes.join(", ") || "none"}</strong>
                </div>
                {#if stepSummary.tutorialCues > 0}
                    <div class="summary-row">
                        <span>Tutorial cues</span>
                        <strong>{stepSummary.tutorialCues} (not trained on)</strong>
                    </div>
                {/if}
            {/if}
        {:else if protocol}
            <button
                type="button"
                class="action-btn secondary convert-steps"
                disabled={readOnly}
                onclick={convertToSteps}
                title="Rewrite this protocol as editable steps — the timeline is unchanged"
            >
                Convert to editable steps
            </button>
        {/if}

        {#if summary && !stepProtocol}
            <div class="summary-row">
                <span>Schedule</span>
                <strong>{summary.holdCues} cues · ~{summary.durationS}s</strong>
            </div>
        {/if}
        <div class="summary-row">
            {#if recordedDevices.length > 0}
                <span>Records</span>
                <strong>{recordedDevices.join(", ")}</strong>
            {:else}
                <span
                    >Every source on this board is recorded — add one to capture
                    data alongside the markers.</span
                >
            {/if}
        </div>

        <div class="panel-action-row">
            {#if recording}
                <button type="button" class="action-btn secondary" onclick={onStop}>
                    <Square size={15} />
                    Stop recording
                </button>
            {:else}
                <button
                    type="button"
                    class="action-btn"
                    disabled={recordBlockedReason !== null}
                    title={recordBlockedReason ?? "Run the protocol and record"}
                    onclick={onRecord}
                >
                    <CircleDot size={15} />
                    Record
                </button>
            {/if}
        </div>
        {#if !recording && recordBlockedReason}
            <p class="muted-text">{recordBlockedReason}</p>
        {/if}

        {#if recording}
            <div class="runtime-card">
                <div class="summary-row">
                    <span>Session</span>
                    <strong>{recording.sessionId}</strong>
                </div>
                <div class="summary-row">
                    <span>Elapsed</span>
                    <strong>
                        {(recording.elapsedMs / 1000).toFixed(1)}s / {(
                            recording.durationMs / 1000
                        ).toFixed(0)}s
                    </strong>
                </div>
                {#if recording.activeCue}
                    <div class="summary-row">
                        <span>Current cue</span>
                        <strong
                            >{recording.activeCue.prompt} · {recording.activeCue
                                .gesture}</strong
                        >
                    </div>
                    {#if recording.activeCue.image_url}
                        <!-- The operator should see the stimulus the participant is
                             being shown, without having to open a run surface. -->
                        <img
                            class="cue-thumb"
                            src={recording.activeCue.image_url}
                            alt={recording.activeCue.prompt}
                        />
                    {/if}
                {/if}
                {#if recording.activeCue?.wait_for_input}
                    <!-- A wait step holds the session. The runner surface may not
                         be open, so the release has to be reachable from here too
                         or the run cannot proceed at all. -->
                    <button
                        type="button"
                        class="action-btn continue-wait"
                        onclick={onContinue}
                    >
                        {recording.activeCue.continue_label || "Continue"}
                    </button>
                {/if}
            </div>
        {/if}
    {/if}

    {#if bound}
        <p class="eyebrow section-label">History</p>
        {#if instances.length === 0}
            <p class="muted-text">
                No recordings yet. Each Record mints an instance: an immutable
                snapshot of this board welded to the data captured during the run.
            </p>
        {:else}
            <div class="instance-list">
                {#each instances as instance}
                    {@const status = instance.recording?.status ?? "unknown"}
                    <div class="instance-row">
                        <div class="instance-main">
                            <span class="instance-id">
                                {instance.instance_id}
                                {#if instance.origin === "fork"}
                                    <span class="instance-tag fork">fork</span>
                                {:else if instance.immutable}
                                    <span class="instance-tag sealed">sealed</span>
                                {/if}
                            </span>
                            <span class={`instance-status ${status}`}>
                                {instanceStatusLabel(instance)}
                            </span>
                        </div>
                        {#if instance.recording?.message}
                            <span class="instance-note">
                                {instance.recording.message}
                            </span>
                        {/if}
                        <button
                            type="button"
                            class="icon-btn instance-delete"
                            title={instance.immutable
                                ? "Delete this sealed recording and its artifacts"
                                : "Delete this instance"}
                            onclick={() =>
                                onDeleteInstance(
                                    instance.graph_id,
                                    instance.immutable === true,
                                )}
                        >
                            <Trash2 size={13} />
                        </button>
                    </div>
                {/each}
            </div>
        {/if}
    {/if}

    {#if message}
        <p class="muted-text">{message}</p>
    {/if}
</div>

<style>
    .experiment-panel {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        padding: 0.85rem;
        overflow-y: auto;
        color: #e6ecf5;
    }

    .panel-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.5rem;
    }

    .panel-header h3 {
        margin: 0.1rem 0 0;
        font-size: 0.95rem;
        overflow-wrap: anywhere;
    }

    .header-actions {
        display: flex;
        gap: 0.25rem;
    }

    .eyebrow {
        margin: 0;
        font-size: 0.65rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(230, 236, 245, 0.55);
    }

    .section-label {
        margin-top: 0.35rem;
    }

    .panel-id {
        margin: -0.2rem 0 0;
        font-family: ui-monospace, SFMono-Regular, monospace;
        font-size: 0.7rem;
        color: rgba(230, 236, 245, 0.5);
        overflow-wrap: anywhere;
    }

    label {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        font-size: 0.72rem;
        color: rgba(230, 236, 245, 0.7);
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

    .field-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.4rem;
    }

    .summary-row {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem;
        font-size: 0.72rem;
        color: rgba(230, 236, 245, 0.65);
    }

    .summary-row strong {
        color: #e6ecf5;
        overflow-wrap: anywhere;
        text-align: right;
    }

    .runtime-card {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(12, 18, 28, 0.6);
        padding: 0.5rem 0.6rem;
    }

    .panel-action-row {
        display: flex;
        gap: 0.4rem;
        margin-top: 0.2rem;
    }

    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 6px;
        border: 1px solid rgba(120, 205, 255, 0.35);
        background: rgba(58, 150, 221, 0.22);
        color: #dceeff;
        padding: 0.4rem 0.65rem;
        font-size: 0.78rem;
        cursor: pointer;
    }

    .action-btn.secondary {
        border-color: rgba(255, 255, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #e6ecf5;
    }

    .action-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
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

    .muted-text {
        margin: 0;
        font-size: 0.72rem;
        line-height: 1.4;
        color: rgba(230, 236, 245, 0.6);
    }

    code {
        font-family: ui-monospace, SFMono-Regular, monospace;
        font-size: 0.7rem;
    }

    .instance-list {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .instance-row {
        display: grid;
        grid-template-columns: 1fr auto;
        grid-template-areas: "main delete" "note delete";
        gap: 0.15rem 0.4rem;
        align-items: center;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: rgba(12, 18, 28, 0.55);
        padding: 0.35rem 0.45rem;
    }

    .instance-main {
        grid-area: main;
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.4rem;
    }

    .instance-id {
        font-family: ui-monospace, SFMono-Regular, monospace;
        font-size: 0.74rem;
        color: #e6ecf5;
    }

    .instance-tag {
        border-radius: 999px;
        padding: 0 0.32rem;
        font-family: system-ui, sans-serif;
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .instance-tag.sealed {
        background: rgba(160, 130, 255, 0.18);
        color: #cbbcff;
    }

    .instance-tag.fork {
        background: rgba(120, 205, 255, 0.16);
        color: #bfe6ff;
    }

    .instance-status {
        font-size: 0.7rem;
        color: rgba(230, 236, 245, 0.6);
        white-space: nowrap;
    }

    .instance-status.complete {
        color: #9ce6b4;
    }

    .instance-status.failed {
        color: #ffb4b4;
    }

    .instance-status.materializing,
    .instance-status.recording {
        color: #ffcf85;
    }

    .instance-note {
        grid-area: note;
        font-size: 0.66rem;
        line-height: 1.35;
        color: rgba(230, 236, 245, 0.5);
    }

    .instance-delete {
        grid-area: delete;
    }

    /* --- Step protocol editor --- */
    .hint-text {
        margin: 0 0 0.4rem;
        font-size: 0.68rem;
        line-height: 1.4;
        color: #7f91c8;
    }

    .step-list {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .step-row {
        border: 1px solid #24304f;
        border-radius: 6px;
        padding: 0.3rem 0.35rem;
        background: #101830;
    }

    /* Practice steps are recorded but excluded from training — make that visible
       while authoring, not just at run time. */
    .step-row.tutorial {
        border-color: #4a3d6b;
        background: #17142b;
    }

    .step-head {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.3rem;
    }

    .step-kind {
        font-size: 0.68rem;
        padding: 0.15rem 0.2rem;
    }

    .step-text {
        flex: 1 1 8rem;
        min-width: 6rem;
        font-size: 0.68rem;
    }

    .step-label {
        width: 6.5rem;
        font-size: 0.68rem;
    }

    .step-num {
        width: 3.2rem;
        font-size: 0.68rem;
    }

    .step-inline {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 0.2rem;
        font-size: 0.66rem;
        color: #7f91c8;
    }

    .step-inline input[type="checkbox"] {
        width: auto;
        margin: 0;
    }

    .step-actions {
        display: flex;
        gap: 0.1rem;
        margin-left: auto;
    }

    .step-media {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin-top: 0.25rem;
        padding-left: 0.1rem;
    }

    .step-media-url {
        width: 9rem;
        font-size: 0.64rem;
    }

    .step-add {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        margin-top: 0.35rem;
    }

    .step-add.nested {
        margin-top: 0.3rem;
        padding-left: 0.8rem;
    }

    .add-step-btn {
        display: flex;
        align-items: center;
        gap: 0.15rem;
        font-size: 0.64rem;
        padding: 0.18rem 0.35rem;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #16203c;
        color: #b9c8f0;
        cursor: pointer;
    }

    .add-step-btn:hover:not(:disabled) {
        border-color: #4f7ef7;
        color: #e4ecff;
    }

    .add-step-btn:disabled {
        opacity: 0.45;
        cursor: default;
    }

    .cue-thumb {
        display: block;
        max-width: 100%;
        max-height: 110px;
        margin: 0.25rem 0;
        border-radius: 6px;
        object-fit: contain;
        background: #0a0f1e;
    }

    .continue-wait {
        align-self: flex-start;
        background: #1d4ed8;
        border-color: #1d4ed8;
        color: #eff6ff;
        font-weight: 700;
    }

    .convert-steps {
        align-self: flex-start;
        font-size: 0.68rem;
    }
</style>
