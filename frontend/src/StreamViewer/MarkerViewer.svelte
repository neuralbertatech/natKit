<script lang="ts">
    // Marker renderer (Phase 2 — markers as a first-class stream). Subscribes to
    // a MarkerEventV1 stream and renders its cue/session events as (a) a compact
    // time axis with session regions + cue ticks and (b) a scrolling event list.
    // Selected by the viewer registry when a stream's schema is MarkerEventV1.
    import type { BufferedMarkerEvent } from "./types";

    interface Props {
        markers: BufferedMarkerEvent[];
        // Cap how many rows the event list shows (newest first).
        maxRows?: number;
    }

    let { markers, maxRows = 40 }: Props = $props();

    // A session lifecycle marker delimits a run; everything else is a cue.
    function isSessionMarker(m: BufferedMarkerEvent): boolean {
        return m.marker_type === "session";
    }

    const timeRange = $derived.by(() => {
        if (markers.length === 0) {
            return null;
        }
        let min = Infinity;
        let max = -Infinity;
        for (const m of markers) {
            if (m.emitted_at_us < min) min = m.emitted_at_us;
            if (m.emitted_at_us > max) max = m.emitted_at_us;
        }
        // Avoid a zero-width axis for a single marker.
        if (max <= min) {
            max = min + 1;
        }
        return { min, max, span: max - min };
    });

    interface Tick {
        left: number; // 0..100 (%)
        label: string;
        session: boolean;
        event: string;
    }

    const ticks = $derived.by<Tick[]>(() => {
        const range = timeRange;
        if (!range) {
            return [];
        }
        return markers.map((m) => ({
            left: ((m.emitted_at_us - range.min) / range.span) * 100,
            label: m.label,
            session: isSessionMarker(m),
            event: m.event,
        }));
    });

    // Session regions: pair start/end session markers by session_id in order.
    interface Region {
        left: number;
        width: number;
        label: string;
    }

    const regions = $derived.by<Region[]>(() => {
        const range = timeRange;
        if (!range) {
            return [];
        }
        const out: Region[] = [];
        const openBySession = new Map<string, number>();
        for (const m of markers) {
            if (!isSessionMarker(m)) {
                continue;
            }
            if (m.event === "start") {
                openBySession.set(m.session_id, m.emitted_at_us);
            } else if (m.event === "end") {
                const startUs = openBySession.get(m.session_id);
                if (startUs !== undefined) {
                    const left = ((startUs - range.min) / range.span) * 100;
                    const width =
                        ((m.emitted_at_us - startUs) / range.span) * 100;
                    out.push({ left, width, label: m.session_id });
                    openBySession.delete(m.session_id);
                }
            }
        }
        // A still-open session (recording live): draw to the live edge.
        for (const [sessionId, startUs] of openBySession) {
            const left = ((startUs - range.min) / range.span) * 100;
            out.push({
                left,
                width: Math.max(0, 100 - left),
                label: `${sessionId} (recording)`,
            });
        }
        return out;
    });

    const recentRows = $derived(
        [...markers].reverse().slice(0, maxRows),
    );

    function formatRelMs(m: BufferedMarkerEvent): string {
        const range = timeRange;
        if (!range) return "0.0s";
        return `${((m.emitted_at_us - range.min) / 1000 / 1000).toFixed(1)}s`;
    }
</script>

{#if markers.length === 0}
    <p class="marker-empty">Waiting for markers… (record an experiment)</p>
{:else}
    <div class="marker-viewer">
        <div class="marker-axis">
            {#each regions as region}
                <div
                    class="marker-region"
                    style={`left:${region.left}%;width:${region.width}%`}
                    title={region.label}
                ></div>
            {/each}
            {#each ticks as tick}
                <div
                    class="marker-tick"
                    class:session={tick.session}
                    style={`left:${tick.left}%`}
                    title={`${tick.label} · ${tick.event}`}
                ></div>
            {/each}
        </div>
        <div class="marker-count">
            {markers.length} marker{markers.length === 1 ? "" : "s"}
        </div>
        <div class="marker-list">
            {#each recentRows as m}
                <div class="marker-row" class:session={isSessionMarker(m)}>
                    <span class="m-time">{formatRelMs(m)}</span>
                    <span class="m-type">{m.marker_type}</span>
                    <span class="m-event">{m.event}</span>
                    <span class="m-label">{m.label}</span>
                </div>
            {/each}
        </div>
    </div>
{/if}

<style>
    .marker-viewer {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .marker-axis {
        position: relative;
        height: 34px;
        border-radius: 6px;
        background: rgba(100, 116, 139, 0.12);
        overflow: hidden;
    }

    .marker-region {
        position: absolute;
        top: 0;
        bottom: 0;
        background: rgba(15, 118, 110, 0.16);
        border-left: 1px solid rgba(15, 118, 110, 0.5);
        border-right: 1px solid rgba(15, 118, 110, 0.5);
    }

    .marker-tick {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #64748b;
        transform: translateX(-1px);
    }

    .marker-tick.session {
        background: #0f766e;
        width: 3px;
    }

    .marker-count {
        color: #64748b;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .marker-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        max-height: 220px;
        overflow-y: auto;
        font-size: 0.8rem;
    }

    .marker-row {
        display: grid;
        grid-template-columns: 3.5rem 4.5rem 3.5rem 1fr;
        gap: 0.5rem;
        padding: 2px 4px;
        border-radius: 4px;
    }

    .marker-row.session {
        background: rgba(15, 118, 110, 0.1);
    }

    .m-time {
        font-variant-numeric: tabular-nums;
        color: #475569;
    }

    .m-type {
        color: #64748b;
    }

    .m-event {
        color: #94a3b8;
    }

    .m-label {
        color: #0f172a;
        font-weight: 600;
        word-break: break-word;
    }

    .marker-empty {
        margin: 0;
        color: #64748b;
    }
</style>
