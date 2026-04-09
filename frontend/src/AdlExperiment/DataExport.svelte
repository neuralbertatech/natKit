<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { Download, RotateCcw } from "lucide-svelte";
    import type { SessionData, Marker, ImuSample } from "./types";
    import { formatDuration } from "./tasks";

    let {
        sessionData,
        onNewSession = () => {},
    }: {
        sessionData: SessionData;
        onNewSession: () => void;
    } = $props();

    // Calculate session duration
    let sessionDuration = $derived(() => {
        if (!sessionData || sessionData.markers.length < 2) return 0;
        const startMarker = sessionData.markers.find(
            (m) => m.marker_type === "session_start",
        );
        const endMarker = sessionData.markers.find(
            (m) => m.marker_type === "session_end",
        );
        if (startMarker && endMarker) {
            return Math.round(
                (endMarker.timestamp - startMarker.timestamp) / 1000,
            );
        }
        return 0;
    });

    // Count task markers
    let taskCount = $derived(
        sessionData.markers.filter((m) => m.marker_type === "task_start")
            .length,
    );

    // Generate CSV content
    function generateCSV(): string {
        const headers = [
            "timestamp",
            "sensor_position",
            "calibration_status_accelerometer",
            "calibration_status_gyroscope",
            "calibration_status_rotation",
            "has_data_accelerometer",
            "has_data_gyroscope",
            "has_data_rotation",
            "quat_i",
            "quat_j",
            "quat_k",
            "quat_real",
            "accel_x",
            "accel_y",
            "accel_z",
            "gyro_x",
            "gyro_y",
            "gyro_z",
            "gravity_x",
            "gravity_y",
            "gravity_z",
            "marker_type",
            "task_id",
        ];

        const rows: string[] = [headers.join(",")];

        // Combine samples and markers, sort by timestamp
        type DataRow = {
            timestamp: number;
            type: "sample" | "marker";
            data: ImuSample | Marker;
        };
        const allData: DataRow[] = [];

        // Add samples
        for (const sample of sessionData.samples) {
            allData.push({
                timestamp: sample.timestamp,
                type: "sample",
                data: sample,
            });
        }

        // Add markers
        for (const marker of sessionData.markers) {
            allData.push({
                timestamp: marker.timestamp,
                type: "marker",
                data: marker,
            });
        }

        // Sort by timestamp
        allData.sort((a, b) => a.timestamp - b.timestamp);

        // Generate rows
        for (const item of allData) {
            if (item.type === "sample") {
                const s = item.data as ImuSample;
                rows.push(
                    [
                        s.timestamp.toString(),
                        s.sensor_position,
                        s.calibration_status_accelerometer.toString(),
                        s.calibration_status_gyroscope.toString(),
                        s.calibration_status_rotation.toString(),
                        s.has_data_accelerometer ? "1" : "0",
                        s.has_data_gyroscope ? "1" : "0",
                        s.has_data_rotation ? "1" : "0",
                        s.quat_i.toString(),
                        s.quat_j.toString(),
                        s.quat_k.toString(),
                        s.quat_real.toString(),
                        s.accel_x.toString(),
                        s.accel_y.toString(),
                        s.accel_z.toString(),
                        s.gyro_x.toString(),
                        s.gyro_y.toString(),
                        s.gyro_z.toString(),
                        s.gravity_x.toString(),
                        s.gravity_y.toString(),
                        s.gravity_z.toString(),
                        "",
                        "",
                    ].join(","),
                );
            } else {
                const m = item.data as Marker;
                const markerRowPrefix = [
                    m.timestamp.toString(),
                    ...Array(headers.length - 3).fill(""),
                ];
                rows.push(
                    [...markerRowPrefix, m.marker_type, m.task_id].join(","),
                );
            }
        }

        return rows.join("\n");
    }

    // Download CSV file
    function downloadCSV() {
        const csv = generateCSV();
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);

        const timestamp = new Date()
            .toISOString()
            .replace(/[:.]/g, "-")
            .slice(0, 19);
        const filename = `adl_experiment_${sessionData.session_id.slice(0, 8)}_${timestamp}.csv`;

        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    // Download markers only (for quick reference)
    function downloadMarkers() {
        const headers = ["timestamp", "marker_type", "task_id"];
        const rows: string[] = [headers.join(",")];

        for (const marker of sessionData.markers) {
            rows.push(
                [
                    marker.timestamp.toString(),
                    marker.marker_type,
                    marker.task_id,
                ].join(","),
            );
        }

        const csv = rows.join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);

        const timestamp = new Date()
            .toISOString()
            .replace(/[:.]/g, "-")
            .slice(0, 19);
        const filename = `adl_markers_${sessionData.session_id.slice(0, 8)}_${timestamp}.csv`;

        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
