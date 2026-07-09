<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { router } from "tinro";
    import {
        StreamViewerWebSocket,
        type ConnectionState,
    } from "../StreamViewer/websocket";
    import { descriptorSupportsAnyTransformCapability } from "../StreamViewer/schemaDescriptor";
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
        DataSchemaDescriptor,
    } from "../StreamViewer/types";
    import type { SessionPublishBundleInput } from "../StreamViewer/experiment";

    const STATUS_REFRESH_INTERVAL_MS = 500;
    const STREAM_GRAPH_REFRESH_INTERVAL_MS = 1000;

    function getWebSocketUrl(): string {
        const wsProtocol =
            window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${wsProtocol}//${window.location.host}/ws/stream_viewer`;
    }

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
    let streamGraphs = $state<StreamGraphDefinition[]>([]);
    let streamGraphStatuses = $state<Record<string, StreamGraphStatusSummary>>(
        {},
    );
    let latestStreamGraphDiagnostics = $state<StreamGraphDiagnostic[]>([]);
    let latestStreamGraphNodeDiagnostics = $state<
        Record<string, StreamGraphDiagnostic[]>
    >({});
    let latestStreamGraphEdgeDiagnostics = $state<
        Record<string, StreamGraphDiagnostic[]>
    >({});
    let lastStreamGraphRefreshAtMs = $state(0);
    let nowMs = $state(Date.now());

    let wsManager: StreamViewerWebSocket | null = null;
    let statusTimer: ReturnType<typeof setInterval> | null = null;

    // Raw sample data for the single stream currently open in a "viewer" node's
    // live data modal. Scoped to one stream at a time since only one modal can
    // be open; unlike the Stream Viewer page this connection is otherwise
    // control-plane only, so we subscribe/unsubscribe on demand instead of
    // buffering every available stream.
    const MAX_LIVE_BUFFER_SIZE = 100;
    let liveStreamId = $state<string | null>(null);
    let liveStreamType = $state<"imu" | "muse" | "emg" | null>(null);
    let liveImuSamples = $state<ImuSample[]>([]);
    let liveMuseSamples = $state<MuseSample[]>([]);
    let liveEmgSamples = $state<BufferedEmgSample[]>([]);

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

    function addLiveImuSample(streamId: string, sample: ImuSample) {
        if (streamId !== liveStreamId) {
            return;
        }
        liveStreamType = "imu";
        const nextBuffer = [...liveImuSamples, sample];
        liveImuSamples =
            nextBuffer.length > MAX_LIVE_BUFFER_SIZE
                ? nextBuffer.slice(-MAX_LIVE_BUFFER_SIZE)
                : nextBuffer;
    }

    function addLiveMuseSample(streamId: string, sample: MuseSample) {
        if (streamId !== liveStreamId) {
            return;
        }
        liveStreamType = "muse";
        const nextBuffer = [...liveMuseSamples, sample];
        liveMuseSamples =
            nextBuffer.length > MAX_LIVE_BUFFER_SIZE
                ? nextBuffer.slice(-MAX_LIVE_BUFFER_SIZE)
                : nextBuffer;
    }

    function addLiveEmgSample(streamId: string, sample: BufferedEmgSample) {
        if (streamId !== liveStreamId) {
            return;
        }
        liveStreamType = "emg";
        const nextBuffer = [...liveEmgSamples, sample];
        const maxHistoryMs = 20000;
        let retainedDurationMs = 0;
        let startIndex = nextBuffer.length;
        while (startIndex > 0) {
            retainedDurationMs += nextBuffer[startIndex - 1].frame_duration_ms;
            if (
                retainedDurationMs > maxHistoryMs &&
                startIndex < nextBuffer.length
            ) {
                break;
            }
            startIndex -= 1;
        }
        liveEmgSamples = nextBuffer.slice(startIndex);
    }

    function subscribeToStream(streamId: string) {
        liveStreamId = streamId;
        liveStreamType = inferLiveStreamType(streamId) ?? null;
        liveImuSamples = [];
        liveMuseSamples = [];
        liveEmgSamples = [];
        wsManager?.subscribe([streamId]);
    }

    function unsubscribeFromStream(streamId: string) {
        wsManager?.unsubscribe([streamId]);
        if (liveStreamId === streamId) {
            liveStreamId = null;
            liveStreamType = null;
            liveImuSamples = [];
            liveMuseSamples = [];
            liveEmgSamples = [];
        }
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
            report?: { model_path?: string | null } | null;
        };
        if (msg.type === "job_accepted") {
            trainJobStatus = `queued (${msg.job_id ?? "job"})`;
        } else if (msg.type === "job_status") {
            trainJobStatus = `${msg.status ?? "?"}: ${msg.message ?? ""}`.trim();
            if (msg.status === "completed" && msg.report?.model_path) {
                trainModelPath = msg.report.model_path;
            }
        } else if (msg.type === "error") {
            trainJobStatus = `error: ${msg.error ?? msg.message ?? "unknown"}`;
        }
    }

    // Submit a train_validate job through the backend ML proxy (Phase 5).
    function submitTrainJob(config: import(
        "../StreamViewer/types"
    ).TrainNodeConfig): void {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Visual Programming WebSocket is not connected";
            return;
        }
        trainModelPath = null;
        trainJobStatus = "submitting…";
        wsManager.sendMlAction({
            action: "start_train_validate_job",
            request_id: crypto.randomUUID(),
            train_runs: config.train_runs,
            eval_runs: config.eval_runs,
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

    function startStreamGraph(graphId: string): boolean {
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
        });
        return true;
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
                addLiveEmgSample(String(message.stream_id), {
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
        wsManager?.disconnect();
    });

    let transformSourceStreams = $derived(
        Object.entries(availableStreams)
            .map(([streamId, info]) => ({
                streamId,
                schemaName:
                    info.topics.find((topic) => topic.descriptor)?.descriptor
                        ?.schema_name ?? "Unknown",
                descriptor:
                    info.topics.find((topic) => topic.descriptor)?.descriptor,
            }))
            .filter((stream) =>
                descriptorSupportsAnyTransformCapability(
                    stream.descriptor,
                    transformCapabilities,
                ),
            )
            .sort((left, right) => left.streamId.localeCompare(right.streamId)),
    );

    const editorStreams = $derived(
        transformSourceStreams.map((stream) => ({
            streamId: stream.streamId,
            schemaName: stream.schemaName,
            descriptor: stream.descriptor,
            live: false,
        })),
    );

    const liveLatestImuSample = $derived(
        liveImuSamples.length > 0
            ? liveImuSamples[liveImuSamples.length - 1]
            : undefined,
    );
    const liveLatestMuseSample = $derived(
        liveMuseSamples.length > 0
            ? liveMuseSamples[liveMuseSamples.length - 1]
            : undefined,
    );
    const liveLatestEmgSample = $derived(
        liveEmgSamples.length > 0
            ? liveEmgSamples[liveEmgSamples.length - 1]
            : undefined,
    );

    const livePrimaryDescriptor: DataSchemaDescriptor | undefined = $derived(
        liveStreamId
            ? availableStreams[liveStreamId]?.topics.find(
                  (topic) => topic.descriptor,
              )?.descriptor
            : undefined,
    );

    const liveDescriptorRecordValue = $derived.by((): unknown => {
        if (liveStreamType === "emg" && liveLatestEmgSample) {
            return liveLatestEmgSample;
        }
        if (liveStreamType === "imu" && liveLatestImuSample) {
            return {
                time: liveLatestImuSample.timestamp,
                accel: liveLatestImuSample.data.accel,
                gyro: liveLatestImuSample.data.gyro,
                quat: liveLatestImuSample.data.quat,
                accuracies: liveLatestImuSample.accuracies,
                has_data: liveLatestImuSample.has_data,
            };
        }
        if (liveStreamType === "muse" && liveLatestMuseSample) {
            return {
                time: liveLatestMuseSample.timestamp,
                eeg_sequence: liveLatestMuseSample.eeg_sequence,
                motion_sequence: liveLatestMuseSample.motion_sequence,
                eeg: liveLatestMuseSample.eeg,
                accel: liveLatestMuseSample.accel,
                gyro: liveLatestMuseSample.gyro,
                ppg: liveLatestMuseSample.ppg,
                has_data: liveLatestMuseSample.has_data,
            };
        }
        return undefined;
    });
</script>

<div class="visual-programming">
    <header class="header">
        <h1>Visual Programming</h1>
        <div class="connection-status {connectionState}">
            {connectionState === "connected"
                ? "Connected"
                : connectionState === "connecting"
                  ? "Connecting…"
                  : "Disconnected"}
        </div>
    </header>

    {#if lastError}
        <p class="error-banner">{lastError}</p>
    {/if}

    <StreamGraphEditor
        availableStreams={editorStreams}
        {transformCapabilities}
        {nodeCatalog}
        graphDefinitions={streamGraphs}
        graphStatuses={streamGraphStatuses}
        latestValidation={latestStreamGraphNodeDiagnostics}
        latestEdgeValidation={latestStreamGraphEdgeDiagnostics}
        latestGraphDiagnostics={latestStreamGraphDiagnostics}
        {connectionState}
        {listStreamGraphs}
        {requestStreamGraphStatus}
        {saveStreamGraph}
        {restartStreamGraphNode}
        {publishSessionBundle}
        {submitTrainJob}
        {trainJobStatus}
        {trainModelPath}
        {validateStreamGraph}
        {startStreamGraph}
        {stopStreamGraph}
        {inspectStream}
        {liveStreamId}
        {liveStreamType}
        {liveLatestMuseSample}
        liveEmgSamples={liveEmgSamples}
        {livePrimaryDescriptor}
        {liveDescriptorRecordValue}
        {subscribeToStream}
        {unsubscribeFromStream}
        {formatNumber}
    />
</div>

<style>
    .visual-programming {
        min-height: calc(100vh - 56px);
        display: flex;
        flex-direction: column;
        gap: 1rem;
        padding: 1.25rem 1.5rem 2rem;
        box-sizing: border-box;
    }

    .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }

    .header h1 {
        margin: 0;
        font-size: 1.5rem;
    }

    .connection-status {
        border-radius: 999px;
        padding: 0.3rem 0.85rem;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid rgba(114, 142, 255, 0.24);
        color: #9dafdf;
    }

    .connection-status.connected {
        color: #8ef2bf;
        border-color: rgba(142, 242, 191, 0.32);
    }

    .connection-status.connecting {
        color: #ffcf85;
        border-color: rgba(255, 176, 32, 0.32);
    }

    .error-banner {
        margin: 0;
        border-radius: 8px;
        padding: 0.7rem 0.9rem;
        background: rgba(70, 18, 26, 0.72);
        color: #ffb9b9;
        border: 1px solid rgba(255, 143, 143, 0.28);
    }
</style>
