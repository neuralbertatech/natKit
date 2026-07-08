<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { StreamViewerWebSocket, type ConnectionState } from "./websocket";
    import ChannelFrameViewer from "./ChannelFrameViewer.svelte";
    import FeatureVectorViewer from "./FeatureVectorViewer.svelte";
    import EmgExperiment from "./EmgExperiment.svelte";
    import EmgTransforms from "./EmgTransforms.svelte";
    import MuseViewer from "./MuseViewer.svelte";
    import ClassificationViewer from "./ClassificationViewer.svelte";
    import SchemaDescriptorInspector from "./SchemaDescriptorInspector.svelte";
    import { router } from "tinro";
    import {
        descriptorSupportsAnyTransformCapability,
        descriptorSupportsNumericChannelFrames,
        findCompatibleTransformInputMappingId,
    } from "./schemaDescriptor";
    import { chooseViewerRenderer } from "./viewerRegistry";
    import type {
        DataSchemaDescriptor,
        StreamListMessage,
        StatusMessage,
        PublishResultMessage,
        TransformCapabilitiesMessage,
        EmgTransformResultMessage,
        EmgTransformListMessage,
        EmgTransformStoppedMessage,
        EmgTransformSummary,
        ImuDataMessage,
        ImuBulkDataMessage,
        MuseDataMessage,
        MuseBulkDataMessage,
        EmgDataMessage,
        BufferedEmgSample,
        TransformProvenanceMessage,
        ImuSample,
        MuseSample,
        StreamInfo,
        ErrorMessage,
        TransformCapability,
        TransformKind,
    } from "./types";
    import type {
        EmgStreamOption,
        SessionPublishBundleInput,
    } from "./experiment";

    function getWebSocketUrl(): string {
        const wsProtocol =
            window.location.protocol === "https:" ? "wss:" : "ws:";
        return `${wsProtocol}//${window.location.host}/ws/stream_viewer`;
    }

    function requestEmgTransformList() {
        lastEmgTransformRefreshAtMs = Date.now();
        wsManager?.send({
            action: "list_transforms",
            request_id: `emg-transform-list:${Date.now()}`,
        });
    }

    // Connection state
    let connectionState = $state<ConnectionState>("disconnected");
    let lastError = $state<string | null>(null);

    // Available streams from backend
    let availableStreams = $state<Record<string, StreamInfo>>({});

    // Currently subscribed streams
    let subscribedStreams = $state<Set<string>>(new Set());

    // Buffered history per stream
    const MAX_BUFFER_SIZE = 100;
    const SENSOR_UNREACHABLE_TIMEOUT_MS = 3000;
    const STATUS_REFRESH_INTERVAL_MS = 500;
    const EMG_TRANSFORM_REFRESH_INTERVAL_MS = 1000;
    let imuBuffers = $state<Map<string, ImuSample[]>>(new Map());
    let museBuffers = $state<Map<string, MuseSample[]>>(new Map());
    let emgBuffers = $state<Map<string, BufferedEmgSample[]>>(new Map());
    let transformProvenanceByStream = $state<
        Map<string, TransformProvenanceMessage>
    >(new Map());
    let lastReceivedAt = $state<Map<string, number>>(new Map());
    let nowMs = $state(Date.now());

    // Track stream types by stream ID
    let streamTypes = $state<Map<string, "imu" | "muse" | "emg">>(new Map());

    // Expanded accordion state
    let expandedStreams = $state<Set<string>>(new Set());
    let currentTab = $state<"live" | "experiment" | "transforms">("live");
    let lastPublishResult = $state<PublishResultMessage | null>(null);
    let lastTransformResult = $state<EmgTransformResultMessage | null>(null);
    let transformCapabilities = $state<TransformCapability[]>([]);
    let emgTransforms = $state<EmgTransformSummary[]>([]);
    let emgTransformWorkerId = $state("natkit-local-transform-worker");
    let emgTransformSlotCapacity = $state(0);
    let emgTransformActiveCount = $state(0);
    let emgTransformAvailableSlotCount = $state(0);
    let emgTransformUtilizationRatio = $state(0);
    let emgTransformLastHeartbeatUs = $state(0);
    let emgTransformWorkerStatus = $state<"idle" | "live" | "stalled">("idle");
    let pendingDerivedStreamId = $state<string | null>(null);
    let pendingDerivedStreamDeadlineMs = $state<number | null>(null);
    let lastEmgTransformRefreshAtMs = $state(0);

    let wsManager: StreamViewerWebSocket | null = null;
    let stalenessTimer: ReturnType<typeof setInterval> | null = null;

    onMount(() => {
        stalenessTimer = setInterval(() => {
            nowMs = Date.now();
            if (
                pendingDerivedStreamId !== null &&
                pendingDerivedStreamDeadlineMs !== null &&
                nowMs <= pendingDerivedStreamDeadlineMs &&
                !availableStreams[pendingDerivedStreamId]
            ) {
                wsManager?.requestStreamList();
            }
            if (
                wsManager?.getConnectionState() === "connected" &&
                (currentTab === "transforms" || emgTransformActiveCount > 0) &&
                nowMs - lastEmgTransformRefreshAtMs >=
                    EMG_TRANSFORM_REFRESH_INTERVAL_MS
            ) {
                requestEmgTransformList();
            }
        }, STATUS_REFRESH_INTERVAL_MS);

        wsManager = new StreamViewerWebSocket(getWebSocketUrl(), {
            onConnectionChange: (state) => {
                connectionState = state;
                if (state === "connected") {
                    lastError = null;
                    wsManager?.send({
                        action: "list_transform_capabilities",
                        request_id: `transform-capabilities:${Date.now()}`,
                    });
                    requestEmgTransformList();
                }
            },
            onStreamList: (message: StreamListMessage) => {
                availableStreams = message.streams;
            },
            onStatus: (message: StatusMessage) => {
                subscribedStreams = new Set(
                    message.subscribed_streams.map(String),
                );
            },
            onPublishResult: (message: PublishResultMessage) => {
                lastPublishResult = message;
            },
            onTransformCapabilities: (
                message: TransformCapabilitiesMessage,
            ) => {
                transformCapabilities = message.transforms;
            },
            onEmgTransformResult: (message: EmgTransformResultMessage) => {
                lastTransformResult = message;
                pendingDerivedStreamId = message.output_stream_id;
                pendingDerivedStreamDeadlineMs = Date.now() + 5000;
                wsManager?.requestStreamList();
            },
            onEmgTransformList: (message: EmgTransformListMessage) => {
                emgTransforms = message.transforms;
                emgTransformWorkerId = message.worker_id;
                emgTransformSlotCapacity = message.slot_capacity;
                emgTransformActiveCount = message.active_count;
                emgTransformAvailableSlotCount =
                    message.available_slot_count;
                emgTransformUtilizationRatio = message.utilization_ratio;
                emgTransformLastHeartbeatUs = message.last_heartbeat_us;
                emgTransformWorkerStatus = message.worker_status;
            },
            onEmgTransformStopped: (message: EmgTransformStoppedMessage) => {
                emgTransformActiveCount = message.active_count;
                emgTransformSlotCapacity = message.slot_capacity;
                lastTransformResult = null;
            },
            onImuData: (message: ImuDataMessage) => {
                addImuSampleToBuffer(String(message.stream_id), {
                    timestamp: message.timestamp,
                    data: message.data,
                    accuracies: message.accuracies,
                    has_data: message.has_data,
                });
            },
            onImuBulkData: (message: ImuBulkDataMessage) => {
                for (const sample of message.samples) {
                    addImuSampleToBuffer(String(message.stream_id), sample);
                }
            },
            onMuseData: (message: MuseDataMessage) => {
                addMuseSampleToBuffer(String(message.stream_id), {
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
                    addMuseSampleToBuffer(String(message.stream_id), sample);
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
                addEmgSampleToBuffer(String(message.stream_id), {
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
            onTransformProvenance: (message: TransformProvenanceMessage) => {
                const nextMap = new Map(transformProvenanceByStream);
                nextMap.set(String(message.stream_id), message);
                transformProvenanceByStream = nextMap;
            },
            onError: (message: ErrorMessage) => {
                lastError = message.message;
            },
        });

        wsManager.connect();
    });

    onDestroy(() => {
        if (stalenessTimer !== null) {
            clearInterval(stalenessTimer);
        }
        wsManager?.disconnect();
    });

    function markStreamDataReceived(streamId: string) {
        const nextMap = new Map(lastReceivedAt);
        nextMap.set(streamId, Date.now());
        lastReceivedAt = nextMap;
    }

    function addImuSampleToBuffer(streamId: string, sample: ImuSample) {
        // Track stream type
        if (!streamTypes.has(streamId)) {
            const newTypes = new Map(streamTypes);
            newTypes.set(streamId, "imu");
            streamTypes = newTypes;
        }

        const existingBuffer = imuBuffers.get(streamId) || [];
        let newBuffer = [...existingBuffer, sample];
        if (newBuffer.length > MAX_BUFFER_SIZE) {
            newBuffer = newBuffer.slice(-MAX_BUFFER_SIZE);
        }
        const newMap = new Map(imuBuffers);
        newMap.set(streamId, newBuffer);
        imuBuffers = newMap;
        markStreamDataReceived(streamId);
    }

    function addMuseSampleToBuffer(streamId: string, sample: MuseSample) {
        // Track stream type
        if (!streamTypes.has(streamId)) {
            const newTypes = new Map(streamTypes);
            newTypes.set(streamId, "muse");
            streamTypes = newTypes;
        }

        const existingBuffer = museBuffers.get(streamId) || [];
        let newBuffer = [...existingBuffer, sample];
        if (newBuffer.length > MAX_BUFFER_SIZE) {
            newBuffer = newBuffer.slice(-MAX_BUFFER_SIZE);
        }
        const newMap = new Map(museBuffers);
        newMap.set(streamId, newBuffer);
        museBuffers = newMap;
        markStreamDataReceived(streamId);
    }

    function addEmgSampleToBuffer(streamId: string, sample: BufferedEmgSample) {
        if (!streamTypes.has(streamId)) {
            const newTypes = new Map(streamTypes);
            newTypes.set(streamId, "emg");
            streamTypes = newTypes;
        }

        const existingBuffer = emgBuffers.get(streamId) || [];
        const nextBuffer = [...existingBuffer, sample];
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
        const newBuffer = nextBuffer.slice(startIndex);
        const newMap = new Map(emgBuffers);
        newMap.set(streamId, newBuffer);
        emgBuffers = newMap;
        markStreamDataReceived(streamId);
    }

    function toggleStreamSubscription(streamId: string) {
        if (subscribedStreams.has(streamId)) {
            wsManager?.unsubscribe([streamId]);
            // Clear buffers for this stream
            imuBuffers.delete(streamId);
            imuBuffers = new Map(imuBuffers);
            museBuffers.delete(streamId);
            museBuffers = new Map(museBuffers);
            emgBuffers.delete(streamId);
            emgBuffers = new Map(emgBuffers);
            transformProvenanceByStream.delete(streamId);
            transformProvenanceByStream = new Map(transformProvenanceByStream);
            streamTypes.delete(streamId);
            streamTypes = new Map(streamTypes);
            lastReceivedAt.delete(streamId);
            lastReceivedAt = new Map(lastReceivedAt);
        } else {
            wsManager?.subscribe([streamId]);
        }
    }

    function ensureStreamSubscribed(streamId: string) {
        if (subscribedStreams.has(streamId)) {
            return;
        }
        wsManager?.subscribe([streamId]);
        const nextSubscribedStreams = new Set(subscribedStreams);
        nextSubscribedStreams.add(streamId);
        subscribedStreams = nextSubscribedStreams;
    }

    function inspectStream(streamId: string) {
        ensureStreamSubscribed(streamId);
        currentTab = "live";
        const nextExpandedStreams = new Set(expandedStreams);
        nextExpandedStreams.add(streamId);
        expandedStreams = nextExpandedStreams;
    }

    // Deep-link support: other pages (e.g. Visual Programming) can navigate to
    // /StreamViewer?inspect=<streamId> to open the live view of a stream.
    let pendingInspectStreamId = $state<string | null>(null);

    onMount(() => {
        const inspect = router.location.query.get("inspect");
        if (typeof inspect === "string" && inspect.length > 0) {
            pendingInspectStreamId = inspect;
            router.location.query.delete("inspect");
        }
    });

    $effect(() => {
        if (
            pendingInspectStreamId !== null &&
            connectionState === "connected"
        ) {
            inspectStream(pendingInspectStreamId);
            pendingInspectStreamId = null;
        }
    });

    function inferStreamType(
        streamId: string,
    ): "imu" | "muse" | "emg" | undefined {
        const knownType = streamTypes.get(streamId);
        if (knownType) {
            return knownType;
        }
        const info = availableStreams[streamId];
        if (!info) {
            return undefined;
        }
        // Channel-frame streams are detected by descriptor capability, not by
        // sensor/schema name — any record matching the canonical numeric
        // channel-frame contract renders on the waveform viewer. (Phase 2 will
        // replace this whole enum with a descriptor-driven viewer registry.)
        if (descriptorSupportsNumericChannelFrames(getPrimaryDescriptor(streamId))) {
            return "emg";
        }
        const schemaNames = info.topics.map((topic) => topic.schema_name);
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

    function toggleStreamExpanded(streamId: string) {
        if (expandedStreams.has(streamId)) {
            expandedStreams.delete(streamId);
        } else {
            expandedStreams.add(streamId);
        }
        expandedStreams = new Set(expandedStreams);
    }

    function getPrimaryDescriptor(
        streamId: string,
    ): DataSchemaDescriptor | undefined {
        return availableStreams[streamId]?.topics.find((topic) => topic.descriptor)
            ?.descriptor;
    }

    function getDescriptorRecordValue(
        streamType: "imu" | "muse" | "emg" | undefined,
        latestImuSample: ImuSample | undefined,
        latestMuseSample: MuseSample | undefined,
        latestEmgSample: BufferedEmgSample | undefined,
    ): unknown {
        if (streamType === "emg" && latestEmgSample) {
            return latestEmgSample;
        }
        if (streamType === "imu" && latestImuSample) {
            return {
                time: latestImuSample.timestamp,
                accel: latestImuSample.data.accel,
                gyro: latestImuSample.data.gyro,
                quat: latestImuSample.data.quat,
                accuracies: latestImuSample.accuracies,
                has_data: latestImuSample.has_data,
            };
        }
        if (streamType === "muse" && latestMuseSample) {
            return {
                time: latestMuseSample.timestamp,
                eeg_sequence: latestMuseSample.eeg_sequence,
                motion_sequence: latestMuseSample.motion_sequence,
                eeg: latestMuseSample.eeg,
                accel: latestMuseSample.accel,
                gyro: latestMuseSample.gyro,
                ppg: latestMuseSample.ppg,
                has_data: latestMuseSample.has_data,
            };
        }
        return undefined;
    }

    function formatNumber(num: number, decimals: number = 4): string {
        return num.toFixed(decimals);
    }

    function formatTimestampUs(timestampUs: number): string {
        if (!Number.isFinite(timestampUs) || timestampUs <= 0) {
            return "Unknown";
        }
        return new Date(timestampUs / 1000).toLocaleString();
    }

    function parseTransformConfigJson(
        configJson: string,
    ): Array<{ key: string; value: string }> {
        try {
            const parsed = JSON.parse(configJson) as Record<string, unknown>;
            return Object.entries(parsed).map(([key, value]) => ({
                key,
                value:
                    typeof value === "number"
                        ? String(value)
                        : typeof value === "string"
                          ? value
                          : JSON.stringify(value),
            }));
        } catch {
            return [];
        }
    }

    function getConnectionClass(state: ConnectionState): string {
        switch (state) {
            case "connected":
                return "status-connected";
            case "connecting":
                return "status-connecting";
            case "disconnected":
                return "status-disconnected";
        }
    }

    function isStreamUnreachable(streamId: string): boolean {
        const streamLastSeen = lastReceivedAt.get(streamId);
        return (
            streamLastSeen !== undefined &&
            nowMs - streamLastSeen >= SENSOR_UNREACHABLE_TIMEOUT_MS
        );
    }

    function getStreamStatusClass(streamId: string, hasData: boolean): string {
        if (!hasData) {
            return "stream-status-nodata";
        }
        return isStreamUnreachable(streamId)
            ? "stream-status-unreachable"
            : "stream-status-live";
    }

    function getStreamStatusLabel(streamId: string, hasData: boolean): string {
        if (!hasData) {
            return "No Data";
        }
        return isStreamUnreachable(streamId) ? "Unreachable" : "Live";
    }

    function refreshStreams() {
        wsManager?.requestStreamList();
    }

    function publishSessionBundle(payload: SessionPublishBundleInput): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Stream Viewer WebSocket is not connected";
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

    function createEmgTransform(payload: {
        requestId: string;
        sourceStreamId: string;
        outputIdentifier: string;
        transformKind: TransformKind;
        inputMappingId?: string;
        config: {
            cutoff_hz?: number;
            low_cutoff_hz?: number;
            high_cutoff_hz?: number;
            notch_hz?: number;
            notch_q?: number;
            iir_method?: "butterworth" | "biquad";
            butterworth_order?: number;
            biquad_q?: number;
            harmonic_count?: number;
            window_samples?: number;
            step_samples?: number;
        };
    }): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Stream Viewer WebSocket is not connected";
            return false;
        }

        wsManager.send({
            action: "create_transform",
            request_id: payload.requestId,
            source_stream_id: payload.sourceStreamId,
            output_identifier: payload.outputIdentifier,
            transform_kind: payload.transformKind,
            input_mapping_id: payload.inputMappingId,
            config: payload.config,
        });
        return true;
    }

    function stopEmgTransform(outputStreamId: string): boolean {
        if (wsManager?.getConnectionState() !== "connected") {
            lastError = "Stream Viewer WebSocket is not connected";
            return false;
        }
        wsManager.send({
            action: "stop_transform",
            request_id: `emg-transform-stop:${Date.now()}`,
            output_stream_id: outputStreamId,
        });
        return true;
    }

    $effect(() => {
        if (
            pendingDerivedStreamId === null ||
            pendingDerivedStreamDeadlineMs === null
        ) {
            return;
        }

        if (availableStreams[pendingDerivedStreamId]) {
            ensureStreamSubscribed(pendingDerivedStreamId);
            pendingDerivedStreamId = null;
            pendingDerivedStreamDeadlineMs = null;
            return;
        }

        if (nowMs > pendingDerivedStreamDeadlineMs) {
            pendingDerivedStreamId = null;
            pendingDerivedStreamDeadlineMs = null;
        }
    });

    let emgStreams = $derived(
        Object.entries(availableStreams)
            .filter(([streamId]) => inferStreamType(streamId) === "emg")
            .map(([streamId, info]) => ({
                streamId,
                info,
                subscribed: subscribedStreams.has(streamId),
                live:
                    (lastReceivedAt.get(streamId) ?? 0) > 0 &&
                    !isStreamUnreachable(streamId),
                lastReceivedAtMs: lastReceivedAt.get(streamId) ?? null,
                latestSample: emgBuffers.get(streamId)?.at(-1) ?? null,
            }) satisfies EmgStreamOption)
            .sort((left, right) => left.streamId.localeCompare(right.streamId)),
    );

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
</script>

<div class="stream-viewer">
    <header class="header">
        <h1>Stream Viewer</h1>
        <div class="connection-status {getConnectionClass(connectionState)}">
            {connectionState === "connected"
                ? "Connected"
                : connectionState === "connecting"
                  ? "Connecting..."
                  : "Disconnected"}
        </div>
    </header>

    {#if lastError}
        <div class="error-banner">
            Error: {lastError}
        </div>
    {/if}

    <div class="main-content">
        <!-- Stream Selection Panel -->
        <aside class="stream-panel">
            <div class="panel-header">
                <h2>Available Streams</h2>
                <button
                    class="refresh-btn"
                    onclick={refreshStreams}
                    title="Refresh stream list"
                >
                    Refresh
                </button>
            </div>

            {#if Object.keys(availableStreams).length === 0}
                <p class="no-streams">No streams available</p>
            {:else}
                <ul class="stream-list">
                    {#each Object.entries(availableStreams) as [streamIdStr, streamInfo]}
                        <li class="stream-item">
                            <label class="stream-label">
                                <input
                                    type="checkbox"
                                    checked={subscribedStreams.has(streamIdStr)}
                                    onchange={() =>
                                        toggleStreamSubscription(streamIdStr)}
                                />
                                <span class="stream-id"
                                    >Stream {streamIdStr}</span
                                >
                            </label>
                            <ul class="topic-list">
                                {#each streamInfo.topics ?? [] as topic}
                                    <li class="topic-item">
                                        <span
                                            class="topic-type {topic.type.toLowerCase()}"
                                            >{topic.type}</span
                                        >
                                        <span class="topic-schema"
                                            >{topic.schema_name}</span
                                        >
                                        {#if topic.descriptor}
                                            <span class="topic-descriptor">
                                                descriptor v{topic.descriptor
                                                    .descriptor_version}
                                            </span>
                                        {/if}
                                    </li>
                                {/each}
                            </ul>
                        </li>
                    {/each}
                </ul>
            {/if}
        </aside>

        <!-- Data Display Panel -->
        <main class="data-panel">
            <div class="data-panel-header">
                <h2
                    >{currentTab === "live"
                        ? "Live Data"
                        : currentTab === "experiment"
                          ? "EMG Experiment"
                          : "EMG Transforms"}</h2
                >
                <div class="panel-tabs">
                    <button
                        class:active={currentTab === "live"}
                        onclick={() => (currentTab = "live")}
                    >
                        Live
                    </button>
                    <button
                        class:active={currentTab === "experiment"}
                        onclick={() => (currentTab = "experiment")}
                    >
                        Experiment
                    </button>
                    <button
                        class:active={currentTab === "transforms"}
                        onclick={() => (currentTab = "transforms")}
                    >
                        Transforms
                    </button>
                </div>
            </div>

            {#if currentTab === "live"}
                {#if subscribedStreams.size === 0}
                    <p class="no-data">Select streams to view live data</p>
                {:else}
                    <div class="stream-data-list">
                        {#each Array.from(subscribedStreams) as streamId}
                            {@const streamType = inferStreamType(streamId)}
                            {@const imuBuffer = imuBuffers.get(streamId) || []}
                            {@const museBuffer = museBuffers.get(streamId) || []}
                            {@const emgBuffer = emgBuffers.get(streamId) || []}
                            {@const latestImuSample =
                                imuBuffer[imuBuffer.length - 1]}
                            {@const latestMuseSample =
                                museBuffer[museBuffer.length - 1]}
                            {@const latestEmgSample =
                                emgBuffer[emgBuffer.length - 1]}
                            {@const transformProvenance =
                                transformProvenanceByStream.get(streamId)}
                            {@const transformConfigEntries =
                                transformProvenance
                                    ? parseTransformConfigJson(
                                          transformProvenance.config_json,
                                      )
                                    : []}
                            {@const primaryDescriptor =
                                getPrimaryDescriptor(streamId)}
                            {@const descriptorRecordValue =
                                getDescriptorRecordValue(
                                    streamType,
                                    latestImuSample,
                                    latestMuseSample,
                                    latestEmgSample,
                                )}
                            {@const rendererKind = chooseViewerRenderer(
                                primaryDescriptor,
                                latestEmgSample
                                    ? {
                                          n_channels:
                                              latestEmgSample.n_channels,
                                          samples_per_channel:
                                              latestEmgSample.samples_per_channel,
                                          channel_labels:
                                              latestEmgSample.channel_labels,
                                      }
                                    : undefined,
                            )}
                            {@const isExpanded = expandedStreams.has(streamId)}
                            {@const bufferSize =
                                streamType === "muse"
                                    ? museBuffer.length
                                    : streamType === "emg"
                                      ? emgBuffer.length
                                    : imuBuffer.length}
                            {@const hasData =
                                latestImuSample !== undefined ||
                                latestMuseSample !== undefined ||
                                latestEmgSample !== undefined}
                            {@const isUnreachable = isStreamUnreachable(streamId)}

                            <div
                                class="stream-data-card {isUnreachable
                                    ? 'stream-data-card-unreachable'
                                    : ''}"
                            >
                                <button
                                    class="card-header"
                                    onclick={() => toggleStreamExpanded(streamId)}
                                >
                                    <span class="stream-title"
                                        >Stream {streamId}</span
                                    >
                                    <span
                                        class="stream-type-badge {streamType ||
                                            'unknown'}"
                                        >{streamType === "muse"
                                            ? "Muse"
                                            : streamType === "emg"
                                              ? "EMG"
                                            : streamType === "imu"
                                              ? "IMU"
                                              : "..."}</span
                                    >
                                    <span
                                        class="stream-status-badge {getStreamStatusClass(
                                            streamId,
                                            hasData,
                                        )}"
                                        >{getStreamStatusLabel(
                                            streamId,
                                            hasData,
                                        )}</span
                                    >
                                    <span class="buffer-info"
                                        >{bufferSize} {streamType === "emg"
                                            ? "frames"
                                            : "samples"} buffered</span
                                    >
                                    <span class="expand-icon"
                                        >{isExpanded ? "−" : "+"}</span
                                    >
                                </button>

                                {#if isExpanded}
                                    {#if rendererKind === "muse"}
                                        {#if latestMuseSample}
                                            <div class="card-content">
                                                {#if isUnreachable}
                                                    <p
                                                        class="sensor-unreachable-note"
                                                    >
                                                        Sensor may be unreachable:
                                                        no data received for 3s+
                                                    </p>
                                                {/if}
                                                {#if primaryDescriptor}
                                                    <SchemaDescriptorInspector
                                                        descriptor={primaryDescriptor}
                                                        recordValue={descriptorRecordValue}
                                                    />
                                                {/if}
                                                <MuseViewer
                                                    sample={latestMuseSample}
                                                    {formatNumber}
                                                />
                                            </div>
                                        {:else}
                                            <div class="card-content">
                                                <p class="waiting">
                                                    Waiting for Muse data...
                                                </p>
                                            </div>
                                        {/if}
                                    {:else if rendererKind === "classification" || rendererKind === "feature_vector" || rendererKind === "channel_frame"}
                                        {#if latestEmgSample}
                                            <div class="card-content">
                                                {#if isUnreachable}
                                                    <p
                                                        class="sensor-unreachable-note"
                                                    >
                                                        Sensor may be unreachable:
                                                        no data received for 3s+
                                                    </p>
                                                {/if}
                                                {#if primaryDescriptor}
                                                    <SchemaDescriptorInspector
                                                        descriptor={primaryDescriptor}
                                                        recordValue={descriptorRecordValue}
                                                    />
                                                {/if}
                                                {#if transformProvenance}
                                                    <section
                                                        class="transform-provenance"
                                                    >
                                                        <div
                                                            class="transform-provenance-header"
                                                        >
                                                            <h4>
                                                                Derived Stream
                                                            </h4>
                                                            <span
                                                                class="mapping-badge"
                                                            >
                                                                {transformProvenance.input_mapping_id}
                                                            </span>
                                                        </div>
                                                        <div
                                                            class="transform-provenance-grid"
                                                        >
                                                            <div>
                                                                <span
                                                                    class="meta-label"
                                                                    >Kind</span
                                                                >
                                                                <span
                                                                    class="meta-value"
                                                                    >{transformProvenance.transform_kind}</span
                                                                >
                                                            </div>
                                                            <div>
                                                                <span
                                                                    class="meta-label"
                                                                    >Source</span
                                                                >
                                                                <span
                                                                    class="meta-value"
                                                                    >Stream {transformProvenance.source_stream_id}</span
                                                                >
                                                            </div>
                                                            <div>
                                                                <span
                                                                    class="meta-label"
                                                                    >Schema</span
                                                                >
                                                                <span
                                                                    class="meta-value"
                                                                    >{transformProvenance.source_schema_name}</span
                                                                >
                                                            </div>
                                                            <div>
                                                                <span
                                                                    class="meta-label"
                                                                    >Created</span
                                                                >
                                                                <span
                                                                    class="meta-value"
                                                                    >{formatTimestampUs(
                                                                        transformProvenance.created_at_us,
                                                                    )}</span
                                                                >
                                                            </div>
                                                        </div>
                                                        {#if transformConfigEntries.length > 0}
                                                            <div
                                                                class="transform-config-list"
                                                            >
                                                                {#each transformConfigEntries as entry}
                                                                    <div
                                                                        class="transform-config-item"
                                                                    >
                                                                        <span
                                                                            class="meta-label"
                                                                            >{entry.key}</span
                                                                        >
                                                                        <span
                                                                            class="meta-value"
                                                                            >{entry.value}</span
                                                                        >
                                                                    </div>
                                                                {/each}
                                                            </div>
                                                        {/if}
                                                    </section>
                                                {/if}
                                                {#if rendererKind === "classification"}
                                                    <ClassificationViewer
                                                        samples={emgBuffer}
                                                        {formatNumber}
                                                    />
                                                {:else if rendererKind === "feature_vector"}
                                                    <FeatureVectorViewer
                                                        samples={emgBuffer}
                                                        {formatNumber}
                                                    />
                                                {:else}
                                                    <ChannelFrameViewer
                                                        samples={emgBuffer}
                                                        {formatNumber}
                                                    />
                                                {/if}
                                            </div>
                                        {:else}
                                            <div class="card-content">
                                                <p class="waiting">
                                                    Waiting for EMG data...
                                                </p>
                                            </div>
                                        {/if}
                                    {:else}
                                        <div class="card-content">
                                            {#if isUnreachable}
                                                <p class="sensor-unreachable-note">
                                                    Sensor may be unreachable: no
                                                    data received for 3s+
                                                </p>
                                            {/if}
                                            {#if primaryDescriptor}
                                                <SchemaDescriptorInspector
                                                    descriptor={primaryDescriptor}
                                                    recordValue={descriptorRecordValue}
                                                />
                                            {:else}
                                                <p class="waiting">
                                                    Waiting for data...
                                                </p>
                                            {/if}
                                        </div>
                                    {/if}
                                {/if}
                            </div>
                        {/each}
                    </div>
                {/if}
            {:else if currentTab === "experiment"}
                <EmgExperiment
                    {emgStreams}
                    {emgBuffers}
                    {ensureStreamSubscribed}
                    {publishSessionBundle}
                    {lastPublishResult}
                />
            {:else if currentTab === "transforms"}
                <EmgTransforms
                    emgStreams={transformSourceStreams}
                    {createEmgTransform}
                    {stopEmgTransform}
                    {lastTransformResult}
                    {transformCapabilities}
                    {emgTransforms}
                    emgTransformWorkerId={emgTransformWorkerId}
                    emgTransformSlotCapacity={emgTransformSlotCapacity}
                    emgTransformActiveCount={emgTransformActiveCount}
                    emgTransformAvailableSlotCount={emgTransformAvailableSlotCount}
                    emgTransformUtilizationRatio={emgTransformUtilizationRatio}
                    emgTransformLastHeartbeatUs={emgTransformLastHeartbeatUs}
                    emgTransformWorkerStatus={emgTransformWorkerStatus}
                />
            {/if}
        </main>
    </div>
</div>

<style>
    .stream-viewer {
        min-height: calc(100vh - 56px);
        display: flex;
        flex-direction: column;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 1.5rem;
        background: white;
        border-bottom: 1px solid #e0e0e0;
    }

    .header h1 {
        margin: 0;
        font-size: 1.5rem;
        color: #1a1a2e;
    }

    .connection-status {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.875rem;
        font-weight: 500;
    }

    .status-connected {
        background: #d4edda;
        color: #155724;
    }

    .status-connecting {
        background: #fff3cd;
        color: #856404;
    }

    .transform-provenance {
        display: grid;
        gap: 0.75rem;
        padding: 0.9rem 1rem;
        border: 1px solid #d8e2ec;
        border-radius: 8px;
        background: #f8fbff;
        margin-bottom: 1rem;
    }

    .transform-provenance-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }

    .transform-provenance-header h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #223042;
    }

    .transform-provenance-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.75rem;
    }

    .transform-config-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.75rem;
    }

    .transform-config-item,
    .transform-provenance-grid > div {
        display: grid;
        gap: 0.2rem;
    }

    .meta-label {
        font-size: 0.72rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .meta-value {
        font-size: 0.9rem;
        color: #1e293b;
        word-break: break-word;
    }

    .mapping-badge {
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: #dbeafe;
        color: #1d4ed8;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .status-disconnected {
        background: #f8d7da;
        color: #721c24;
    }

    .error-banner {
        padding: 0.75rem 1.5rem;
        background: #f8d7da;
        color: #721c24;
        border-bottom: 1px solid #f5c6cb;
    }

    .main-content {
        display: flex;
        flex: 1;
        overflow: hidden;
    }

    .stream-panel {
        width: 300px;
        background: white;
        border-right: 1px solid #e0e0e0;
        overflow-y: auto;
        padding: 1rem;
    }

    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .panel-header h2 {
        margin: 0;
        font-size: 1rem;
        color: #333;
    }

    .refresh-btn {
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        background: #f0f0f0;
        border: 1px solid #ddd;
        border-radius: 4px;
        cursor: pointer;
    }

    .refresh-btn:hover {
        background: #e0e0e0;
    }

    .no-streams,
    .no-data {
        color: #666;
        font-style: italic;
    }

    .stream-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .stream-item {
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }

    .stream-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
        font-weight: 500;
    }

    .stream-label input {
        width: 16px;
        height: 16px;
    }

    .topic-list {
        list-style: none;
        padding-left: 1.5rem;
        margin: 0.5rem 0 0 0;
    }

    .topic-item {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: #666;
        margin-top: 0.25rem;
    }

    .topic-type {
        padding: 0.1rem 0.4rem;
        border-radius: 3px;
        font-size: 0.7rem;
        text-transform: uppercase;
    }

    .topic-type.data {
        background: #e3f2fd;
        color: #1565c0;
    }

    .topic-type.meta {
        background: #f3e5f5;
        color: #7b1fa2;
    }

    .topic-descriptor {
        padding: 0.1rem 0.4rem;
        border-radius: 999px;
        background: #dcfce7;
        color: #166534;
        font-size: 0.7rem;
        font-weight: 600;
    }

    .data-panel {
        flex: 1;
        padding: 1rem 1.5rem;
        overflow-y: auto;
    }

    .data-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .data-panel h2 {
        margin: 0;
        font-size: 1rem;
        color: #333;
    }

    .panel-tabs {
        display: inline-flex;
        gap: 0.25rem;
        padding: 0.25rem;
        background: #e2e8f0;
        border-radius: 999px;
    }

    .panel-tabs button {
        border: none;
        background: transparent;
        color: #475569;
        padding: 0.45rem 0.85rem;
        border-radius: 999px;
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
    }

    .panel-tabs button.active {
        background: #fff;
        color: #0f172a;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
    }

    .stream-data-list {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .stream-data-card {
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        overflow: hidden;
    }

    .stream-data-card-unreachable {
        border: 1px solid #f5c6cb;
    }

    .card-header {
        width: 100%;
        display: flex;
        justify-content: flex-start;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem;
        background: #f8f9fa;
        border: none;
        cursor: pointer;
        text-align: left;
    }

    .card-header:hover {
        background: #e9ecef;
    }

    .stream-title {
        font-weight: 600;
        color: #1a1a2e;
        margin-right: auto;
    }

    .stream-type-badge {
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 500;
        text-transform: uppercase;
    }

    .stream-type-badge.imu {
        background: #e3f2fd;
        color: #1565c0;
    }

    .stream-type-badge.muse {
        background: #f3e5f5;
        color: #7b1fa2;
    }

    .stream-type-badge.emg {
        background: #dcfce7;
        color: #166534;
    }

    .stream-type-badge.unknown {
        background: #f5f5f5;
        color: #666;
    }

    .stream-status-badge {
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 500;
        text-transform: uppercase;
    }

    .stream-status-live {
        background: #d4edda;
        color: #155724;
    }

    .stream-status-unreachable {
        background: #f8d7da;
        color: #721c24;
    }

    .stream-status-nodata {
        background: #f5f5f5;
        color: #666;
    }

    .buffer-info {
        font-size: 0.8rem;
        color: #666;
    }

    .expand-icon {
        font-size: 1.25rem;
        color: #666;
    }

    .card-content {
        padding: 1rem;
        display: grid;
        gap: 1rem;
    }

    .waiting {
        color: #666;
        font-style: italic;
    }

    .sensor-unreachable-note {
        margin: 0 0 0.75rem 0;
        padding: 0.6rem 0.75rem;
        border-radius: 6px;
        background: #fff3cd;
        color: #856404;
        font-size: 0.85rem;
    }

    @media (max-width: 720px) {
        .data-panel-header {
            flex-direction: column;
            align-items: stretch;
        }

        .panel-tabs {
            width: fit-content;
        }
    }
</style>
