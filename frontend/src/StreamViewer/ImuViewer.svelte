<script lang="ts">
    import { onMount } from "svelte";
    import Chart from "chart.js/auto";
    import type { Chart as ChartInstance, ChartDataset } from "chart.js";
    import type { ImuSample } from "./types";
    import OrientationView from "./OrientationView.svelte";

    interface Props {
        samples: ImuSample[];
        formatNumber: (num: number, decimals?: number) => string;
        // Compact mode (on-canvas node preview): drop the summary/controls and
        // shrink the chart.
        compact?: boolean;
    }

    interface SeriesPoint {
        x: number;
        y: number;
    }

    let { samples, formatNumber, compact = false }: Props = $props();

    type Group = "accel" | "gyro" | "quat";
    const GROUPS: { key: Group; label: string; unit: string }[] = [
        { key: "accel", label: "Accelerometer", unit: "m/s²" },
        { key: "gyro", label: "Gyroscope", unit: "rad/s" },
        // The quaternion is presented as a 3D orientation (arrow-in-a-sphere +
        // Euler readout) rather than four raw component traces.
        { key: "quat", label: "Orientation", unit: "" },
    ];

    // Below these peak-to-peak spans the sensor is treated as stationary — the
    // whole reason this viewer exists: at rest the numbers barely move, which
    // reads as "stalled" even while data streams. Tuned for a resting BNO08x
    // (gravity-only accel, ~0 gyro).
    const STATIONARY_ACCEL_PP = 0.4; // m/s²
    const STATIONARY_GYRO_PP = 0.06; // rad/s

    const SERIES_COLORS = ["#dc2626", "#16a34a", "#2563eb", "#a855f7"];

    let selectedGroup = $state<Group>("accel");
    let chartCanvas = $state<HTMLCanvasElement | null>(null);
    let chart: ChartInstance<"line", SeriesPoint[]> | null = null;

    function seriesForGroup(group: Group): {
        label: string;
        pick: (s: ImuSample) => number;
    }[] {
        if (group === "accel") {
            return [
                { label: "x", pick: (s) => s.data.accel.x },
                { label: "y", pick: (s) => s.data.accel.y },
                { label: "z", pick: (s) => s.data.accel.z },
            ];
        }
        if (group === "gyro") {
            return [
                { label: "x", pick: (s) => s.data.gyro.x },
                { label: "y", pick: (s) => s.data.gyro.y },
                { label: "z", pick: (s) => s.data.gyro.z },
            ];
        }
        return [
            { label: "w", pick: (s) => s.data.quat.real },
            { label: "i", pick: (s) => s.data.quat.i },
            { label: "j", pick: (s) => s.data.quat.j },
            { label: "k", pick: (s) => s.data.quat.k },
        ];
    }

    // x = seconds relative to the newest sample (0 = now, negative = past). Uses
    // the device timestamp when it looks sane, else falls back to even index
    // spacing so a zero/garbage clock still plots a readable trace.
    function timeAxis(frames: ImuSample[]): number[] {
        const n = frames.length;
        if (n === 0) return [];
        const last = frames[n - 1].timestamp;
        const first = frames[0].timestamp;
        const monotonic = last > first && last - first < 1_000_000_000;
        if (monotonic) {
            return frames.map((s) => (s.timestamp - last) / 1000);
        }
        // Fallback: assume ~100 Hz spacing anchored at now.
        return frames.map((_, i) => (i - (n - 1)) / 100);
    }

    function ptp(values: number[]): number {
        if (values.length === 0) return 0;
        let min = values[0];
        let max = values[0];
        for (const v of values) {
            if (v < min) min = v;
            if (v > max) max = v;
        }
        return max - min;
    }

    const latest = $derived(samples.at(-1));

    // Peak-to-peak of accel/gyro magnitude across the buffer → "is it moving?".
    const motion = $derived.by(() => {
        if (samples.length < 2) {
            return { stationary: false, accelPp: 0, gyroPp: 0 };
        }
        const accelMag = samples.map((s) =>
            Math.hypot(s.data.accel.x, s.data.accel.y, s.data.accel.z),
        );
        const gyroMag = samples.map((s) =>
            Math.hypot(s.data.gyro.x, s.data.gyro.y, s.data.gyro.z),
        );
        const accelPp = ptp(accelMag);
        const gyroPp = ptp(gyroMag);
        return {
            accelPp,
            gyroPp,
            stationary:
                accelPp < STATIONARY_ACCEL_PP && gyroPp < STATIONARY_GYRO_PP,
        };
    });

    function syncChart(): void {
        // Orientation is rendered by the OrientationView overlay, not the line
        // chart — skip the (hidden) chart rebuild while it's selected.
        if (!chart || selectedGroup === "quat") return;
        const frames = samples;
        const xs = timeAxis(frames);
        const series = seriesForGroup(selectedGroup);
        const datasets: ChartDataset<"line", SeriesPoint[]>[] = series.map(
            (s, idx) => ({
                label: s.label,
                data: frames.map((frame, i) => ({ x: xs[i], y: s.pick(frame) })),
                borderColor: SERIES_COLORS[idx % SERIES_COLORS.length],
                backgroundColor: `${SERIES_COLORS[idx % SERIES_COLORS.length]}22`,
                borderWidth: 1.75,
                pointRadius: 0,
                pointHoverRadius: 0,
                tension: 0.12,
            }),
        );
        const minX = xs.length > 0 ? xs[0] : -1;
        chart.data.datasets = datasets;
        chart.options.scales = {
            x: {
                type: "linear",
                min: Math.min(minX, -0.001),
                max: 0,
                grid: { color: "rgba(148, 163, 184, 0.16)" },
                ticks: {
                    maxTicksLimit: 6,
                    callback: (value) => {
                        const n = Number(value);
                        return n === 0 ? "Now" : `${Math.abs(n).toFixed(1)}s`;
                    },
                },
                title: { display: !compact, text: "Recent history" },
            },
            y: {
                grid: { color: "rgba(148, 163, 184, 0.14)" },
                title: {
                    display: !compact,
                    text:
                        GROUPS.find((g) => g.key === selectedGroup)?.unit || "",
                },
            },
        };
        chart.update("none");
    }

    // Throttle redraws to ~22 fps. Data arrives at ~25 fps and each redraw rebuilds
    // the full multi-hundred-point dataset; syncing on every single frame adds
    // avoidable per-frame allocation/Chart.js work. A capped rate looks identical
    // and keeps the main thread quiet. (Same rationale as ChannelFrameViewer.)
    let lastSyncMs = 0;
    const MIN_SYNC_INTERVAL_MS = 45;
    $effect(() => {
        // track the buffer + selected group so this re-runs when they change
        samples;
        selectedGroup;
        const now = Date.now();
        if (now - lastSyncMs < MIN_SYNC_INTERVAL_MS) {
            return;
        }
        lastSyncMs = now;
        syncChart();
    });

    onMount(() => {
        if (!chartCanvas) return;
        chart = new Chart(chartCanvas, {
            type: "line",
            data: { datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                parsing: false,
                normalized: true,
                resizeDelay: 50,
                interaction: { intersect: false, mode: "nearest" },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            usePointStyle: true,
                            boxWidth: 8,
                            boxHeight: 8,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: (item) =>
                                `${item.dataset.label}: ${formatNumber(
                                    item.parsed.y ?? 0,
                                    3,
                                )}`,
                        },
                    },
                },
            },
        });
        syncChart();
        return () => {
            chart?.destroy();
            chart = null;
        };
    });
