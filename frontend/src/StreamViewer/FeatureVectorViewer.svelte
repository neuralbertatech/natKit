<script lang="ts">
    import { onMount } from "svelte";
    import type { BufferedEmgSample } from "./types";

    interface Props {
        samples: BufferedEmgSample[];
        formatNumber: (num: number, decimals?: number) => string;
    }

    let { samples, formatNumber }: Props = $props();

    // A feature-vector stream emits one scalar per feature per sliding window
    // (samples_per_channel === 1), not a continuous waveform. So instead of a
    // rolling trace we show (a) the latest window's values as per-feature bars
    // and (b) an activation heatmap of features over recent windows.
    const MAX_HISTORY = 240;
    const ROW_HEIGHT = 16;

    // Categorical colors per Hudgins-style feature family — reuses the waveform
    // viewer's palette so the two viewers read as one system.
    const FAMILY_COLORS: Record<string, string> = {
        mav: "#0f766e",
        rms: "#2563eb",
        rmsw: "#2563eb",
        wl: "#7c3aed",
        zc: "#ea580c",
        ssc: "#dc2626",
        ar: "#65a30d",
    };
    const DEFAULT_COLOR = "#475569";

    // Channel labels look like "in1.flexor_a.bp.notch.hp.rect.win.env.mav" —
    // the trailing token is the feature family (AR coefficients trail as
    // "ar.0".."ar.3"), and the first two tokens name the source channel.
    function parseFeatureLabel(raw: string) {
        const parts = raw.split(".");
        const last = parts.at(-1) ?? raw;
        const prev = parts.at(-2) ?? "";
        const isAr = prev === "ar";
        const family = isAr ? "ar" : last;
        const channel = parts.slice(0, 2).join(".") || raw;
        const feature = isAr ? `ar[${last}]` : family;
        return { family, channel, feature };
    }

    function normalize(value: number, min: number, max: number): number {
        if (!(max > min)) {
            return 0.5;
        }
        return Math.min(1, Math.max(0, (value - min) / (max - min)));
    }

    // Sequential ramp (pale slate -> indigo) for the heatmap intensity.
    function heatColor(t: number): string {
        const lo = [226, 232, 240];
        const hi = [67, 56, 202];
        const r = Math.round(lo[0] + (hi[0] - lo[0]) * t);
        const g = Math.round(lo[1] + (hi[1] - lo[1]) * t);
        const b = Math.round(lo[2] + (hi[2] - lo[2]) * t);
        return `rgb(${r}, ${g}, ${b})`;
    }

    let chartCanvas = $state<HTMLCanvasElement | null>(null);

    interface FeatureRow {
        index: number;
        label: string;
        channel: string;
        feature: string;
        family: string;
        color: string;
        value: number;
        min: number;
        max: number;
    }

    const featureRows = $derived.by<FeatureRow[]>(() => {
        const latest = samples.at(-1);
        if (!latest) {
            return [];
        }
        const rows: FeatureRow[] = [];
        for (let index = 0; index < latest.n_channels; index += 1) {
            let min = Number.POSITIVE_INFINITY;
            let max = Number.NEGATIVE_INFINITY;
            for (const sample of samples) {
                const value = sample.payload[index]?.[0] ?? 0;
                if (value < min) min = value;
                if (value > max) max = value;
            }
            if (!Number.isFinite(min) || !Number.isFinite(max)) {
                min = 0;
                max = 1;
            }
            const label = latest.channel_labels[index] ?? `f${index + 1}`;
            const parsed = parseFeatureLabel(label);
            rows.push({
                index,
                label,
                channel: parsed.channel,
                feature: parsed.feature,
                family: parsed.family,
                color: FAMILY_COLORS[parsed.family] ?? DEFAULT_COLOR,
                value: latest.payload[index]?.[0] ?? 0,
                min,
                max,
            });
        }
        return rows;
    });

    const latestSample = $derived(samples.at(-1));

    const windowRateHz = $derived.by(() => {
        if (samples.length < 2) {
            return 0;
        }
        const first = samples[0].received_at_ms;
        const last = samples[samples.length - 1].received_at_ms;
        const durationMs = Math.max(1, last - first);
        return ((samples.length - 1) * 1000) / durationMs;
    });

    const familyLegend = $derived.by(() => {
        const seen = new Map<string, string>();
        for (const row of featureRows) {
            if (!seen.has(row.family)) {
                seen.set(row.family, row.color);
            }
        }
        return [...seen.entries()].map(([family, color]) => ({ family, color }));
    });

    function drawHeatmap(): void {
        const canvas = chartCanvas;
        if (!canvas) {
            return;
        }
        const rows = featureRows;
        const cols = Math.min(MAX_HISTORY, samples.length);
        const cssWidth = canvas.clientWidth || 600;
        const cssHeight = rows.length * ROW_HEIGHT;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.floor(cssWidth * dpr));
        canvas.height = Math.max(1, Math.floor(cssHeight * dpr));
        canvas.style.height = `${cssHeight}px`;

        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return;
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssWidth, cssHeight);
        if (cols === 0 || rows.length === 0) {
            return;
        }

        const colWidth = cssWidth / cols;
        const startFrame = samples.length - cols;
        for (let r = 0; r < rows.length; r += 1) {
            const row = rows[r];
            for (let c = 0; c < cols; c += 1) {
                const value = samples[startFrame + c].payload[row.index]?.[0] ?? 0;
                ctx.fillStyle = heatColor(normalize(value, row.min, row.max));
                ctx.fillRect(
                    c * colWidth,
                    r * ROW_HEIGHT,
                    Math.ceil(colWidth),
                    ROW_HEIGHT - 1,
                );
            }
        }
    }

    $effect(() => {
        samples;
        drawHeatmap();
    });

    onMount(() => {
        const handleResize = () => drawHeatmap();
        window.addEventListener("resize", handleResize);
        drawHeatmap();
        return () => window.removeEventListener("resize", handleResize);
    });
