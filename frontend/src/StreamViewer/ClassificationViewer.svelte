<script lang="ts">
    // Classification readout (Phase 2). Renders a classifier's output frame:
    // channel 0 is the predicted class index, the remaining channels are
    // per-class confidences labelled "confidence.<class>". Selected by the
    // viewer registry from the frame's channel-label shape — no schema-name
    // coupling. Shares the feed shape of the other channel-frame viewers.
    import type { BufferedEmgSample } from "./types";

    interface Props {
        samples: BufferedEmgSample[];
        formatNumber: (num: number, decimals?: number) => string;
    }

    let { samples, formatNumber }: Props = $props();

    const latest = $derived(samples.at(-1) ?? null);

    interface ClassRow {
        name: string;
        confidence: number;
        predicted: boolean;
    }

    const readout = $derived.by(() => {
        if (!latest) {
            return null;
        }
        const labels = latest.channel_labels ?? [];
        const value = (channel: number): number => latest.payload[channel]?.[0] ?? 0;
        const predictedIndex = Math.round(value(0));
        const rows: ClassRow[] = [];
        for (let channel = 1; channel < labels.length; channel += 1) {
            rows.push({
                name: labels[channel].replace(/^confidence\./, ""),
                confidence: value(channel),
                predicted: channel - 1 === predictedIndex,
            });
        }
        const predictedName =
            rows[predictedIndex]?.name ?? `class ${predictedIndex}`;
        return { predictedName, rows };
    });
</script>

{#if readout}
    <div class="classification-viewer">
        <div class="prediction">
            <span class="label">Predicted class</span>
            <strong>{readout.predictedName}</strong>
        </div>
        <div class="confidences">
            {#each readout.rows as row}
                <div class="conf-row" class:predicted={row.predicted}>
                    <span class="conf-name">{row.name}</span>
                    <div class="conf-bar-track">
                        <div
                            class="conf-bar-fill"
                            style={`width: ${Math.max(0, Math.min(1, row.confidence)) * 100}%`}
                        ></div>
                    </div>
                    <span class="conf-value">{formatNumber(row.confidence, 3)}</span>
                </div>
            {/each}
        </div>
    </div>
{:else}
    <p class="classification-empty">Waiting for a classification frame…</p>
{/if}

<style>
    .classification-viewer {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .prediction {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .prediction .label {
        color: #64748b;
        font-size: 0.75rem;
        text-transform: uppercase;
    }

    .prediction strong {
        font-size: 1.6rem;
        color: #0f766e;
    }

    .confidences {
        display: grid;
        gap: 0.5rem;
    }

    .conf-row {
        display: grid;
        grid-template-columns: minmax(90px, 1fr) 3fr auto;
        align-items: center;
        gap: 0.6rem;
        font-size: 0.85rem;
    }

    .conf-name {
        color: #475569;
        word-break: break-word;
    }

    .conf-row.predicted .conf-name {
        color: #0f766e;
        font-weight: 600;
    }

    .conf-bar-track {
        height: 10px;
        border-radius: 999px;
        background: rgba(100, 116, 139, 0.18);
        overflow: hidden;
    }

    .conf-bar-fill {
        height: 100%;
        border-radius: 999px;
        background: #94a3b8;
    }

    .conf-row.predicted .conf-bar-fill {
        background: #0f766e;
    }

    .conf-value {
        font-variant-numeric: tabular-nums;
        color: #475569;
    }

    .classification-empty {
        margin: 0;
        color: #64748b;
    }
</style>
