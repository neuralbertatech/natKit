<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { router } from "tinro";
    import {
        StreamViewerWebSocket,
        type ConnectionState,
    } from "../StreamViewer/websocket";
    import { getWebSocketUrl } from "../StreamViewer/config";
    import StreamGraphEditor from "./StreamGraphEditor.svelte";
    import type {
        StreamInfo,
        StreamListMessage,
        TransformCapability,
        NodeCatalogEntry,
        NodeCatalogMessage,
        ErrorMessage,
        StreamGraphDefinition,
        StreamGraphListMessage,
        StreamGraphSavedMessage,
        Profile,
        ProfileListMessage,
        ProfileSavedMessage,
        ProfileDeletedMessage,
        Workspace,
        WorkspaceListMessage,
        WorkspaceSavedMessage,
        WorkspaceDeletedMessage,
        Experiment,
        ExperimentListMessage,
        ExperimentSavedMessage,
        ExperimentDeletedMessage,
        ExperimentInstanceMessage,
        StreamGraphDeletedMessage,
        StreamGraphForkedMessage,
        ExperimentInstanceVerificationMessage,
        DeviceCommandResultMessage,
        InstanceReplayMessage,
        StreamGraphStatusMessage,
        StreamGraphStatusSummary,
        StreamGraphValidationMessage,
        StreamGraphDiagnostic,
        StreamGraphStartedMessage,
        StreamGraphStoppedMessage,
        ImuDataMessage,
        ImuBulkDataMessage,
        ImuSample,
        MuseDataMessage,
        MuseBulkDataMessage,
        MuseSample,
        EmgDataMessage,
        BufferedEmgSample,
        MarkerMessage,
        BufferedMarkerEvent,
        StreamTimeMessage,
        DataSchemaDescriptor,
        LiveStreamData,
    } from "../StreamViewer/types";
    import type {
        RecordedRunSummary,
        ThreadSlotSummary,
    } from "../MlPipeline/types";
    import type { SessionPublishBundleInput } from "../StreamViewer/experiment";

    const STATUS_REFRESH_INTERVAL_MS = 500;
    const STREAM_GRAPH_REFRESH_INTERVAL_MS = 1000;

    let connectionState = $state<ConnectionState>("disconnected");
    let lastError = $state<string | null>(null);
    let availableStreams = $state<Record<string, StreamInfo>>({});
    // The node catalog is the single source of truth for available node types
    // (Phase 1). Transform capabilities are derived from it so the legacy
    // capability-shaped consumers keep working without a second fetch.
    let nodeCatalog = $state<NodeCatalogEntry[]>([]);
    const transformCapabilities = $derived<TransformCapability[]>(
        nodeCatalog
            .filter((entry) => entry.kind === "transform")
            .map((entry) => ({
                kind: entry.node_type,
                label: entry.label,
                description: entry.description,
                input_descriptor_paths: entry.input_descriptor_paths ?? [],
                input_mappings: entry.input_mappings ?? [],
                output_schema_name:
                    entry.output_schema_name ?? "NatSignalFrameDataSchemaV1",
                config_fields: entry.config_fields,
            })),
    );
    // Phase 5: latest ML train-job status + resulting model path (proxied from
    // the control plane over the same connection).
    let trainJobStatus = $state<string | null>(null);
    let trainModelPath = $state<string | null>(null);
    // Durable path to the self-describing live-inference bundle (Phase 2). This
    // is what an emg_gesture_classify node loads; auto-filled into the classify
    // node on job completion so the operator never pastes a path.
    let trainBundlePath = $state<string | null>(null);
    // Phase 6: validation accuracy from the last completed train job, surfaced
    // on the train node so the operator sees the number before going live.
    let trainAccuracy = $state<{
        family: string | null;
        mean_accuracy: number;
        min_accuracy: number;
        mean_coverage: number;
    } | null>(null);
    // Phase 4 (provenance edges): the last completed train job as a compact model
    // record. The editor associates it with the submitting train node so a
    // train→classify provenance edge can offer a re-selectable model dropdown.
    let completedTrainJob = $state<{
        job_id: string;
        bundle_path: string | null;
        model_path: string | null;
        family: string | null;
        accuracy: number | null;
        completed_at_us: number;
    } | null>(null);
    // Phase 5: compute thread slots the control plane advertises (a train job
    // must target one). Captured from proxied thread_slots pushes so submit can
    // auto-pick a slot — no manual slot selection in the walk-up flow.
    let mlThreadSlots = $state<ThreadSlotSummary[]>([]);
    let mlControlPlaneWorkerId = $state<string | null>(null);
    let mlControlPlanePrincipalId = $state<string | null>(null);
    // The selected workspace survives a reload: an operator mid-cohort who
    // refreshes should not silently land in a different one — or worse, in
    // Unfiled, where Record would be pointing at another study's board.
    const WORKSPACE_STORAGE_KEY = "natkit.vp.workspace";

    function readStoredWorkspace(): string | null {
        try {
            const stored = localStorage.getItem(WORKSPACE_STORAGE_KEY);
            return stored && stored.length > 0 ? stored : null;
        } catch {
            // Private-mode / blocked storage: fall back to Unfiled rather than
            // failing to mount the page.
            return null;
        }
    }

    function storeWorkspace(workspaceId: string | null) {
        try {
            if (workspaceId === null) {
                localStorage.removeItem(WORKSPACE_STORAGE_KEY);
            } else {
                localStorage.setItem(WORKSPACE_STORAGE_KEY, workspaceId);
            }
        } catch {
            // Non-fatal: the selection just won't survive the next reload.
        }
    }

    // ⚠️ FALSY, not `=== ""`. "Unfiled" arrives in two representations: an
    // experiment always serializes the key so an unfiled one reads `""`, while a
    // board only emits it when set so an unfiled one reads `undefined`. Comparing
    // against either literal silently drops half the unfiled records.
    function inWorkspace(
        member: { workspace_id?: string },
        workspaceId: string | null,
    ): boolean {
        const filed = member.workspace_id || null;
        return filed === workspaceId;
    }

    let streamGraphs = $state<StreamGraphDefinition[]>([]);
    // Phase 4: individual profiles (person -> saved classify graph).
    let profiles = $state<Profile[]>([]);
    // Experiments (experiment-history-snapshots-plan): first-class objects that
    // own a board + its recorded history. The protocol lives here now, not on a
    // node.
    let experiments = $state<Experiment[]>([]);
    // Workspaces (TEC-NATKIT-56): the container that scopes everything below, so
    // picking an experiment is not picking from every experiment ever made.
    let workspaces = $state<Workspace[]>([]);
    // Which one is in view. `null` is the Unfiled pseudo-workspace, which is
    // where everything that predates workspaces lives — a real view, not a
    // migration artifact, so it must stay usable rather than be special-cased
    // out of existence.
    let selectedWorkspaceId = $state<string | null>(readStoredWorkspace());
    // The workspace lens. Everything the editor sees is filtered through this, so
    // scoping lives in ONE place rather than at each consumer — a consumer that
    // forgot to filter would show another cohort's boards without saying so.
    //
    // Instances are deliberately NOT filtered out by workspace here: they follow
    // their experiment, and an instance whose experiment is in view belongs in
    // view with it.
    const visibleExperiments = $derived(
        experiments.filter((experiment) =>
            inWorkspace(experiment, selectedWorkspaceId),
        ),
    );
    const visibleGraphs = $derived(
        streamGraphs.filter((graph) => inWorkspace(graph, selectedWorkspaceId)),
    );
    const visibleProfiles = $derived(
        profiles.filter((profile) => inWorkspace(profile, selectedWorkspaceId)),
    );
    // How much is filed elsewhere, so the UI can say "3 boards in other
    // workspaces" instead of just appearing to have lost them.
    const hiddenCounts = $derived({
        experiments: experiments.length - visibleExperiments.length,
        graphs: streamGraphs.length - visibleGraphs.length,
        profiles: profiles.length - visibleProfiles.length,
    });

    // The instance currently being recorded (minted on Record, closed on Stop).
    // Held here rather than in the editor because materialization finishes
    // asynchronously and its result is BROADCAST, not returned to a caller.
    let recordingInstanceGraphId = $state<string | null>(null);
    // A freshly created fork the editor should open (cleared once it has).
    let forkedGraphToOpen = $state<string | null>(null);
    // Deep link: #/VisualProgramming?board=<graph_id> opens straight onto that
    // board. The IMU Experiment page's "Record" uses this to hand an experiment
    // over to the editor, which owns the recording engine. Reuses the editor's
    // existing "open this graph" channel rather than adding a second one.
    function boardFromLocation(): string | null {
        const hash = window.location.hash;
        const query = hash.slice(hash.indexOf("?") + 1);
        if (!hash.includes("?")) return null;
        const board = new URLSearchParams(query).get("board");
        return board && board.trim() ? board.trim() : null;
    }
    // The replay session in flight, if any (Phase 5). Held here because
    // materialization-style progress arrives as BROADCASTS from the replay thread,
    // not as replies.
    let activeReplay = $state<InstanceReplayMessage | null>(null);
    // Latest artifact-integrity check per instance graph id (Phase 4 review).
    let instanceVerifications = $state<
        Record<string, ExperimentInstanceVerificationMessage>
    >({});
    // Device commands: what is in flight, and the last answer per stream. Keyed
    // "<stream_id>:<command>" for pending, and by stream id for the result, so a
    // node shows the most recent thing its device said.
    let deviceCommandPending = $state<Record<string, boolean>>({});
    let deviceCommandResults = $state<
        Record<string, DeviceCommandResultMessage>
    >({});
    let streamGraphStatuses = $state<Record<string, StreamGraphStatusSummary>>(
        {},
    );
    // Phase 5: latest time-introspection reply per stream id (offset bounds +
    // offset_for_timestamp), used to resolve a replay start offset.
    let streamTimeExtents = $state<Record<string, StreamTimeMessage>>({});
    // Phase 6: recorded experiments (from natVR run discovery via the ML proxy).
    let recordedRuns = $state<RecordedRunSummary[]>([]);
    let latestStreamGraphDiagnostics = $state<StreamGraphDiagnostic[]>([]);
    let latestStreamGraphNodeDiagnostics = $state<
        Record<string, StreamGraphDiagnostic[]>
    >({});
    let latestStreamGraphEdgeDiagnostics = $state<
        Record<string, StreamGraphDiagnostic[]>
    >({});
    let lastStreamGraphRefreshAtMs = $state(0);
    let nowMs = $state(Date.now());

    let appliedDeepLink = false;
    let wsManager: StreamViewerWebSocket | null = null;
    let statusTimer: ReturnType<typeof setInterval> | null = null;

    // Raw sample data for the single stream currently open in a "viewer" node's
    // live data modal. Scoped to one stream at a time since only one modal can
    // be open; unlike the Stream Viewer page this connection is otherwise
    // control-plane only, so we subscribe/unsubscribe on demand instead of
    // buffering every available stream.
    const MAX_LIVE_BUFFER_SIZE = 100;
    // Per-stream live buffers keyed by stream id, so any number of inspectors can
    // be live at once (not just one). Ref-counted subscriptions let several
    // viewer nodes share a stream without one closing another's feed.
    //
    // $state.raw (NOT deep $state): the sample buffers are large and read on the
    // chart hot path (buildChartState iterates every sample × channel). A deep
    // proxy would route each of those element reads through Svelte's reactive
    // getter — profiling showed that proxy overhead dominating and growing with
    // buffer size (the progressive stutter). Raw state keeps the arrays plain;
    // we trigger reactivity by reassigning the map (cheap — a viewer's chart only
    // rebuilds when its own array reference changes).
    let liveStreams = $state.raw<Record<string, LiveStreamData>>({});
    const streamRefCounts = new Map<string, number>();

    // Ingest is decoupled from render: incoming frames accumulate in a plain
    // (non-reactive) per-stream buffer and are flushed into the reactive
    // liveStreams at a capped rate. A viewer's chart therefore redraws a few
    // times a second regardless of the stream's frame rate or how many viewers
    // are open, which is what keeps several heavy inline charts responsive.
    const LIVE_FLUSH_INTERVAL_MS = 200;
    interface PendingSamples {
        emg: BufferedEmgSample[];
        muse: MuseSample[];
        imu: ImuSample[];
        markers: BufferedMarkerEvent[];
    }
    const pendingByStream = new Map<string, PendingSamples>();
    let liveFlushTimer: ReturnType<typeof setInterval> | null = null;

    function pendingFor(streamId: string): PendingSamples {
        let pending = pendingByStream.get(streamId);
        if (!pending) {
            pending = { emg: [], muse: [], imu: [], markers: [] };
            pendingByStream.set(streamId, pending);
        }
        return pending;
    }

    function ensureLiveFlushTimer() {
        if (liveFlushTimer !== null) return;
        liveFlushTimer = setInterval(flushLiveStreams, LIVE_FLUSH_INTERVAL_MS);
    }

    function trimEmg(buffer: BufferedEmgSample[]): BufferedEmgSample[] {
        const maxHistoryMs = 20000;
        let retainedDurationMs = 0;
        let startIndex = buffer.length;
        while (startIndex > 0) {
            retainedDurationMs += buffer[startIndex - 1].frame_duration_ms;
            if (retainedDurationMs > maxHistoryMs && startIndex < buffer.length) {
                break;
            }
            startIndex -= 1;
        }
        return buffer.slice(startIndex);
    }

    function trimBounded<T>(buffer: T[]): T[] {
        return buffer.length > MAX_LIVE_BUFFER_SIZE
            ? buffer.slice(-MAX_LIVE_BUFFER_SIZE)
            : buffer;
    }

    // Merge each stream's pending frames into its buffer. Only the streams that
    // actually received frames get a fresh value object (new array reference), so
    // an unchanged stream keeps its identity and its viewer's chart doesn't
    // rebuild. We reassign liveStreams once at the end (raw state tracks
    // reassignment, not nested mutation).
    function flushLiveStreams() {
        let updated: Record<string, LiveStreamData> | null = null;
        for (const [streamId, pending] of pendingByStream) {
            const current = liveStreams[streamId];
            if (!current) {
                pendingByStream.delete(streamId);
                continue;
            }
            if (
                !pending.emg.length &&
                !pending.muse.length &&
                !pending.imu.length &&
                !pending.markers.length
            ) {
                continue;
            }
            let next: LiveStreamData = current;
            if (pending.emg.length) {
                next = {
                    ...next,
                    streamType: "emg",
                    emgSamples: trimEmg([...next.emgSamples, ...pending.emg]),
                };
                pending.emg.length = 0;
            }
            if (pending.muse.length) {
                next = {
                    ...next,
                    streamType: "muse",
                    museSamples: trimBounded([...next.museSamples, ...pending.muse]),
                };
                pending.muse.length = 0;
            }
            if (pending.imu.length) {
                next = {
                    ...next,
                    streamType: "imu",
                    imuSamples: trimBounded([...next.imuSamples, ...pending.imu]),
                };
                pending.imu.length = 0;
            }
            if (pending.markers.length) {
                next = {
                    ...next,
                    markers: trimBounded([...next.markers, ...pending.markers]),
                };
                pending.markers.length = 0;
            }
            if (updated === null) {
                updated = { ...liveStreams };
            }
            updated[streamId] = next;
        }
        if (updated !== null) {
            liveStreams = updated;
        }
    }
    // Friendly device name per stream (latest device_id seen). Persists beyond a
    // subscription so a source node can be briefly "sniffed" for its name and
    // then released without losing the label.
    let streamDeviceNames = $state<Record<string, string>>({});

    function emptyLiveStream(streamId: string): LiveStreamData {
        return {
            streamType: inferLiveStreamType(streamId) ?? null,
            emgSamples: [],
            museSamples: [],
            imuSamples: [],
            markers: [],
        };
    }

    function inferLiveStreamType(
        streamId: string,
    ): "imu" | "muse" | "emg" | undefined {
        const info = availableStreams[streamId];
        if (!info) {
            return undefined;
        }
        const schemaNames = info.topics.map((topic) => topic.schema_name);
        if (
            schemaNames.includes("ExgPillEmgDataSchemaV1") ||
            schemaNames.includes("ExgPillEmgTransformDataSchemaV1") ||
            schemaNames.includes("NatSignalFrameDataSchemaV1")
        ) {
            return "emg";
        }
        if (
            schemaNames.some(
                (schemaName) =>
                    schemaName === "NatMuseDataSchema" ||
                    schemaName === "NatMuseBulkDataSchema",
            )
        ) {
            return "muse";
        }
        if (
            schemaNames.some(
                (schemaName) =>
                    schemaName === "NatImuDataSchema" ||
                    schemaName === "NatImuBulkDataSchema",
            )
        ) {
            return "imu";
        }
        return undefined;
    }

    // Frame appenders only push into the non-reactive pending buffer (cheap); the
    // flush timer merges them into the reactive state at a capped rate.
    function addLiveImuSample(streamId: string, sample: ImuSample) {
        if (!streamRefCounts.has(streamId)) return;
        pendingFor(streamId).imu.push(sample);
    }

    function addLiveMuseSample(streamId: string, sample: MuseSample) {
        if (!streamRefCounts.has(streamId)) return;
        pendingFor(streamId).muse.push(sample);
    }

    function addLiveMarker(streamId: string, marker: BufferedMarkerEvent) {
        if (!streamRefCounts.has(streamId)) return;
        pendingFor(streamId).markers.push(marker);
    }

    function addLiveEmgSample(
        streamId: string,
        sample: BufferedEmgSample,
        deviceId?: string,
    ) {
        // Device name is a one-off, so update it immediately (cheap, rare).
        if (deviceId && streamDeviceNames[streamId] !== deviceId) {
            streamDeviceNames[streamId] = deviceId;
        }
        if (!streamRefCounts.has(streamId)) return;
        pendingFor(streamId).emg.push(sample);
    }

    function subscribeToStream(streamId: string) {
        const next = (streamRefCounts.get(streamId) ?? 0) + 1;
        streamRefCounts.set(streamId, next);
        if (next === 1) {
            liveStreams = { ...liveStreams, [streamId]: emptyLiveStream(streamId) };
            ensureLiveFlushTimer();
            wsManager?.subscribe([streamId]);
        }
    }

    function unsubscribeFromStream(streamId: string) {
        const next = (streamRefCounts.get(streamId) ?? 0) - 1;
        if (next > 0) {
            streamRefCounts.set(streamId, next);
            return;
        }
        streamRefCounts.delete(streamId);
        pendingByStream.delete(streamId);
        wsManager?.unsubscribe([streamId]);
        const { [streamId]: _removed, ...rest } = liveStreams;
        liveStreams = rest;
    }

    function sortExperiments(list: Experiment[]): Experiment[] {
        return [...list].sort(
            (left, right) =>
                (right.updated_at_us || 0) - (left.updated_at_us || 0) ||
                left.label.localeCompare(right.label),
        );
    }

    function formatNumber(num: number, decimals: number = 4): string {
        return num.toFixed(decimals);
    }

    function listStreamGraphs() {
        wsManager?.send({
            action: "list_stream_graphs",
            request_id: `stream-graphs:${Date.now()}`,
        });
    }

    function requestStreamGraphStatus(graphId: string) {
        lastStreamGraphRefreshAtMs = Date.now();
        if (wsManager?.getConnectionState() !== "connected") {
            return;
        }
        wsManager.send({
            action: "get_stream_graph_status",
            request_id: `stream-graph-status:${Date.now()}`,
            graph_id: graphId,
        });
    }

    function saveStreamGraph(graph: StreamGraphDefinition): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "save_stream_graph",
            request_id: `stream-graph-save:${Date.now()}`,
            graph,
        });
        return true;
    }

    // Phase 4: individual profiles.
    function listProfiles() {
        wsManager?.send({
            action: "list_profiles",
            request_id: `profiles:${Date.now()}`,
        });
    }

    function saveProfile(profile: Profile): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "save_profile",
            request_id: `profile-save:${Date.now()}`,
            profile,
        });
        return true;
    }

    function deleteProfile(participantId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "delete_profile",
            request_id: `profile-delete:${Date.now()}`,
            participant_id: participantId,
        });
        return true;
    }

    // Workspaces (TEC-NATKIT-56).
    function listWorkspaces() {
        wsManager?.send({
            action: "list_workspaces",
            request_id: `workspaces:${Date.now()}`,
        });
    }

    function saveWorkspace(workspace: Workspace): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "save_workspace",
            request_id: `workspace-save:${Date.now()}`,
            workspace,
        });
        return true;
    }

    // ⚠️ The contents SURVIVE. The backend un-files experiments, boards and
    // profiles rather than deleting them, so this moves a cohort to Unfiled — it
    // never destroys recorded history. The confirm copy has to say so, because
    // "delete workspace" reads like it takes everything with it.
    function deleteWorkspace(workspaceId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "delete_workspace",
            request_id: `workspace-delete:${Date.now()}`,
            workspace_id: workspaceId,
        });
        return true;
    }

    function selectWorkspace(workspaceId: string | null) {
        selectedWorkspaceId = workspaceId;
        storeWorkspace(workspaceId);
    }

    // Experiments. save_experiment doubles as the bind action: setting
    // `live_graph_id` makes the backend stamp `experiment_id` onto that board
    // (and clear it from any other), so the 1:1 pair is written in one place.
    function listExperiments() {
        wsManager?.send({
            action: "list_experiments",
            request_id: `experiments:${Date.now()}`,
        });
    }

    function saveExperiment(experiment: Experiment): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "save_experiment",
            request_id: `experiment-save:${Date.now()}`,
            experiment,
        });
        return true;
    }

    function deleteExperiment(experimentId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "delete_experiment",
            request_id: `experiment-delete:${Date.now()}`,
            experiment_id: experimentId,
        });
        return true;
    }

    // Instances (experiment-history-snapshots-plan, Phases 2 + 3). Recording mints
    // an immutable snapshot of the board welded to the data captured in its window.
    function startExperimentInstance(
        experimentId: string,
        windowStartUs: number,
        participantId: string,
        sensorPositions: { stream_id: string; position: string }[],
        // Non-null when the operator recorded through the calibration gate; the
        // text is the reason they were shown, so the run carries what was overridden
        // rather than just that something was.
        calibrationOverride: string | null,
    ): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "start_experiment_instance",
            request_id: `instance-start:${Date.now()}`,
            experiment_id: experimentId,
            participant_id: participantId,
            sensor_positions: sensorPositions,
            ...(calibrationOverride
                ? { calibration_override: calibrationOverride }
                : {}),
            window_start_us: windowStartUs,
        });
        return true;
    }

    function finishExperimentInstance(
        graphId: string,
        windowEndUs: number,
        completed: boolean,
    ): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "finish_experiment_instance",
            request_id: `instance-finish:${Date.now()}`,
            graph_id: graphId,
            window_end_us: windowEndUs,
            completed,
        });
        return true;
    }

    // Fork an instance into an editable copy (Phase 0's action, finally wired up).
    // The reply carries the new graph; the editor opens it so the user lands in the
    // copy they just asked for rather than having to find it.
    function forkStreamGraph(sourceGraphId: string, label?: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "fork_stream_graph",
            request_id: `graph-fork:${Date.now()}`,
            source_graph_id: sourceGraphId,
            ...(label ? { label } : {}),
        });
        return true;
    }

    function verifyExperimentInstance(graphId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "verify_experiment_instance",
            request_id: `instance-verify:${Date.now()}`,
            graph_id: graphId,
        });
        return true;
    }

    function deleteStreamGraph(graphId: string, force = false): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "delete_stream_graph",
            request_id: `graph-delete:${Date.now()}`,
            graph_id: graphId,
            force,
        });
        return true;
    }

    // Send a command to a device (EXECUTION_COMMAND) and wait for its answer on
    // the log channel. The backend does the correlating, so the reply that lands
    // here is already the device's own words.
    function sendDeviceCommand(streamId: string, command: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        // Keyed per stream+command so two buttons on the same node can be in
        // flight without one clearing the other's spinner.
        deviceCommandPending = {
            ...deviceCommandPending,
            [`${streamId}:${command}`]: true,
        };
        wsManager.send({
            action: "send_device_command",
            request_id: `device-command:${Date.now()}`,
            stream_id: streamId,
            command,
        });
        return true;
    }

    // Incremental reactivity (Phase 7): after a config edit is saved in a
    // running graph, restart only the affected node + its downstream subgraph.
    function restartStreamGraphNode(graphId: string, nodeId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "restart_stream_graph_node",
            request_id: `stream-graph-restart:${Date.now()}`,
            graph_id: graphId,
            node_id: nodeId,
        });
        return true;
    }

    // Publish a session's metadata + markers (Phase 4). Recording is driven
    // client-side by a session node; this forwards the bundle over the same
    // backend WebSocket that carries the graph protocol.
    function publishSessionBundle(payload: SessionPublishBundleInput): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "publish_session_bundle",
            request_id: payload.requestId,
            session_id: payload.sessionId,
            meta_records: payload.metaRecords,
            marker_events: payload.markerEvents,
        });
        return true;
    }

    // Track proxied ML control-plane messages for the train node (Phase 5).
    function handleMlControlPlaneMessage(message: unknown): void {
        const msg = message as {
            type?: string;
            status?: string;
            message?: string;
            error?: string;
            job_id?: string;
            report?: {
                model_path?: string | null;
                bundle_path?: string | null;
                selected_family?: string | null;
                selected_mean_accuracy?: number | null;
                selected_min_accuracy?: number | null;
                selected_mean_coverage?: number | null;
            } | null;
            runs?: RecordedRunSummary[];
            worker_id?: string;
            principal_id?: string | null;
            slots?: ThreadSlotSummary[];
        };
        if (msg.type === "thread_slots") {
            mlThreadSlots = msg.slots ?? [];
            mlControlPlaneWorkerId = msg.worker_id ?? null;
            mlControlPlanePrincipalId = msg.principal_id ?? null;
            return;
        }
        if (msg.type === "recorded_runs") {
            // Experiment library (Phase 6): recorded runs discovered by natVR's
            // reconstruct_session, surfaced through the ML proxy.
            recordedRuns = msg.runs ?? [];
            return;
        }
        if (msg.type === "job_accepted") {
            trainJobStatus = `queued (${msg.job_id ?? "job"})`;
        } else if (msg.type === "job_status") {
            trainJobStatus = `${msg.status ?? "?"}: ${msg.message ?? ""}`.trim();
            if (msg.status === "completed" && msg.report?.model_path) {
                trainModelPath = msg.report.model_path;
            }
            if (msg.status === "completed" && msg.report?.bundle_path) {
                trainBundlePath = msg.report.bundle_path;
            }
            if (
                msg.status === "completed" &&
                typeof msg.report?.selected_mean_accuracy === "number"
            ) {
                trainAccuracy = {
                    family: msg.report.selected_family ?? null,
                    mean_accuracy: msg.report.selected_mean_accuracy,
                    min_accuracy: msg.report.selected_min_accuracy ?? 0,
                    mean_coverage: msg.report.selected_mean_coverage ?? 0,
                };
            }
            if (msg.status === "completed" && msg.job_id) {
                completedTrainJob = {
                    job_id: msg.job_id,
                    bundle_path: msg.report?.bundle_path ?? null,
                    model_path: msg.report?.model_path ?? null,
                    family: msg.report?.selected_family ?? null,
                    accuracy:
                        typeof msg.report?.selected_mean_accuracy === "number"
                            ? msg.report.selected_mean_accuracy
                            : null,
                    completed_at_us: Date.now() * 1000,
                };
            }
        } else if (msg.type === "error") {
            trainJobStatus = `error: ${msg.error ?? msg.message ?? "unknown"}`;
        }
    }

    // Pick the least-busy compute thread slot the user may submit to. Returns
    // null if none are usable.
    function pickThreadSlot(): string | null {
        const usable = mlThreadSlots.filter((slot) => {
            const mode = slot.access_mode ?? "shared";
            if (mode === "shared") return true;
            return (
                !!mlControlPlanePrincipalId &&
                slot.dedicated_username === mlControlPlanePrincipalId
            );
        });
        if (usable.length === 0) return null;
        const busy = (slot: ThreadSlotSummary) =>
            (slot.queue_depth ?? 0) + (slot.running_job_count ?? 0);
        return [...usable].sort((a, b) => busy(a) - busy(b))[0]?.slot_id ?? null;
    }

    // Submit a train_validate job through the backend ML proxy (Phase 5).
    function submitTrainJob(config: import(
        "../StreamViewer/types"
    ).TrainNodeConfig): void {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return;
        }
        const trainInstances = config.train_instances ?? [];
        if (config.train_runs.length === 0 && trainInstances.length === 0) {
            trainJobStatus =
                "error: pick at least one recorded instance (or a run) to train on";
            return;
        }
        // Validation runs are optional — the model fits on the training runs
        // alone; eval only reports held-out accuracy + picks between families.
        const threadSlotId = pickThreadSlot();
        if (!threadSlotId) {
            trainJobStatus =
                "error: no compute slot available (waiting for the ML control plane / worker)";
            wsManager.sendMlAction({
                action: "list_thread_slots",
                request_id: crypto.randomUUID(),
            });
            return;
        }
        trainModelPath = null;
        trainBundlePath = null;
        trainAccuracy = null;
        trainJobStatus = "submitting…";
        wsManager.sendMlAction({
            action: "start_train_validate_job",
            request_id: crypto.randomUUID(),
            thread_slot_id: threadSlotId,
            train_runs: config.train_runs,
            eval_runs: config.eval_runs,
            // Instance ids go up as ids; the BACKEND swaps them for artifact paths
            // (it owns the instance store). Training then reads the recording's
            // Parquet off disk instead of reconstructing it from Kafka.
            ...(trainInstances.length ? { train_instances: trainInstances } : {}),
            ...(config.eval_instances?.length
                ? { eval_instances: config.eval_instances }
                : {}),
            families: config.families,
            ...(config.selected_fields.length
                ? { selected_fields: config.selected_fields }
                : {}),
            window_ms: config.window_ms,
            hop_ms: config.hop_ms,
            vote_windows: config.vote_windows,
            confidence_threshold: config.confidence_threshold,
            min_hold_windows: config.min_hold_windows,
            rest_gesture: config.rest_gesture,
            active_gesture: config.active_gesture,
        });
    }

    function validateStreamGraph(graph: StreamGraphDefinition): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "validate_stream_graph",
            request_id: `stream-graph-validate:${Date.now()}`,
            graph,
        });
        return true;
    }

    // Replay an instance: mint the scratch topics, then (once they exist) start the
    // graph bound to them so the whole pipeline runs over the recording.
    function startInstanceReplay(
        graphId: string,
        mode: "review" | "recompute",
        speed: number,
    ): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "start_instance_replay",
            request_id: `replay-start:${Date.now()}`,
            graph_id: graphId,
            mode,
            speed,
        });
        return true;
    }

    function stopInstanceReplay(replayId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            return false;
        }
        wsManager.send({
            action: "stop_instance_replay",
            request_id: `replay-stop:${Date.now()}`,
            replay_id: replayId,
        });
        return true;
    }

    // A replay's scratch topics are created moments before it reports "started",
    // and getAllStreams() reads Kafka metadata that takes a few seconds to include
    // them — so the stream list fetched at that instant comes back without them.
    // Viewers resolve their renderer from the DESCRIPTOR in that list (the
    // channel-frame renderer is descriptor-gated; a frame shape hint is not
    // enough), so until the replayed streams are listed a viewer subscribes,
    // receives the replayed records, and still shows "Waiting for data on this
    // stream…". Replay progress messages are far too sparse to converge on (two in
    // the first fifteen seconds), hence a short bounded poll that stops as soon as
    // every replayed stream is known.
    let replayStreamPollTimer: ReturnType<typeof setTimeout> | null = null;

    function awaitReplayStreams(streamIds: string[], attempt = 0): void {
        if (replayStreamPollTimer) {
            clearTimeout(replayStreamPollTimer);
            replayStreamPollTimer = null;
        }
        const missing = streamIds.filter((id) => !(id in availableStreams));
        if (missing.length === 0 || attempt >= 8) {
            return;
        }
        wsManager?.requestStreamList();
        replayStreamPollTimer = setTimeout(
            () => awaitReplayStreams(streamIds, attempt + 1),
            1200,
        );
    }

    function startStreamGraph(
        graphId: string,
        startOffset?: number,
        replayId?: string,
    ): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        // Starting a graph makes the backend synchronously create Kafka topics
        // and spin up transform workers before it replies with
        // stream_graph_started — that round trip can take many seconds. Flip the
        // local run state to "starting" immediately so the UI reacts to the
        // click instead of looking frozen until the reply lands.
        const existing = streamGraphStatuses[graphId];
        streamGraphStatuses = {
            ...streamGraphStatuses,
            [graphId]: {
                graph_id: graphId,
                run_state: "starting",
                active_run_id: existing?.active_run_id ?? null,
                node_statuses: existing?.node_statuses ?? {},
            },
        };
        wsManager.send({
            action: "start_stream_graph",
            request_id: `stream-graph-start:${Date.now()}`,
            graph_id: graphId,
            ...(startOffset !== undefined ? { start_offset: startOffset } : {}),
            ...(replayId ? { replay_id: replayId } : {}),
        });
        return true;
    }

    function queryStreamTime(
        streamId: string,
        timestampUs?: number,
        requestId?: string,
    ): void {
        wsManager?.queryStreamTime(streamId, timestampUs, requestId);
    }

    // Ask the control plane (via the ML proxy) for recorded experiments; the
    // reply arrives as a recorded_runs message (Phase 6).
    function requestRecordedRuns(): void {
        if (wsManager?.getConnectionState() !== "connected") return;
        wsManager.sendMlAction({
            action: "list_recorded_runs",
            request_id: crypto.randomUUID(),
        });
    }

    function stopStreamGraph(graphId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "stop_stream_graph",
            request_id: `stream-graph-stop:${Date.now()}`,
            graph_id: graphId,
        });
        return true;
    }

    // Cross-page link: open the live view of a stream on the Stream Viewer page.
    function inspectStream(streamId: string) {
        router.goto(`/StreamViewer?inspect=${encodeURIComponent(streamId)}`);
    }

    onMount(() => {
        statusTimer = setInterval(() => {
            nowMs = Date.now();
            if (
                wsManager?.getConnectionState() === "connected" &&
                nowMs - lastStreamGraphRefreshAtMs >=
                    STREAM_GRAPH_REFRESH_INTERVAL_MS
            ) {
                const graphIds = streamGraphs
                    .map((graph) => graph.graph_id)
                    .filter((graphId) => graphId.length > 0);
                for (const graphId of graphIds) {
                    requestStreamGraphStatus(graphId);
                }
                lastStreamGraphRefreshAtMs = nowMs;
            }
        }, STATUS_REFRESH_INTERVAL_MS);

        wsManager = new StreamViewerWebSocket(getWebSocketUrl(), {
            onConnectionChange: (state) => {
                connectionState = state;
                if (state === "connected") {
                    lastError = null;
                    wsManager?.send({
                        action: "list_node_catalog",
                        request_id: `node-catalog:${Date.now()}`,
                    });
                    listStreamGraphs();
                    listProfiles();
                    listExperiments();
                    listWorkspaces();
                    // Ask the control plane (via the proxy) for compute slots so a
                    // train submit can auto-pick one; periodic pushes keep it fresh.
                    wsManager?.sendMlAction({
                        action: "list_thread_slots",
                        request_id: `thread-slots:${Date.now()}`,
                    });
                    // Re-issue every live subscription that was dropped because
                    // the socket wasn't open yet (subscribeToStream fires without
                    // waiting for the connection), or lost across a reconnect.
                    const activeStreamIds = Array.from(streamRefCounts.keys());
                    if (activeStreamIds.length > 0) {
                        wsManager?.subscribe(activeStreamIds);
                    }
                }
            },
            onStreamList: (message: StreamListMessage) => {
                availableStreams = message.streams;
            },
            onNodeCatalog: (message: NodeCatalogMessage) => {
                nodeCatalog = message.nodes;
            },
            onMlControlPlane: (message: unknown) => {
                handleMlControlPlaneMessage(message);
            },
            onStreamGraphList: (message: StreamGraphListMessage) => {
                // Honour ?board= on the first listing only; after that the user's
                // selection is theirs.
                if (!appliedDeepLink) {
                    const wanted = boardFromLocation();
                    if (wanted && (message.graphs ?? []).some((g) => g.graph_id === wanted)) {
                        forkedGraphToOpen = wanted;
                    }
                    appliedDeepLink = true;
                }
                streamGraphs = message.graphs;
                streamGraphStatuses = message.statuses;
            },
            onStreamGraphSaved: (message: StreamGraphSavedMessage) => {
                const remainingGraphs = streamGraphs.filter(
                    (graph) => graph.graph_id !== message.graph_id,
                );
                streamGraphs = [...remainingGraphs, message.graph].sort(
                    (left, right) => left.label.localeCompare(right.label),
                );
            },
            onProfileList: (message: ProfileListMessage) => {
                profiles = [...message.profiles].sort((left, right) =>
                    left.display_name.localeCompare(right.display_name),
                );
            },
            onProfileSaved: (message: ProfileSavedMessage) => {
                const remaining = profiles.filter(
                    (profile) =>
                        profile.participant_id !== message.participant_id,
                );
                profiles = [...remaining, message.profile].sort((left, right) =>
                    left.display_name.localeCompare(right.display_name),
                );
            },
            onProfileDeleted: (message: ProfileDeletedMessage) => {
                profiles = profiles.filter(
                    (profile) =>
                        profile.participant_id !== message.participant_id,
                );
            },
            onWorkspaceList: (message: WorkspaceListMessage) => {
                workspaces = [...message.workspaces].sort((left, right) =>
                    left.label.localeCompare(right.label),
                );
                // A stored selection pointing at a workspace that no longer
                // exists would scope every list to nothing and look like data
                // loss. Fall back to Unfiled instead.
                if (
                    selectedWorkspaceId !== null &&
                    !workspaces.some(
                        (workspace) =>
                            workspace.workspace_id === selectedWorkspaceId,
                    )
                ) {
                    selectWorkspace(null);
                }
            },
            onWorkspaceSaved: (message: WorkspaceSavedMessage) => {
                const remaining = workspaces.filter(
                    (workspace) =>
                        workspace.workspace_id !== message.workspace_id,
                );
                workspaces = [...remaining, message.workspace].sort(
                    (left, right) => left.label.localeCompare(right.label),
                );
            },
            onWorkspaceDeleted: (message: WorkspaceDeletedMessage) => {
                workspaces = workspaces.filter(
                    (workspace) =>
                        workspace.workspace_id !== message.workspace_id,
                );
                if (selectedWorkspaceId === message.workspace_id) {
                    selectWorkspace(null);
                }
                // Its members were un-filed server-side, so the local copies of
                // all three lists are stale.
                listExperiments();
                listStreamGraphs();
                listProfiles();
            },
            onExperimentList: (message: ExperimentListMessage) => {
                experiments = sortExperiments(message.experiments);
            },
            onExperimentSaved: (message: ExperimentSavedMessage) => {
                const remaining = experiments.filter(
                    (experiment) =>
                        experiment.experiment_id !== message.experiment_id,
                );
                experiments = sortExperiments([...remaining, message.experiment]);
                // The save also (re)bound a board, so the graph records the
                // backend just rewrote are now stale locally.
                listStreamGraphs();
            },
            onExperimentInstance: (message: ExperimentInstanceMessage) => {
                // Upsert into the graph list: an instance IS a graph record, so the
                // board picker's instance filter and the history both read it from
                // there rather than from a second list that could disagree.
                const remaining = streamGraphs.filter(
                    (graph) => graph.graph_id !== message.graph_id,
                );
                streamGraphs = [...remaining, message.graph];
                const status = message.graph.recording?.status;
                if (status === "recording") {
                    recordingInstanceGraphId = message.graph_id;
                } else if (recordingInstanceGraphId === message.graph_id) {
                    recordingInstanceGraphId = null;
                }
                if (status === "failed") {
                    lastError =
                        `Instance ${message.instance_id} failed to materialize: ` +
                        (message.graph.recording?.message ?? "unknown reason");
                }
            },
            onStreamGraphDeleted: (message: StreamGraphDeletedMessage) => {
                streamGraphs = streamGraphs.filter(
                    (graph) => graph.graph_id !== message.graph_id,
                );
                const { [message.graph_id]: _dropped, ...rest } =
                    instanceVerifications;
                instanceVerifications = rest;
            },
            onStreamGraphForked: (message: StreamGraphForkedMessage) => {
                const remaining = streamGraphs.filter(
                    (graph) => graph.graph_id !== message.graph.graph_id,
                );
                streamGraphs = [...remaining, message.graph];
                // Hand the editor the fork to open — the point of forking is to
                // start editing the copy.
                forkedGraphToOpen = message.graph.graph_id;
            },
            onInstanceReplay: (message: InstanceReplayMessage) => {
                if (["stopped", "finished", "failed"].includes(message.state)) {
                    if (activeReplay?.replay_id === message.replay_id) {
                        activeReplay = null;
                    }
                    if (message.state === "failed") {
                        lastError = `Replay failed: ${message.error ?? "unknown reason"}`;
                    }
                    // The scratch topics are deleted when a replay ends; drop them
                    // from the advertised list so nothing keeps offering them.
                    wsManager?.requestStreamList();
                    return;
                }
                const isNew = activeReplay?.replay_id !== message.replay_id;
                activeReplay = message;
                if (isNew) {
                    awaitReplayStreams(
                        (message.bindings ?? []).map((binding) =>
                            String(binding.replay_stream_id),
                        ),
                    );
                }
                // The backend only answers once the first record is on the scratch
                // topic, so by now it exists — start the graph against it. A
                // transform resolves its source topic on the broker, so starting
                // any earlier would fail to find it.
                if (isNew && message.state === "started") {
                    // Re-fetch the stream list first: get_streams is otherwise only
                    // sent once, on connect, so a replay's scratch topics are absent
                    // from availableStreams. Viewers resolve their renderer and
                    // channel labels from that list's descriptor, so without this a
                    // viewer subscribes, receives the replayed records, and still
                    // shows "Waiting for data on this stream…" because it cannot
                    // tell what schema they are.
                    wsManager?.requestStreamList();
                    startStreamGraph(message.graph_id, undefined, message.replay_id);
                }
            },
            onDeviceCommandResult: (message: DeviceCommandResultMessage) => {
                deviceCommandPending = {
                    ...deviceCommandPending,
                    [`${message.stream_id}:${message.command}`]: false,
                };
                deviceCommandResults = {
                    ...deviceCommandResults,
                    [message.stream_id]: message,
                };
            },
            onExperimentInstanceVerification: (
                message: ExperimentInstanceVerificationMessage,
            ) => {
                instanceVerifications = {
                    ...instanceVerifications,
                    [message.graph_id]: message,
                };
            },
            onExperimentDeleted: (message: ExperimentDeletedMessage) => {
                experiments = experiments.filter(
                    (experiment) =>
                        experiment.experiment_id !== message.experiment_id,
                );
                listStreamGraphs();
            },
            onStreamGraphValidation: (
                message: StreamGraphValidationMessage,
            ) => {
                latestStreamGraphDiagnostics =
                    message.graph_diagnostics ?? [];
                latestStreamGraphNodeDiagnostics =
                    message.node_diagnostics ?? {};
                latestStreamGraphEdgeDiagnostics =
                    message.edge_diagnostics ?? {};
            },
            onStreamGraphStatus: (message: StreamGraphStatusMessage) => {
                streamGraphStatuses = {
                    ...streamGraphStatuses,
                    [message.graph_id]: message.status,
                };
            },
            onStreamGraphStarted: (message: StreamGraphStartedMessage) => {
                streamGraphStatuses = {
                    ...streamGraphStatuses,
                    [message.graph_id]: {
                        graph_id: message.graph_id,
                        run_state: "running",
                        active_run_id: message.graph_run_id,
                        node_statuses: message.node_statuses,
                    },
                };
                listStreamGraphs();
                // Starting a graph MINTS topics the frontend has never seen — every
                // transform/combine output, and a replay's scratch topics. Viewers
                // resolve their renderer and channel labels from the descriptor in
                // the advertised stream list, and get_streams is otherwise only sent
                // once on connect, so without this a viewer subscribes, receives
                // records, and still reports "Waiting for data on this stream…"
                // because it cannot tell what schema they are. This is the
                // authoritative moment: the backend has just resolved these topics
                // on the broker in order to build the workers.
                wsManager?.requestStreamList();
            },
            onStreamGraphStopped: (message: StreamGraphStoppedMessage) => {
                streamGraphStatuses = {
                    ...streamGraphStatuses,
                    [message.graph_id]: {
                        graph_id: message.graph_id,
                        run_state: "stopped",
                        active_run_id: message.graph_run_id,
                        node_statuses: message.node_statuses,
                    },
                };
            },
            onImuData: (message: ImuDataMessage) => {
                addLiveImuSample(String(message.stream_id), {
                    timestamp: message.timestamp,
                    data: message.data,
                    accuracies: message.accuracies,
                    has_data: message.has_data,
                });
            },
            onImuBulkData: (message: ImuBulkDataMessage) => {
                for (const sample of message.samples) {
                    addLiveImuSample(String(message.stream_id), sample);
                }
            },
            onMuseData: (message: MuseDataMessage) => {
                addLiveMuseSample(String(message.stream_id), {
                    timestamp: message.timestamp,
                    eeg_sequence: message.eeg_sequence,
                    motion_sequence: message.motion_sequence,
                    eeg: message.eeg,
                    accel: message.accel,
                    gyro: message.gyro,
                    ppg: message.ppg,
                    has_data: message.has_data,
                });
            },
            onMuseBulkData: (message: MuseBulkDataMessage) => {
                for (const sample of message.samples) {
                    addLiveMuseSample(String(message.stream_id), sample);
                }
            },
            onEmgData: (message: EmgDataMessage) => {
                const frameDurationMs =
                    message.sample_rate_hz > 0
                        ? Math.max(
                              1,
                              (message.samples_per_channel /
                                  message.sample_rate_hz) *
                                  1000,
                          )
                        : 1000;
                addLiveEmgSample(
                    String(message.stream_id),
                    {
                        schema_version: message.schema_version,
                        device_id: message.device_id,
                        seq_no: message.seq_no,
                        device_ts_us: message.device_ts_us,
                        n_channels: message.n_channels,
                        samples_per_channel: message.samples_per_channel,
                        sample_rate_hz: message.sample_rate_hz,
                        channel_labels: message.channel_labels,
                        payload: message.payload,
                        received_at_ms: Date.now(),
                        frame_duration_ms: frameDurationMs,
                    },
                    message.device_id,
                );
            },
            onStreamTime: (message: StreamTimeMessage) => {
                streamTimeExtents = {
                    ...streamTimeExtents,
                    [String(message.stream_id)]: message,
                };
            },
            onMarker: (message: MarkerMessage) => {
                addLiveMarker(String(message.stream_id), {
                    session_id: message.session_id,
                    marker_type: message.marker_type,
                    marker_id: message.marker_id,
                    event: message.event,
                    label: message.label,
                    emitted_at_us: message.emitted_at_us,
                    attributes: message.attributes ?? {},
                    received_at_ms: Date.now(),
                });
            },
            onError: (message: ErrorMessage) => {
                lastError = message.message;
            },
        });

        wsManager.connect();
    });

    onDestroy(() => {
        if (statusTimer !== null) {
            clearInterval(statusTimer);
        }
        if (liveFlushTimer !== null) {
            clearInterval(liveFlushTimer);
        }
        wsManager?.disconnect();
    });

    // Every discovered stream is selectable as a source node. This is NOT
    // filtered to transform-compatible streams (the old behavior) — a source node
    // just represents a stream to view/record/route, and gating it on transform
    // capability hid non-channel-frame sensors like the IMU from the palette
    // entirely. Transform-compatibility is enforced later, at connection time.
    const editorStreams = $derived(
        Object.entries(availableStreams)
            .map(([streamId, info]) => ({
                streamId,
                schemaName:
                    info.topics.find((topic) => topic.descriptor)?.descriptor
                        ?.schema_name ?? "Unknown",
                descriptor:
                    info.topics.find((topic) => topic.descriptor)?.descriptor,
                live: false,
            }))
            .sort((left, right) => left.streamId.localeCompare(right.streamId)),
    );