</script>

<div class="data-export">
    <h2><b>Session Complete</b></h2>

    <div class="session-summary">
        <h3>Session Summary</h3>
        <div class="summary-grid">
            <div class="summary-item">
                <span class="label">Session ID</span>
                <span class="value"
                    >{sessionData.session_id.slice(0, 8)}...</span
                >
            </div>
            <div class="summary-item">
                <span class="label">Duration</span>
                <span class="value">{formatDuration(sessionDuration())}</span>
            </div>
            <div class="summary-item">
                <span class="label">Tasks Completed</span>
                <span class="value">{taskCount}</span>
            </div>
            <div class="summary-item">
                <span class="label">Total Markers</span>
                <span class="value">{sessionData.marker_count}</span>
            </div>
            <div class="summary-item">
                <span class="label">IMU Samples</span>
                <span class="value"
                    >{sessionData.sample_count.toLocaleString()}</span
                >
            </div>
        </div>
    </div>

    <div class="marker-preview">
        <h3>Marker Events</h3>
        <div class="marker-list">
            {#each sessionData.markers as marker}
                <div
                    class="marker-item"
                    class:session={marker.marker_type.includes("session")}
                    class:task-start={marker.marker_type === "task_start"}
                    class:task-end={marker.marker_type === "task_end"}
                >
                    <span class="marker-time"
                        >{new Date(marker.timestamp).toLocaleTimeString()}</span
                    >
                    <span class="marker-type">{marker.marker_type}</span>
                    {#if marker.task_id}
                        <span class="marker-task">{marker.task_id}</span>
                    {/if}
                </div>
            {/each}
        </div>
    </div>

    <div class="export-actions">
        <h3>Export Data</h3>
        <div class="button-group">
            <Button onclick={downloadCSV}>
                <Download size={18} class="mr-2" />
                Download Full CSV
            </Button>
            <Button variant="outline" onclick={downloadMarkers}>
                <Download size={18} class="mr-2" />
                Download Markers Only
            </Button>
        </div>
        <p class="export-note">
            The full CSV contains all IMU data samples and markers sorted by
            timestamp.
        </p>
    </div>

    <div class="new-session">
        <Button variant="secondary" onclick={onNewSession}>
            <RotateCcw size={18} class="mr-2" />
            Start New Session
        </Button>
    </div>
</div>

<style>
    .data-export {
        padding: 1em;
    }

    h2 {
        text-align: center;
        color: #4caf50;
        margin-bottom: 1.5em;
    }

    h3 {
        margin: 0 0 0.75em 0;
        font-size: 1em;
        color: #333;
    }

    .session-summary {
        background-color: #f5f5f5;
        padding: 1.5em;
        border-radius: 8px;
        margin-bottom: 1.5em;
    }

    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1em;
    }

    .summary-item {
        display: flex;
        flex-direction: column;
    }

    .summary-item .label {
        font-size: 0.85em;
        color: #666;
    }

    .summary-item .value {
        font-size: 1.2em;
        font-weight: 500;
        color: #333;
    }

    .marker-preview {
        background-color: #fafafa;
        padding: 1.5em;
        border-radius: 8px;
        margin-bottom: 1.5em;
        max-height: 300px;
        overflow-y: auto;
    }

    .marker-list {
        display: flex;
        flex-direction: column;
        gap: 0.5em;
    }

    .marker-item {
        display: flex;
        gap: 1em;
        padding: 0.5em;
        background-color: white;
        border-radius: 4px;
        border-left: 3px solid #ccc;
    }

    .marker-item.session {
        border-left-color: #9c27b0;
        background-color: #f3e5f5;
    }

    .marker-item.task-start {
        border-left-color: #4caf50;
        background-color: #e8f5e9;
    }

    .marker-item.task-end {
        border-left-color: #ff9800;
        background-color: #fff3e0;
    }

    .marker-time {
        font-family: monospace;
        font-size: 0.85em;
        color: #666;
    }

    .marker-type {
        font-weight: 500;
        min-width: 100px;
    }

    .marker-task {
        color: #666;
    }

    .export-actions {
        background-color: #e3f2fd;
        padding: 1.5em;
        border-radius: 8px;
        margin-bottom: 1.5em;
    }

    .button-group {
        display: flex;
        gap: 1em;
        flex-wrap: wrap;
        margin-bottom: 0.75em;
    }

    .export-note {
        font-size: 0.85em;
        color: #666;
        margin: 0;
    }

    .new-session {
        text-align: center;
        padding-top: 1em;
        border-top: 1px solid #eee;
    }

    :global(.mr-2) {
        margin-right: 0.5em;
    }
</style>
