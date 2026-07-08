<script lang="ts">
    import { onMount } from "svelte";
    import Chart from "chart.js/auto";
    import type { Chart as ChartInstance, ChartDataset } from "chart.js";
    import type { BufferedEmgSample } from "./types";

    interface Props {
        samples: BufferedEmgSample[];
        formatNumber: (num: number, decimals?: number) => string;
    }

    interface ChartRenderState {
        datasets: ChartDataset<"line", SeriesPoint[]>[];
        yMin: number;
        yMax: number;
    }

    interface SeriesPoint {
        x: number;
        y: number;
    }

    const CHART_COLORS = [
        "#0f766e",
        "#2563eb",
        "#7c3aed",
        "#ea580c",
        "#dc2626",
        "#65a30d",
    ];
    const DISPLAY_WINDOWS = [
        { label: "5s", ms: 5000 },
        { label: "10s", ms: 10000 },
        { label: "20s", ms: 20000 },
    ];
    const MAX_POINTS_PER_CHANNEL = 1600;

    let { samples, formatNumber }: Props = $props();

    let chartCanvas = $state<HTMLCanvasElement | null>(null);
    let selectedWindowMs = $state(10000);
    let renderClockMs = $state(Date.now());

    let chart: ChartInstance<"line", SeriesPoint[]> | null = null;
    let animationFrameId: number | null = null;

    function clamp(value: number, min: number, max: number): number {
        return Math.min(max, Math.max(min, value));
    }

    function getChannelColor(index: number): string {
        return CHART_COLORS[index % CHART_COLORS.length];
    }

    function getChannelStats(values: number[]) {
        let min = Number.POSITIVE_INFINITY;
        let max = Number.NEGATIVE_INFINITY;
        let sum = 0;
        let sumSquares = 0;
        for (const value of values) {
            min = Math.min(min, value);
            max = Math.max(max, value);
            sum += value;
            sumSquares += value * value;
        }
        const mean = values.length > 0 ? sum / values.length : 0;
        const rms =
            values.length > 0 ? Math.sqrt(sumSquares / values.length) : 0;
        return {
            min: Number.isFinite(min) ? min : 0,
            max: Number.isFinite(max) ? max : 0,
            mean,
            rms,
            last: values.at(-1) ?? 0,
        };
    }

    function getFrameDurationMs(sample: BufferedEmgSample): number {
        if (sample.frame_duration_ms > 0) {
            return sample.frame_duration_ms;
        }
        if (sample.sample_rate_hz > 0) {
            return Math.max(
                1,
                (sample.samples_per_channel / sample.sample_rate_hz) * 1000,
            );
        }
        return 1000;
    }

    function getVisibleSampleCount(
        sample: BufferedEmgSample | undefined,
        nowMs: number,
    ): number {
        if (!sample) {
            return 0;
        }

        const durationMs = getFrameDurationMs(sample);
        const elapsedMs = nowMs - sample.received_at_ms;
        const fraction = clamp(elapsedMs / durationMs, 0, 1);
        if (fraction <= 0) {
            return 0;
        }

        const rawCount = Math.floor(fraction * sample.samples_per_channel);
        if (fraction < 1 && rawCount === 0) {
            return 1;
        }

        return Math.min(sample.samples_per_channel, rawCount);
    }

    function downsampleMinMax(
        points: SeriesPoint[],
        maxPoints: number,
    ): SeriesPoint[] {
        if (points.length <= maxPoints || maxPoints < 4) {
            return points;
        }

        const bucketCount = Math.max(1, Math.floor(maxPoints / 2));
        const bucketSize = points.length / bucketCount;
        const result: SeriesPoint[] = [];

        for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
            const start = Math.floor(bucketIndex * bucketSize);
            const end = Math.min(
                points.length,
                Math.floor((bucketIndex + 1) * bucketSize),
            );

            if (start >= end) {
                continue;
            }

            let minPoint = points[start];
            let maxPoint = points[start];

            for (let pointIndex = start + 1; pointIndex < end; pointIndex += 1) {
                const point = points[pointIndex];
                if (point.y < minPoint.y) {
                    minPoint = point;
                }
                if (point.y > maxPoint.y) {
                    maxPoint = point;
                }
            }

            if (minPoint.x <= maxPoint.x) {
                result.push(minPoint, maxPoint);
            } else {
                result.push(maxPoint, minPoint);
            }
        }

        if (result[0]?.x !== points[0]?.x || result[0]?.y !== points[0]?.y) {
            result.unshift(points[0]);
        }

        const lastPoint = points.at(-1);
        if (
            lastPoint &&
            (result.at(-1)?.x !== lastPoint.x || result.at(-1)?.y !== lastPoint.y)
        ) {
            result.push(lastPoint);
        }

        const deduped: SeriesPoint[] = [];
        for (const point of result) {
            const prev = deduped.at(-1);
            if (!prev || prev.x !== point.x || prev.y !== point.y) {
                deduped.push(point);
            }
        }

        return deduped;
    }

    function buildChartState(
        frames: BufferedEmgSample[],
        nowMs: number,
        visibleWindowMs: number,
    ): ChartRenderState {
        if (frames.length === 0) {
            return {
                datasets: [],
                yMin: 0,
                yMax: 1,
            };
        }

        const channelCount = Math.max(...frames.map((frame) => frame.n_channels));
        const fullSeries = Array.from(
            { length: channelCount },
            () => [] as SeriesPoint[],
        );

        let timelineCursorMs = 0;
        let visibleEndMs = 0;

        for (const frame of frames) {
            const frameDurationMs = getFrameDurationMs(frame);
            const stepMs =
                frame.samples_per_channel > 0
                    ? frameDurationMs / frame.samples_per_channel
                    : frameDurationMs;
            const visibleCount = getVisibleSampleCount(frame, nowMs);
            const clampedVisibleDurationMs = Math.min(
                frameDurationMs,
                visibleCount * stepMs,
            );

            if (visibleCount > 0) {
                visibleEndMs = timelineCursorMs + clampedVisibleDurationMs;
                const activeChannels = Math.min(channelCount, frame.payload.length);
                for (
                    let channelIndex = 0;
                    channelIndex < activeChannels;
                    channelIndex += 1
                ) {
                    const values = frame.payload[channelIndex] ?? [];
                    const sampleCount = Math.min(visibleCount, values.length);
                    const points = fullSeries[channelIndex];
                    for (let sampleIndex = 0; sampleIndex < sampleCount; sampleIndex += 1) {
                        points.push({
                            x: timelineCursorMs + sampleIndex * stepMs,
                            y: values[sampleIndex],
                        });
                    }
                }
            }

            timelineCursorMs += frameDurationMs;
        }

        const windowStartMs = Math.max(0, visibleEndMs - visibleWindowMs);
        let yMin = Number.POSITIVE_INFINITY;
        let yMax = Number.NEGATIVE_INFINITY;

        const datasets = fullSeries.map((points, channelIndex) => {
            const filtered = points.filter((point) => point.x >= windowStartMs);
            const shifted = filtered.map((point) => ({
                x: (point.x - visibleEndMs) / 1000,
                y: point.y,
            }));

            for (const point of shifted) {
                yMin = Math.min(yMin, point.y);
                yMax = Math.max(yMax, point.y);
            }

            const latestFrame = frames.at(-1);
            const label =
                latestFrame?.channel_labels[channelIndex] ??
                `ch${channelIndex + 1}`;

            return {
                label,
                data: downsampleMinMax(shifted, MAX_POINTS_PER_CHANNEL),
                borderColor: getChannelColor(channelIndex),
                backgroundColor: `${getChannelColor(channelIndex)}22`,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 0,
                tension: 0.16,
            } satisfies ChartDataset<"line", SeriesPoint[]>;
        });

        if (!Number.isFinite(yMin) || !Number.isFinite(yMax)) {
            yMin = 0;
            yMax = 1;
        } else if (yMin === yMax) {
            yMin -= 1;
            yMax += 1;
        } else {
            const padding = (yMax - yMin) * 0.14;
            yMin -= padding;
            yMax += padding;
        }

        return { datasets, yMin, yMax };
    }

    function formatPayload(sampleToFormat: BufferedEmgSample): string {
        return JSON.stringify(
            {
                schema_version: sampleToFormat.schema_version,
                device_id: sampleToFormat.device_id,
                seq_no: sampleToFormat.seq_no,
                device_ts_us: sampleToFormat.device_ts_us,
                n_channels: sampleToFormat.n_channels,
                samples_per_channel: sampleToFormat.samples_per_channel,
                sample_rate_hz: sampleToFormat.sample_rate_hz,
                channel_labels: sampleToFormat.channel_labels,
                payload: sampleToFormat.payload,
            },
            null,
            2,
        );
    }

    function formatRecentValues(values: number[], count: number = 10): string {
        return values
            .slice(-count)
            .map((value) => formatNumber(value, 2))
            .join(", ");
    }

    function getBufferedDurationMs(frames: BufferedEmgSample[]): number {
        return frames.reduce(
            (total, frame) => total + getFrameDurationMs(frame),
            0,
        );
    }

    function getObservedDeliveryMetrics(frames: BufferedEmgSample[]) {
        if (frames.length < 2) {
            return {
                frameRateHz: 0,
                sampleRateHz: 0,
                batchIntervalMs: 0,
            };
        }

        const first = frames[0].received_at_ms;
        const last = frames[frames.length - 1].received_at_ms;
        const durationMs = Math.max(1, last - first);
        const frameRateHz = ((frames.length - 1) * 1000) / durationMs;
        const latest = frames[frames.length - 1];
        const sampleRateHz = frameRateHz * latest.samples_per_channel;
        const batchIntervalMs = 1000 / frameRateHz;

        return {
            frameRateHz,
            sampleRateHz,
            batchIntervalMs,
        };
    }

    function syncChart(): void {
        if (!chart) {
            return;
        }

        const { datasets, yMin, yMax } = buildChartState(
            samples,
            renderClockMs,
            selectedWindowMs,
        );

        chart.data.datasets = datasets;
        chart.options.scales = {
            x: {
                type: "linear",
                min: -(selectedWindowMs / 1000),
                max: 0,
                grid: {
                    color: "rgba(148, 163, 184, 0.16)",
                },
                ticks: {
                    maxTicksLimit: 6,
                    callback: (value) => {
                        const numericValue = Number(value);
                        if (numericValue === 0) {
                            return "Now";
                        }
                        return `${Math.abs(numericValue).toFixed(0)}s`;
                    },
                },
                title: {
                    display: true,
                    text: "Recent history",
                },
            },
            y: {
                min: yMin,
                max: yMax,
                grid: {
                    color: "rgba(148, 163, 184, 0.14)",
                },
                title: {
                    display: true,
                    text: "Amplitude",
                },
            },
        };

        chart.update("none");
    }

    function startAnimationLoop(): void {
        renderClockMs = Date.now();
        syncChart();
        animationFrameId = requestAnimationFrame(startAnimationLoop);
    }

    $effect(() => {
        selectedWindowMs;
        samples;
        syncChart();
    });

    onMount(() => {
        if (!chartCanvas) {
            return;
        }

        chart = new Chart(chartCanvas, {
            type: "line",
            data: {
                datasets: [],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                parsing: false,
                normalized: true,
                resizeDelay: 50,
                interaction: {
                    intersect: false,
                    mode: "nearest",
                },
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
                            title: (items) => {
                                const point = items[0];
                                const timeAgoSec = Math.abs(point.parsed.x ?? 0);
                                return timeAgoSec < 0.05
                                    ? "Now"
                                    : `${timeAgoSec.toFixed(3)}s ago`;
                            },
                            label: (item) =>
                                `${item.dataset.label}: ${formatNumber(
                                    item.parsed.y ?? 0,
                                    2,
                                )}`,
                        },
                    },
                },
                elements: {
                    line: {
                        capBezierPoints: false,
                    },
                },
            },
        });

        startAnimationLoop();

        return () => {
            if (animationFrameId !== null) {
                cancelAnimationFrame(animationFrameId);
            }
            chart?.destroy();
            chart = null;
        };
    });

    const latestSample = $derived(samples.at(-1));
    const latestVisibleCount = $derived(
        getVisibleSampleCount(latestSample, renderClockMs),
    );
    const deliveryMetrics = $derived(getObservedDeliveryMetrics(samples));
    const revealProgressPct = $derived(
        latestSample
            ? (latestVisibleCount / latestSample.samples_per_channel) * 100
            : 0,
    );
    const bufferedDurationSec = $derived(
        getBufferedDurationMs(samples) / 1000,
    );
