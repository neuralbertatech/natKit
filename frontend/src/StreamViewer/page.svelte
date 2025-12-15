<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { StreamViewerWebSocket, type ConnectionState } from "./websocket";
    import MuseViewer from "./MuseViewer.svelte";
    import type {
        StreamListMessage,
        StatusMessage,
        ImuDataMessage,
        ImuBulkDataMessage,
        MuseDataMessage,
        MuseBulkDataMessage,
        ImuSample,
        MuseSample,
        StreamInfo,
        ErrorMessage,
    } from "./types";

    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
    const WS_URL =
        BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://") +
        "/ws/stream_viewer";

    // Connection state
    let connectionState = $state<ConnectionState>("disconnected");
    let lastError = $state<string | null>(null);

    // Available streams from backend
    let availableStreams = $state<Record<string, StreamInfo>>({});

    // Currently subscribed streams
    let subscribedStreams = $state<Set<number>>(new Set());

    // Buffered samples per stream (circular buffer, max 100 samples)
    const MAX_BUFFER_SIZE = 100;
    let imuBuffers = $state<Map<number, ImuSample[]>>(new Map());
    let museBuffers = $state<Map<number, MuseSample[]>>(new Map());

    // Track stream types by stream ID
    let streamTypes = $state<Map<number, "imu" | "muse">>(new Map());

    // Expanded accordion state
    let expandedStreams = $state<Set<number>>(new Set());

    let wsManager: StreamViewerWebSocket | null = null;

    onMount(() => {
        wsManager = new StreamViewerWebSocket(WS_URL, {
            onConnectionChange: (state) => {
                connectionState = state;
                if (state === "connected") {
                    lastError = null;
                }
            },
            onStreamList: (message: StreamListMessage) => {
                availableStreams = message.streams;
            },
            onStatus: (message: StatusMessage) => {
                subscribedStreams = new Set(message.subscribed_streams);
            },
            onImuData: (message: ImuDataMessage) => {
                addImuSampleToBuffer(message.stream_id, {
                    timestamp: message.timestamp,
                    data: message.data,
                    accuracies: message.accuracies,
                    has_data: message.has_data,
                });
            },
            onImuBulkData: (message: ImuBulkDataMessage) => {
                for (const sample of message.samples) {
                    addImuSampleToBuffer(message.stream_id, sample);
                }
            },
            onMuseData: (message: MuseDataMessage) => {
                addMuseSampleToBuffer(message.stream_id, {
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
                    addMuseSampleToBuffer(message.stream_id, sample);
                }
            },
            onError: (message: ErrorMessage) => {
                lastError = message.message;
            },
        });

        wsManager.connect();
    });

    onDestroy(() => {
        wsManager?.disconnect();
    });

    function addImuSampleToBuffer(streamId: number, sample: ImuSample) {
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
    }

    function addMuseSampleToBuffer(streamId: number, sample: MuseSample) {
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
    }

    function toggleStreamSubscription(streamId: number) {
        if (subscribedStreams.has(streamId)) {
            wsManager?.unsubscribe([streamId]);
            // Clear buffers for this stream
            imuBuffers.delete(streamId);
            imuBuffers = new Map(imuBuffers);
            museBuffers.delete(streamId);
            museBuffers = new Map(museBuffers);
            streamTypes.delete(streamId);
            streamTypes = new Map(streamTypes);
        } else {
            wsManager?.subscribe([streamId]);
        }
    }

    function toggleStreamExpanded(streamId: number) {
        if (expandedStreams.has(streamId)) {
            expandedStreams.delete(streamId);
        } else {
            expandedStreams.add(streamId);
        }
        expandedStreams = new Set(expandedStreams);
    }

    function formatNumber(num: number, decimals: number = 4): string {
        return num.toFixed(decimals);
    }

    function getAccuracyLabel(value: number): string {
        switch (value) {
            case 0:
                return "Unreliable";
            case 1:
                return "Low";
            case 2:
                return "Medium";
            case 3:
                return "High";
            default:
                return "Unknown";
        }
    }

    function getAccuracyClass(value: number): string {
        switch (value) {
            case 0:
                return "accuracy-unreliable";
            case 1:
                return "accuracy-low";
            case 2:
                return "accuracy-medium";
            case 3:
                return "accuracy-high";
            default:
                return "";
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

    function refreshStreams() {
        wsManager?.requestStreamList();
    }
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
                        {@const streamId = parseInt(streamIdStr)}
                        <li class="stream-item">
                            <label class="stream-label">
                                <input
                                    type="checkbox"
                                    checked={subscribedStreams.has(streamId)}
                                    onchange={() =>
                                        toggleStreamSubscription(streamId)}
                                />
                                <span class="stream-id">Stream {streamId}</span>
                            </label>
                            <ul class="topic-list">
                                {#each streamInfo.topics as topic}
                                    <li class="topic-item">
                                        <span
                                            class="topic-type {topic.type.toLowerCase()}"
                                            >{topic.type}</span
                                        >
                                        <span class="topic-schema"
                                            >{topic.schema_name}</span
                                        >
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
            <h2>Live Data</h2>

            {#if subscribedStreams.size === 0}
                <p class="no-data">Select streams to view live data</p>
            {:else}
                <div class="stream-data-list">
                    {#each Array.from(subscribedStreams) as streamId}
                        {@const streamType = streamTypes.get(streamId)}
                        {@const imuBuffer = imuBuffers.get(streamId) || []}
                        {@const museBuffer = museBuffers.get(streamId) || []}
                        {@const latestImuSample =
                            imuBuffer[imuBuffer.length - 1]}
                        {@const latestMuseSample =
                            museBuffer[museBuffer.length - 1]}
                        {@const isExpanded = expandedStreams.has(streamId)}
                        {@const bufferSize =
                            streamType === "muse"
                                ? museBuffer.length
                                : imuBuffer.length}

                        <div class="stream-data-card">
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
                                        : streamType === "imu"
                                          ? "IMU"
                                          : "..."}</span
                                >
                                <span class="buffer-info"
                                    >{bufferSize} samples buffered</span
                                >
                                <span class="expand-icon"
                                    >{isExpanded ? "−" : "+"}</span
                                >
                            </button>

                            {#if isExpanded}
                                {#if streamType === "muse"}
                                    {#if latestMuseSample}
                                        <div class="card-content">
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
                                {:else if streamType === "imu"}
                                    {#if latestImuSample}
                                        <div class="card-content">
                                            <!-- Accelerometer -->
                                            <div class="sensor-section">
                                                <h4>
                                                    Accelerometer (m/s²)
                                                    <span
                                                        class="accuracy-badge {getAccuracyClass(
                                                            latestImuSample
                                                                .accuracies
                                                                .accelerometer,
                                                        )}"
                                                    >
                                                        {getAccuracyLabel(
                                                            latestImuSample
                                                                .accuracies
                                                                .accelerometer,
                                                        )}
                                                    </span>
                                                </h4>
                                                <div class="sensor-values">
                                                    <span
                                                        >X: {formatNumber(
                                                            latestImuSample.data
                                                                .accel.x,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Y: {formatNumber(
                                                            latestImuSample.data
                                                                .accel.y,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Z: {formatNumber(
                                                            latestImuSample.data
                                                                .accel.z,
                                                        )}</span
                                                    >
                                                </div>
                                            </div>

                                            <!-- Gyroscope -->
                                            <div class="sensor-section">
                                                <h4>
                                                    Gyroscope (rad/s)
                                                    <span
                                                        class="accuracy-badge {getAccuracyClass(
                                                            latestImuSample
                                                                .accuracies
                                                                .gyroscope,
                                                        )}"
                                                    >
                                                        {getAccuracyLabel(
                                                            latestImuSample
                                                                .accuracies
                                                                .gyroscope,
                                                        )}
                                                    </span>
                                                </h4>
                                                <div class="sensor-values">
                                                    <span
                                                        >X: {formatNumber(
                                                            latestImuSample.data
                                                                .gyro.x,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Y: {formatNumber(
                                                            latestImuSample.data
                                                                .gyro.y,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Z: {formatNumber(
                                                            latestImuSample.data
                                                                .gyro.z,
                                                        )}</span
                                                    >
                                                </div>
                                            </div>

                                            <!-- Quaternion -->
                                            <div class="sensor-section">
                                                <h4>
                                                    Rotation Quaternion
                                                    <span
                                                        class="accuracy-badge {getAccuracyClass(
                                                            latestImuSample
                                                                .accuracies
                                                                .rotation,
                                                        )}"
                                                    >
                                                        {getAccuracyLabel(
                                                            latestImuSample
                                                                .accuracies
                                                                .rotation,
                                                        )}
                                                    </span>
                                                </h4>
                                                <div
                                                    class="sensor-values quaternion"
                                                >
                                                    <span
                                                        >W: {formatNumber(
                                                            latestImuSample.data
                                                                .quat.real,
                                                        )}</span
                                                    >
                                                    <span
                                                        >X: {formatNumber(
                                                            latestImuSample.data
                                                                .quat.i,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Y: {formatNumber(
                                                            latestImuSample.data
                                                                .quat.j,
                                                        )}</span
                                                    >
                                                    <span
                                                        >Z: {formatNumber(
                                                            latestImuSample.data
                                                                .quat.k,
                                                        )}</span
                                                    >
                                                </div>
                                            </div>

                                            <!-- Timestamp -->
                                            <div class="timestamp-section">
                                                <span class="timestamp-label"
                                                    >Timestamp:</span
                                                >
                                                <span class="timestamp-value"
                                                    >{latestImuSample.timestamp}</span
                                                >
                                            </div>
                                        </div>
                                    {:else}
                                        <div class="card-content">
                                            <p class="waiting">
                                                Waiting for IMU data...
                                            </p>
                                        </div>
                                    {/if}
                                {:else}
                                    <div class="card-content">
                                        <p class="waiting">
                                            Waiting for data...
                                        </p>
                                    </div>
                                {/if}
                            {/if}
                        </div>
                    {/each}
                </div>
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

    .data-panel {
        flex: 1;
        padding: 1rem 1.5rem;
        overflow-y: auto;
    }

    .data-panel h2 {
        margin: 0 0 1rem 0;
        font-size: 1rem;
        color: #333;
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

    .card-header {
        width: 100%;
        display: flex;
        justify-content: space-between;
        align-items: center;
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

    .stream-type-badge.unknown {
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
    }

    .sensor-section {
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }

    .sensor-section:last-of-type {
        border-bottom: none;
        margin-bottom: 0.5rem;
        padding-bottom: 0.5rem;
    }

    .sensor-section h4 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
        color: #333;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .sensor-values {
        display: flex;
        gap: 1.5rem;
        font-family: monospace;
        font-size: 0.9rem;
    }

    .sensor-values.quaternion {
        flex-wrap: wrap;
    }

    .accuracy-badge {
        padding: 0.15rem 0.5rem;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: normal;
    }

    .accuracy-unreliable {
        background: #f8d7da;
        color: #721c24;
    }

    .accuracy-low {
        background: #fff3cd;
        color: #856404;
    }

    .accuracy-medium {
        background: #d1ecf1;
        color: #0c5460;
    }

    .accuracy-high {
        background: #d4edda;
        color: #155724;
    }

    .timestamp-section {
        font-size: 0.8rem;
        color: #666;
        padding-top: 0.5rem;
        border-top: 1px solid #eee;
    }

    .timestamp-label {
        font-weight: 500;
    }

    .timestamp-value {
        font-family: monospace;
    }

    .waiting {
        color: #666;
        font-style: italic;
    }
</style>
