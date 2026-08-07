<script lang="ts">
    // Timelined experiments and their recordings, on the IMU Experiment page.
    //
    // An experiment owns a board and mints an immutable instance per recording
    // (see the experiment-history work). This surface is for the two things you
    // want when a participant is in front of you: pick an experiment to run, or
    // pull up what you already recorded and take the data away.
    //
    // Recording itself deliberately stays in the Visual Programming editor. That
    // engine handles marker timing, wait-step clock holding, instance minting and
    // media stimuli, and duplicating it here would mean two implementations of
    // "what actually happened during a run" -- so Record hands off to the board
    // with the experiment already selected.
    import { onDestroy, onMount } from "svelte";
    import { Download, ExternalLink, RefreshCw } from "@lucide/svelte";
    import { StreamViewerWebSocket } from "../StreamViewer/websocket";
    import { getWebSocketUrl } from "../StreamViewer/config";
    import type {
        Experiment,
        SessionProtocol,
        StreamGraphDefinition,
        StreamGraphNode,
    } from "../StreamViewer/types";
    import {
        compileStepProtocol,
        isStepProtocol,
        protocolClasses,
        stepProtocolDurationMs,
        type StepProtocol,
    } from "../StreamViewer/experimentSteps";
    import { adlStepProtocol, ADL_PROTOCOL_ID } from "../AdlExperiment/tasks";

    let {
        // Streams the operator assigned to body positions in Stream Selection.
        // A built-in experiment is created with a source per assigned stream, so
        // it is recordable immediately after calibration.
        streamPositions = new Map<number, string>(),
    }: { streamPositions?: Map<number, string> } = $props();

    let ws: StreamViewerWebSocket | null = null;
    let connection = $state<"connecting" | "connected" | "disconnected">(
        "connecting",
    );
    let experiments = $state<Experiment[]>([]);
    let graphs = $state<StreamGraphDefinition[]>([]);
    let selectedExperimentId = $state<string | null>(null);
    let error = $state<string | null>(null);

    function refresh() {
        ws?.send({ action: "list_experiments", request_id: `exp:${Date.now()}` });
        ws?.send({
            action: "list_stream_graphs",
            request_id: `graphs:${Date.now()}`,
        });
    }

    onMount(() => {
        ws = new StreamViewerWebSocket(getWebSocketUrl(), {
            onConnectionChange: (state) => {
                connection = state as typeof connection;
                if (state === "connected") {
                    error = null;
                    refresh();
                }
            },
            onExperimentList: (message) => {
                experiments = message.experiments ?? [];
                if (
                    selectedExperimentId &&
                    !experiments.some(
                        (e) => e.experiment_id === selectedExperimentId,
                    )
                ) {
                    selectedExperimentId = null;
                }
            },
            onStreamGraphList: (message) => {
                graphs = message.graphs ?? [];
            },
            onError: (message) => {
                error = message?.message ?? "Unknown backend error";
            },
        });
        ws.connect();
    });

    onDestroy(() => {
        ws?.disconnect();
        ws = null;
    });

    const selected = $derived(
        experiments.find((e) => e.experiment_id === selectedExperimentId) ?? null,
    );

    /** Recordings for an experiment, newest first. */
    function instancesFor(experimentId: string): StreamGraphDefinition[] {
        return graphs
            .filter((g) => g.experiment_id === experimentId && !!g.instance_id)
            .sort((a, b) => (b.created_at_us ?? 0) - (a.created_at_us ?? 0));
    }

    /** A one-line description of what the protocol will do. */
    function protocolSummary(experiment: Experiment): string {
        const protocol = experiment.protocol as unknown;
        if (isStepProtocol(protocol)) {
            const steps = (protocol as StepProtocol).steps ?? [];
            const classes = protocolClasses(protocol as StepProtocol);
            return `${steps.length} step${steps.length === 1 ? "" : "s"}${
                classes.length > 0 ? ` · ${classes.join(", ")}` : ""
            }`;
        }
        const legacy = protocol as { classes?: string[]; repetitions?: number };
        const classes = legacy?.classes ?? [];
        return classes.length > 0
            ? `${classes.length} classes × ${legacy?.repetitions ?? 1} · ${classes.join(", ")}`
            : "No protocol yet";
    }

    function formatWindow(startUs?: number | null, endUs?: number | null) {
        if (!startUs) return "—";
        const start = new Date(startUs / 1000);
        const seconds = endUs ? Math.round((endUs - startUs) / 1_000_000) : null;
        const duration =
            seconds === null
                ? ""
                : seconds < 60
                  ? ` · ${seconds}s`
                  : ` · ${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
        return `${start.toLocaleString()}${duration}`;
    }

    /** Download URL for one materialised artifact of an instance. */
    function artifactUrl(graphId: string, path: string) {
        const params = new URLSearchParams({ graph_id: graphId, path });
        return `/api/instances/artifact?${params}`;
    }

    /** Every downloadable artifact of an instance, data files and markers alike. */
    function artifactsOf(instance: StreamGraphDefinition) {
        const recording = instance.recording as
            | {
                  artifacts?: {
                      data?: { path?: string; stream_id?: string; rows?: number }[];
                      markers?: { path?: string; count?: number }[];
                  };
              }
            | undefined;
        const artifacts = recording?.artifacts;
        const out: { label: string; path: string; detail: string }[] = [];
        for (const item of artifacts?.data ?? []) {
            if (!item.path) continue;
            out.push({
                label: item.path.split("/").pop() ?? item.path,
                path: item.path,
                detail: item.rows != null ? `${item.rows} rows` : "data",
            });
        }
        for (const item of artifacts?.markers ?? []) {
            if (!item.path) continue;
            out.push({
                label: item.path.split("/").pop() ?? item.path,
                path: item.path,
                detail: item.count != null ? `${item.count} markers` : "markers",
            });
        }
        return out;
    }

    // --- Built-in experiments ---------------------------------------------
    const builtIns = $derived([
        (() => {
            const protocol = adlStepProtocol();
            const schedule = compileStepProtocol(protocol);
            return {
                id: ADL_PROTOCOL_ID,
                label: "ADL tasks",
                description:
                    "The original hard-coded activities-of-daily-living " +
                    "sequence: mime each everyday task in turn, with a get-ready " +
                    "prompt and a rest between.",
                protocol,
                cues: schedule.filter((c) => c.phase === "hold").length,
                durationS: Math.round(stepProtocolDurationMs(schedule) / 1000),
            };
        })(),
    ]);

    let creating = $state<string | null>(null);

    /**
     * Create a real experiment from a built-in protocol, together with a board
     * carrying one source per assigned stream and a markers node -- otherwise the
     * experiment would exist with nothing to record from.
     */
    function createFromBuiltIn(builtIn: (typeof builtIns)[number]) {
        if (!ws || creating) return;
        creating = builtIn.id;
        error = null;
        const stamp = Date.now();
        const boardId = `${builtIn.id}-board-${stamp}`;
        const experimentId = `${builtIn.id}-${stamp}`;

        const assigned = [...streamPositions.entries()];
        const nodes: StreamGraphNode[] = assigned.map(
            ([streamId, position], index) => ({
                id: `source/${streamId}`,
                kind: "stream_source" as const,
                label: position && position !== "N/A" ? position : String(streamId),
                position: { x: 120, y: 80 + index * 150 },
                stream_id: String(streamId),
                schema_name: "NatImuBulkDataSchema",
                output_port_ids: ["data"],
            }),
        );
        nodes.push({
            id: `markers/${stamp}`,
            kind: "markers" as const,
            label: "Markers",
            position: { x: 520, y: 80 },
            output_port_ids: ["markers"],
        });

        const graph = {
            graph_version: 1 as const,
            graph_id: boardId,
            label: `${builtIn.label} — ${new Date(stamp).toLocaleDateString()}`,
            description: builtIn.description,
            notes: [],
            nodes,
            edges: [],
        };

        // Messages are processed in order on one connection, so the board exists
        // by the time the experiment referencing it is saved. editor_metadata is
        // sent too so the Visual Programming editor loads this exact tree.
        ws.send({
            action: "save_stream_graph",
            graph: { ...graph, editor_metadata: graph },
            request_id: `builtin-graph:${stamp}`,
        });
        ws.send({
            action: "save_experiment",
            experiment: {
                experiment_id: experimentId,
                label: builtIn.label,
                participant_id: "",
                notes: "",
                live_graph_id: boardId,
                created_at_us: stamp * 1000,
                updated_at_us: stamp * 1000,
                // A StepProtocol, which Experiment.protocol declares as
                // SessionProtocol; the read sites discriminate with
                // isStepProtocol. See the note on that field.
                protocol: builtIn.protocol as unknown as SessionProtocol,
            },
            request_id: `builtin-exp:${stamp}`,
        });

        // The list refresh is what confirms it landed.
        setTimeout(() => {
            refresh();
            selectedExperimentId = experimentId;
            creating = null;
        }, 600);
    }

    /** Open the Visual Programming board for this experiment, ready to record. */
    function recordExperiment(experiment: Experiment) {
        const board = experiment.live_graph_id;
        window.location.hash = board
            ? `#/VisualProgramming?board=${encodeURIComponent(board)}`
            : "#/VisualProgramming";
    }