</script>

<div class="feature-viewer">
    {#if latestSample}
        <div class="summary">
            <div><span class="label">Device</span>{latestSample.device_id}</div>
            <div><span class="label">Seq</span>{latestSample.seq_no}</div>
            <div>
                <span class="label">Features</span>{latestSample.n_channels}
            </div>
            <div>
                <span class="label">Window Rate</span>{formatNumber(
                    windowRateHz,
                    1,
                )} /s
            </div>
            <div>
                <span class="label">Buffered</span>{samples.length} windows
            </div>
        </div>

        <div class="section">
            <div class="section-head">
                <h4>Latest window</h4>
                <div class="legend">
                    {#each familyLegend as item}
                        <span class="legend-item">
                            <span
                                class="dot"
                                style={`background:${item.color}`}
                            ></span>
                            {item.family}
                        </span>
                    {/each}
                </div>
            </div>
            <p class="hint">
                Bars are scaled to each feature's own recent range — length shows
                relative activation, not comparable raw magnitude.
            </p>
            <div class="feature-list">
                {#each featureRows as row}
                    <div class="feature-row">
                        <div class="feature-name" title={row.label}>
                            <span
                                class="dot"
                                style={`background:${row.color}`}
                            ></span>
                            <span class="chan">{row.channel}</span>
                            <span class="feat">{row.feature}</span>
                        </div>
                        <div class="bar-track">
                            <div
                                class="bar-fill"
                                style={`width:${
                                    normalize(row.value, row.min, row.max) * 100
                                }%; background:${row.color}`}
                            ></div>
                        </div>
                        <div class="feature-value">
                            {formatNumber(row.value, 2)}
                        </div>
                    </div>
                {/each}
            </div>
        </div>

        <div class="section">
            <div class="section-head">
                <h4>Activation over time</h4>
                <div class="scale">
                    low
                    <span class="scale-ramp"></span>
                    high
                </div>
            </div>
            <p class="hint">
                Each row is one feature over the last {Math.min(
                    MAX_HISTORY,
                    samples.length,
                )} windows (newest at right), normalized per feature.
            </p>
            <div class="heatmap">
                <div class="heatmap-labels">
                    {#each featureRows as row}
                        <div
                            class="heatmap-label"
                            style={`height:${ROW_HEIGHT}px`}
                            title={row.label}
                        >
                            {row.channel}.{row.feature}
                        </div>
                    {/each}
                </div>
                <div class="heatmap-canvas-wrap">
                    <canvas bind:this={chartCanvas}></canvas>
                </div>
            </div>
        </div>
    {:else}
        <p class="muted">Waiting for feature data…</p>
    {/if}
</div>

<style>
    .feature-viewer {
        display: flex;
        flex-direction: column;
        gap: 1.1rem;
    }

    .summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
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

    .section {
        display: grid;
        gap: 0.5rem;
    }

    .section-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .section-head h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #0f172a;
    }

    .hint {
        margin: 0;
        font-size: 0.76rem;
        color: #64748b;
    }

    .legend {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        font-size: 0.76rem;
        color: #475569;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        flex-shrink: 0;
    }

    .feature-list {
        display: flex;
        flex-direction: column;
        gap: 0.28rem;
    }

    .feature-row {
        display: grid;
        grid-template-columns: minmax(150px, 220px) 1fr minmax(60px, auto);
        align-items: center;
        gap: 0.6rem;
    }

    .feature-name {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        min-width: 0;
        font-size: 0.8rem;
    }

    .feature-name .chan {
        color: #334155;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .feature-name .feat {
        color: #0f172a;
        font-weight: 600;
        flex-shrink: 0;
    }

    .bar-track {
        position: relative;
        height: 10px;
        border-radius: 999px;
        background: #eef2f7;
        overflow: hidden;
    }

    .bar-fill {
        position: absolute;
        inset: 0 auto 0 0;
        border-radius: 999px;
        transition: width 0.12s linear;
    }

    .feature-value {
        font-family: monospace;
        font-size: 0.78rem;
        color: #334155;
        text-align: right;
    }

    .scale {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.74rem;
        color: #64748b;
    }

    .scale-ramp {
        width: 74px;
        height: 10px;
        border-radius: 3px;
        background: linear-gradient(to right, #e2e8f0, #4338ca);
    }

    .heatmap {
        display: flex;
        gap: 0.5rem;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.5rem;
        background: #fbfcfe;
        overflow: hidden;
    }

    .heatmap-labels {
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        width: 150px;
    }

    .heatmap-label {
        display: flex;
        align-items: center;
        font-size: 0.68rem;
        color: #475569;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .heatmap-canvas-wrap {
        flex: 1;
        min-width: 0;
    }

    .heatmap-canvas-wrap canvas {
        width: 100%;
        display: block;
    }

    .muted {
        color: #64748b;
    }
</style>