</script>

<div class="imu-viewer" class:compact>
    {#if latest}
        {#if !compact && motion.stationary}
            <p class="steady-note">
                Sensor appears stationary — values are steady (accel Δ {formatNumber(
                    motion.accelPp,
                    2,
                )} m/s², gyro Δ {formatNumber(motion.gyroPp, 3)} rad/s). Data is
                still streaming; move the sensor to see the trace change.
            </p>
        {/if}

        {#if !compact}
            <div class="imu-summary">
                <div>
                    <span class="label">Accel (m/s²)</span>
                    {formatNumber(latest.data.accel.x, 2)}, {formatNumber(
                        latest.data.accel.y,
                        2,
                    )}, {formatNumber(latest.data.accel.z, 2)}
                </div>
                <div>
                    <span class="label">Gyro (rad/s)</span>
                    {formatNumber(latest.data.gyro.x, 3)}, {formatNumber(
                        latest.data.gyro.y,
                        3,
                    )}, {formatNumber(latest.data.gyro.z, 3)}
                </div>
                <div>
                    <span class="label">Quat (w,i,j,k)</span>
                    {formatNumber(latest.data.quat.real, 3)}, {formatNumber(
                        latest.data.quat.i,
                        3,
                    )}, {formatNumber(latest.data.quat.j, 3)}, {formatNumber(
                        latest.data.quat.k,
                        3,
                    )}
                </div>
                <div>
                    <span class="label">Accuracy (a/g/r)</span>
                    {latest.accuracies.accelerometer}/{latest.accuracies
                        .gyroscope}/{latest.accuracies.rotation}
                </div>
            </div>
        {/if}

        <div class="graph-section">
            {#if !compact}
                <div class="graph-head">
                    <h4>Rolling Trace</h4>
                    <div class="group-controls" aria-label="Signal group">
                        {#each GROUPS as option}
                            <button
                                type="button"
                                class:selected={selectedGroup === option.key}
                                onclick={() => {
                                    selectedGroup = option.key;
                                }}
                            >
                                {option.label}
                            </button>
                        {/each}
                    </div>
                </div>
            {/if}
            <div class="chart-wrap">
                <canvas bind:this={chartCanvas}></canvas>
                {#if selectedGroup === "quat" && latest}
                    <div class="orientation-overlay">
                        <OrientationView
                            quat={latest.data.quat}
                            {formatNumber}
                        />
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .imu-viewer {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .steady-note {
        margin: 0;
        padding: 0.6rem 0.75rem;
        border-radius: 8px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e40af;
        font-size: 0.85rem;
        line-height: 1.4;
    }

    .imu-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 0.75rem;
        font-family: monospace;
        font-size: 0.85rem;
        color: #334155;
    }

    .label {
        display: block;
        margin-bottom: 0.2rem;
        color: #64748b;
        font-size: 0.72rem;
        text-transform: uppercase;
        font-family: system-ui, sans-serif;
    }

    .graph-section {
        display: grid;
        gap: 0.75rem;
    }

    .graph-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .graph-head h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #0f172a;
    }

    .group-controls {
        display: inline-flex;
        border: 1px solid #dbe3ee;
        border-radius: 8px;
        overflow: hidden;
        background: #f8fafc;
    }

    .group-controls button {
        border: 0;
        background: transparent;
        padding: 0.45rem 0.7rem;
        font-size: 0.82rem;
        color: #475569;
        cursor: pointer;
    }

    .group-controls button.selected {
        background: #e2e8f0;
        color: #0f172a;
        font-weight: 600;
    }

    .chart-wrap {
        position: relative;
        min-height: 280px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: linear-gradient(
            to bottom,
            rgba(248, 250, 252, 0.96),
            rgba(255, 255, 255, 0.98)
        );
        padding: 0.75rem;
    }

    /* The orientation widget replaces the line chart in-place when selected. */
    .orientation-overlay {
        position: absolute;
        inset: 0;
        padding: 0.75rem;
        border-radius: 8px;
        background: linear-gradient(
            to bottom,
            rgba(248, 250, 252, 0.98),
            rgba(255, 255, 255, 1)
        );
    }

    .imu-viewer.compact {
        gap: 0;
        height: 100%;
    }

    .imu-viewer.compact .graph-section {
        height: 100%;
    }

    .imu-viewer.compact .chart-wrap {
        min-height: 0;
        height: 100%;
        padding: 0.35rem;
    }

    @media (max-width: 720px) {
        .chart-wrap {
            min-height: 240px;
            padding: 0.5rem;
        }
    }
</style>