</script>

<div class="visual-programming">
    <!-- Connection status now lives in the editor toolbar (see conn-pill) so it
         no longer floats over the toolbar's right-edge buttons. -->

    {#if lastError}
        <p class="error-banner">{lastError}</p>
    {/if}

    <StreamGraphEditor
        availableStreams={editorStreams}
        {transformCapabilities}
        {nodeCatalog}
        graphDefinitions={visibleGraphs}
        graphStatuses={streamGraphStatuses}
        latestValidation={latestStreamGraphNodeDiagnostics}
        latestEdgeValidation={latestStreamGraphEdgeDiagnostics}
        latestGraphDiagnostics={latestStreamGraphDiagnostics}
        {connectionState}
        {listStreamGraphs}
        {requestStreamGraphStatus}
        {saveStreamGraph}
        profiles={visibleProfiles}
        {listProfiles}
        {saveProfile}
        {deleteProfile}
        experiments={visibleExperiments}
        {workspaces}
        {selectedWorkspaceId}
        {hiddenCounts}
        {selectWorkspace}
        {saveWorkspace}
        {deleteWorkspace}
        {saveExperiment}
        {deleteExperiment}
        {startExperimentInstance}
        {finishExperimentInstance}
        {deleteStreamGraph}
        {recordingInstanceGraphId}
        {forkStreamGraph}
        {verifyExperimentInstance}
        {startInstanceReplay}
        {stopInstanceReplay}
        {activeReplay}
        {instanceVerifications}
        {forkedGraphToOpen}
        onForkOpened={() => (forkedGraphToOpen = null)}
        {restartStreamGraphNode}
        {sendDeviceCommand}
        {deviceCommandPending}
        {deviceCommandResults}
        {publishSessionBundle}
        {submitTrainJob}
        {trainJobStatus}
        {trainModelPath}
        {trainBundlePath}
        {trainAccuracy}
        {completedTrainJob}
        {validateStreamGraph}
        {startStreamGraph}
        {stopStreamGraph}
        {queryStreamTime}
        {streamTimeExtents}
        {recordedRuns}
        {requestRecordedRuns}
        {inspectStream}
        {liveStreams}
        {streamDeviceNames}
        {subscribeToStream}
        {unsubscribeFromStream}
        {formatNumber}
    />
</div>

<style>
    .visual-programming {
        position: relative;
        height: calc(100vh - 56px);
        box-sizing: border-box;
        overflow: hidden;
    }

    /* Error toast floats over the full-bleed canvas (connection status moved
       into the editor toolbar). */
    .error-banner {
        position: absolute;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 30;
        margin: 0;
        max-width: min(70vw, 640px);
        border-radius: 8px;
        padding: 0.7rem 0.9rem;
        background: rgba(70, 18, 26, 0.92);
        color: #ffb9b9;
        border: 1px solid rgba(255, 143, 143, 0.28);
        backdrop-filter: blur(4px);
    }
</style>
