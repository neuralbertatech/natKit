<script lang="ts">
    // Experiment status card (experiment-authoring-ux-rework, Phase 2).
    //
    // The experiment used to be a node you dropped on the canvas; then it became
    // a first-class object authored entirely in this side panel — which crammed
    // a 30-step protocol editor into a 320px strip. Authoring now lives in the
    // ExperimentDesigner overlay ("Edit protocol"); this panel is the OPERATOR
    // surface: bind/create an experiment, Record/Stop, watch the live cue, and
    // review the recorded history. The participant is NOT here — it belongs to the
    // run, so Record asks for it (TEC-NATKIT-55).
    import {
        CircleDot,
        Pencil,
        Plus,
        Square,
        Trash2,
        Unlink,
    } from "@lucide/svelte";
    import type {
        Experiment,
        Workspace,
        SessionProtocol,
        StreamGraphDefinition,
    } from "../StreamViewer/types";
    import type { EmgCueEvent } from "../StreamViewer/experiment";
    import {
        compileStepProtocol,
        isStepProtocol,
        protocolClasses,
        stepProtocolDurationMs,
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
        // Workspaces (TEC-NATKIT-56): filing this experiment. Moving it takes its
        // bound board with it — save_experiment stamps the board's workspace_id —
        // so this control moves BOTH halves of the binding at once.
        workspaces: Workspace[];
        selectedWorkspaceId: string | null;
        // Opens the ExperimentDesigner overlay, where the protocol is authored.
        onEditProtocol: () => void;
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
        workspaces,
        selectedWorkspaceId,
        onEditProtocol,
        onDelete,
        onRecord,
        onStop,
        onContinue,
    }: Props = $props();

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

    const protocolClassList = $derived(
        stepProtocol
            ? protocolClasses(stepProtocol)
            : (bound?.protocol?.classes ?? []),
    );

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
            <span>Workspace</span>
            <select
                value={bound.workspace_id || ""}
                onchange={(event) =>
                    onPatch({
                        workspace_id: (event.currentTarget as HTMLSelectElement)
                            .value,
                    })}
            >
                <option value="">Unfiled</option>
                {#each workspaces as workspace}
                    <option value={workspace.workspace_id}>
                        {workspace.label || workspace.workspace_id}
                    </option>
                {/each}
            </select>
        </label>
        {#if (bound.workspace_id || null) !== selectedWorkspaceId}
            <!-- Moving an experiment out of the workspace in view makes it (and
                 its board) leave the lists on screen. Saying so beats it
                 seeming to vanish. -->
            <p class="hint-text">
                Moving this experiment takes its bound board with it, and both
                leave the workspace you are viewing.
            </p>
        {/if}

        <!-- No participant field: it belongs to the RUN, and Record asks for it
             (TEC-NATKIT-55). A field here could only ever name the most recent
             person, so one procedure recording a cohort attributed every run to
             whoever was typed last — and editing it retroactively reassigned the
             runs already recorded. -->
        <p class="hint-text">
            Participant is chosen when you press Record, so one experiment can
            record a whole cohort.
        </p>
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
            <div class="protocol-card">
                <div class="protocol-main">
                    <strong>{protocol.label || "Untitled protocol"}</strong>
                    <span class="hint-text">
                        {#if stepSummary}
                            {stepSummary.steps} steps · ~{stepSummary.durationS}s{stepSummary.waits >
                            0
                                ? ` · ${stepSummary.waits} wait${
                                      stepSummary.waits > 1 ? "s" : ""
                                  }`
                                : ""}
                        {:else if summary}
                            {summary.holdCues} cues · ~{summary.durationS}s
                        {:else}
                            no schedule yet
                        {/if}
                    </span>
                    <span class="hint-text">
                        Classes: {protocolClassList.join(", ") || "none"}
                    </span>
                    {#if stepSummary && stepSummary.tutorialCues > 0}
                        <span class="hint-text">
                            {stepSummary.tutorialCues} practice cue{stepSummary.tutorialCues >
                            1
                                ? "s"
                                : ""} excluded from training
                        </span>
                    {/if}
                </div>
                <button
                    type="button"
                    class="action-btn secondary edit-protocol"
                    onclick={onEditProtocol}
                    title="Open the protocol designer"
                >
                    <Pencil size={13} />
                    Edit protocol
                </button>
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

        <!-- Sticky so Record never scrolls out of reach under a long history. -->
        <div class="panel-action-row record-footer">
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

    .hint-text {
        margin: 0;
        font-size: 0.68rem;
        line-height: 1.4;
        color: #7f91c8;
    }

    /* The protocol at a glance, with the designer one click away. */
    .protocol-card {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        border-radius: 8px;
        border: 1px solid #24304f;
        background: rgba(12, 18, 28, 0.6);
        padding: 0.5rem 0.6rem;
    }

    .protocol-main {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
    }

    .protocol-main strong {
        font-size: 0.8rem;
        color: #e6ecf5;
    }

    .edit-protocol {
        align-self: flex-start;
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

    .record-footer {
        position: sticky;
        bottom: 0;
        z-index: 2;
        margin: 0 -0.85rem -0.85rem;
        padding: 0.55rem 0.85rem;
        background: linear-gradient(
            to top,
            rgba(11, 16, 32, 0.97) 65%,
            rgba(11, 16, 32, 0)
        );
        border-top: 1px solid #24304f;
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
</style>