</script>

<div class="emg-viewer">
    {#if latestSample}
        <div class="emg-summary">
            <div><span class="label">Device</span>{latestSample.device_id}</div>
            <div><span class="label">Seq</span>{latestSample.seq_no}</div>
            <div>
                <span class="label">Declared Rate</span>{latestSample.sample_rate_hz} Hz
            </div>
            <div>
                <span class="label">Frame</span>{latestSample.n_channels} ch x
                {latestSample.samples_per_channel}
            </div>
            <div>
                <span class="label">Ingress</span>{formatNumber(
                    deliveryMetrics.sampleRateHz,
                    0,
                )} samples/s
            </div>
            <div>
                <span class="label">Frame Cadence</span>{formatNumber(
                    deliveryMetrics.frameRateHz,
                    1,
                )} fps
            </div>
            <div>
                <span class="label">Reveal</span>{Math.round(revealProgressPct)}%
            </div>
            <div>
                <span class="label">Buffered</span>{formatNumber(
                    bufferedDurationSec,
                    1,
                )}s
            </div>
        </div>

        <div class="graph-section">
            <div class="graph-head">
                <h4>Rolling Trace</h4>
                <div class="window-controls" aria-label="History window">
                    {#each DISPLAY_WINDOWS as option}
                        <button
                            type="button"
                            class:selected={selectedWindowMs === option.ms}
                            onclick={() => {
                                selectedWindowMs = option.ms;
                            }}
                        >
                            {option.label}
                        </button>
                    {/each}
                </div>
            </div>

            <div class="chart-wrap">
                <canvas bind:this={chartCanvas}></canvas>
            </div>

            <div class="graph-foot">
                <span>
                    Revealing {latestVisibleCount}/{latestSample
                        .samples_per_channel} samples from the newest frame
                </span>
                <span>
                    Arrival {formatNumber(deliveryMetrics.batchIntervalMs, 0)} ms
                </span>
                <span>
                    Window {formatNumber(selectedWindowMs / 1000, 0)}s
                </span>
            </div>
        </div>

        <div class="channel-list">
            {#each latestSample.payload as values, channelIndex}
                {@const stats = getChannelStats(values)}
                <div class="channel-row">
                    <div class="channel-name">
                        {latestSample.channel_labels[channelIndex] ??
                            `ch${channelIndex + 1}`}
                    </div>
                    <div class="channel-stats">
                        <span>last {formatNumber(stats.last, 2)}</span>
                        <span>mean {formatNumber(stats.mean, 1)}</span>
                        <span>rms {formatNumber(stats.rms, 1)}</span>
                        <span>range {formatNumber(stats.min, 2)}..{formatNumber(
                            stats.max,
                            2,
                        )}</span>
                    </div>
                    <div class="recent-values">
                        {formatRecentValues(values)}
                    </div>
                </div>
            {/each}
        </div>

        <details class="raw-section">
            <summary>Raw Frame JSON</summary>
            <pre>{formatPayload(latestSample)}</pre>
        </details>
    {/if}
</div>

<style>
    .emg-viewer {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .emg-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.75rem;
        font-size: 0.9rem;
    }

    .label {
        display: block;
        margin-bottom: 0.2rem;
        color: #64748b;
        font-size: 0.75rem;
        text-transform: uppercase;
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

    .window-controls {
        display: inline-flex;
        border: 1px solid #dbe3ee;
        border-radius: 8px;
        overflow: hidden;
        background: #f8fafc;
    }

    .window-controls button {
        border: 0;
        background: transparent;
        padding: 0.45rem 0.7rem;
        font-size: 0.82rem;
        color: #475569;
        cursor: pointer;
    }

    .window-controls button.selected {
        background: #e2e8f0;
        color: #0f172a;
        font-weight: 600;
    }

    .chart-wrap {
        position: relative;
        min-height: 280px;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background:
            linear-gradient(
                to bottom,
                rgba(248, 250, 252, 0.96),
                rgba(255, 255, 255, 0.98)
            );
        padding: 0.75rem;
    }

    .graph-foot {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        flex-wrap: wrap;
        font-size: 0.8rem;
        color: #475569;
    }

    .channel-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .channel-row {
        display: grid;
        gap: 0.35rem;
        padding-top: 0.2rem;
    }

    .channel-name {
        font-weight: 600;
        color: #0f172a;
    }

    .channel-stats {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        font-family: monospace;
        font-size: 0.8rem;
        color: #475569;
    }

    .recent-values {
        font-family: monospace;
        font-size: 0.78rem;
        color: #334155;
        overflow-x: auto;
        white-space: nowrap;
    }

    .raw-section {
        border-top: 1px solid #e5e7eb;
        padding-top: 0.75rem;
    }

    .raw-section summary {
        cursor: pointer;
        font-weight: 500;
        color: #334155;
    }

    .raw-section pre {
        margin: 0.75rem 0 0 0;
        padding: 0.75rem;
        border-radius: 6px;
        background: #0f172a;
        color: #e2e8f0;
        font-size: 0.78rem;
        line-height: 1.45;
        overflow: auto;
    }

    @media (max-width: 720px) {
        .chart-wrap {
            min-height: 240px;
            padding: 0.5rem;
        }
    }
</style>
