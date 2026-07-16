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
        MarkerMessage,
        BufferedMarkerEvent,
        StreamTimeMessage,
        DataSchemaDescriptor,
        LiveStreamData,
    } from "../StreamViewer/types";
    import type { RecordedRunSummary } from "../MlPipeline/types";
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
    // Durable path to the self-describing live-inference bundle (Phase 2). This
    // is what an emg_gesture_classify node loads; auto-filled into the classify
    // node on job completion so the operator never pastes a path.
    let trainBundlePath = $state<string | null>(null);
    let streamGraphs = $state<StreamGraphDefinition[]>([]);
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
            report?: { model_path?: string | null; bundle_path?: string | null } | null;
            runs?: RecordedRunSummary[];
        };
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
        trainBundlePath = null;
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

    function startStreamGraph(graphId: string, startOffset?: number): boolean {
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
        {trainBundlePath}
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