</script>

<div class="experiment-library">
    <div class="library-header">
        <h3>Experiments</h3>
        <button
            type="button"
            class="ghost-btn"
            onclick={refresh}
            title="Reload experiments and recordings"
            disabled={connection !== "connected"}
        >
            <RefreshCw size={14} />
            Refresh
        </button>
    </div>

    {#if connection !== "connected"}
        <p class="note">
            {connection === "connecting"
                ? "Connecting to the backend…"
                : "Disconnected from the backend."}
        </p>
    {:else if error}
        <p class="note error">{error}</p>
    {:else}
        <div class="builtin-row">
            <p class="eyebrow">Start from a built-in experiment</p>
            {#each builtIns as builtIn}
                <div class="builtin">
                    <div class="builtin-main">
                        <strong>{builtIn.label}</strong>
                        <span class="experiment-meta"
                            >{builtIn.cues} tasks · ~{Math.round(
                                builtIn.durationS / 60,
                            )} min</span
                        >
                        <span class="note">{builtIn.description}</span>
                    </div>
                    <button
                        type="button"
                        class="primary-btn"
                        disabled={creating !== null || streamPositions.size === 0}
                        title={streamPositions.size === 0
                            ? "Assign at least one stream to a body position under Stream Selection first"
                            : "Create this experiment with a board for the streams you assigned"}
                        onclick={() => createFromBuiltIn(builtIn)}
                    >
                        {creating === builtIn.id ? "Creating…" : "Create"}
                    </button>
                </div>
            {/each}
            {#if streamPositions.size === 0}
                <p class="note">
                    Assign streams to body positions under Stream Selection to
                    create one — the new experiment gets a source per assigned
                    board.
                </p>
            {/if}
        </div>
    {/if}

    {#if connection === "connected" && !error && experiments.length === 0}
        <p class="note">
            No experiments yet. Create one from a built-in above, or build your own
            in Visual Programming.
        </p>
    {:else if connection === "connected" && !error}
        <div class="library-body">
            <ul class="experiment-list">
                {#each experiments as experiment (experiment.experiment_id)}
                    {@const recordings = instancesFor(experiment.experiment_id)}
                    <li>
                        <button
                            type="button"
                            class="experiment-item"
                            class:selected={experiment.experiment_id ===
                                selectedExperimentId}
                            onclick={() =>
                                (selectedExperimentId =
                                    experiment.experiment_id ===
                                    selectedExperimentId
                                        ? null
                                        : experiment.experiment_id)}
                        >
                            <span class="experiment-name"
                                >{experiment.label ||
                                    experiment.experiment_id}</span
                            >
                            <span class="experiment-meta"
                                >{protocolSummary(experiment)}</span
                            >
                            <span class="recording-count"
                                >{recordings.length} recording{recordings.length ===
                                1
                                    ? ""
                                    : "s"}</span
                            >
                        </button>
                    </li>
                {/each}
            </ul>

            {#if selected}
                {@const recordings = instancesFor(selected.experiment_id)}
                <div class="experiment-detail">
                    <div class="detail-header">
                        <div>
                            <strong>{selected.label || selected.experiment_id}</strong>
                            <span class="detail-sub"
                                >{protocolSummary(selected)}</span
                            >
                        </div>
                        <button
                            type="button"
                            class="primary-btn"
                            onclick={() => recordExperiment(selected)}
                            title="Open this experiment's board in Visual Programming to run it"
                        >
                            <ExternalLink size={14} />
                            Record
                        </button>
                    </div>
                    {#if selected.participant_id}
                        <p class="note">Participant: {selected.participant_id}</p>
                    {/if}

                    <p class="eyebrow">Past recordings</p>
                    {#if recordings.length === 0}
                        <p class="note">
                            Nothing recorded yet. Press Record to run it.
                        </p>
                    {:else}
                        <ul class="recording-list">
                            {#each recordings as instance (instance.graph_id)}
                                {@const status =
                                    instance.recording?.status ?? "unknown"}
                                {@const files = artifactsOf(instance)}
                                <li class="recording">
                                    <div class="recording-head">
                                        <strong>{instance.instance_id}</strong>
                                        <span class={`status ${status}`}>{status}</span>
                                        <span class="recording-when">
                                            {formatWindow(
                                                instance.recording?.window_start_us,
                                                instance.recording?.window_end_us,
                                            )}
                                        </span>
                                    </div>
                                    {#if files.length === 0}
                                        <p class="note">
                                            {status === "complete"
                                                ? "Sealed, but no artifacts are listed."
                                                : "No artifacts yet."}
                                        </p>
                                    {:else}
                                        <div class="artifact-row">
                                            {#each files as file}
                                                <a
                                                    class="artifact-link"
                                                    href={artifactUrl(
                                                        instance.graph_id,
                                                        file.path,
                                                    )}
                                                    download
                                                    title={`Download ${file.label}`}
                                                >
                                                    <Download size={12} />
                                                    {file.label}
                                                    <span class="artifact-detail"
                                                        >{file.detail}</span
                                                    >
                                                </a>
                                            {/each}
                                        </div>
                                    {/if}
                                </li>
                            {/each}
                        </ul>
                    {/if}
                </div>
            {:else}
                <p class="note detail-placeholder">
                    Select an experiment to see its recordings.
                </p>
            {/if}
        </div>
    {/if}
</div>

<style>
    .experiment-library {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        font-size: 0.86rem;
    }

    .library-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .library-header h3 {
        margin: 0;
        font-size: 1rem;
    }

    .builtin-row {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #e4e4e7;
    }

    .builtin {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        border: 1px solid #d4d4d8;
        border-radius: 6px;
        padding: 0.45rem 0.55rem;
    }

    .builtin-main {
        display: flex;
        flex-direction: column;
        gap: 0.1rem;
    }

    .library-body {
        display: grid;
        grid-template-columns: minmax(14rem, 20rem) 1fr;
        gap: 1rem;
        align-items: start;
    }

    .experiment-list,
    .recording-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .experiment-item {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 0.1rem;
        text-align: left;
        padding: 0.45rem 0.55rem;
        border: 1px solid #d4d4d8;
        border-radius: 6px;
        background: transparent;
        cursor: pointer;
    }

    .experiment-item:hover {
        border-color: #4f7ef7;
    }

    .experiment-item.selected {
        border-color: #4f7ef7;
        box-shadow: inset 0 0 0 1px #4f7ef7;
    }

    .experiment-name {
        font-weight: 600;
    }

    .experiment-meta,
    .recording-count,
    .detail-sub,
    .artifact-detail {
        font-size: 0.74rem;
        opacity: 0.7;
    }

    .detail-sub {
        margin-left: 0.5rem;
    }

    .experiment-detail {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
    }

    .detail-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
    }

    .eyebrow {
        margin: 0.3rem 0 0;
        font-size: 0.7rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        opacity: 0.65;
    }

    .recording {
        border: 1px solid #d4d4d8;
        border-radius: 6px;
        padding: 0.45rem 0.55rem;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .recording-head {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .recording-when {
        margin-left: auto;
        font-size: 0.74rem;
        opacity: 0.7;
    }

    .status {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 0.05rem 0.35rem;
        border-radius: 999px;
        border: 1px solid currentColor;
        opacity: 0.85;
    }

    .status.complete {
        color: #15803d;
    }

    .status.failed {
        color: #b91c1c;
    }

    .artifact-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
    }

    .artifact-link {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.76rem;
        padding: 0.2rem 0.45rem;
        border: 1px solid #d4d4d8;
        border-radius: 999px;
        text-decoration: none;
        color: inherit;
    }

    .artifact-link:hover {
        border-color: #4f7ef7;
    }

    .note {
        margin: 0;
        font-size: 0.8rem;
        opacity: 0.75;
    }

    .note.error {
        color: #b91c1c;
        opacity: 1;
    }

    .detail-placeholder {
        padding-top: 0.5rem;
    }

    .primary-btn,
    .ghost-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.8rem;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        border: 1px solid #d4d4d8;
        background: transparent;
        cursor: pointer;
    }

    .primary-btn {
        border-color: #1d4ed8;
        background: #1d4ed8;
        color: #eff6ff;
        font-weight: 600;
    }

    .ghost-btn:disabled {
        opacity: 0.5;
        cursor: default;
    }
</style>
