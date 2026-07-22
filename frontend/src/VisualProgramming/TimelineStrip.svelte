<script lang="ts">
    // Timeline & transport strip (Phase 4). A DVR/DAW-style surface for the
    // graph's time context: a horizontal axis spanning the source history →
    // live edge, with recorded experiments as regions, cues as ticks, a
    // playhead, a glowing LIVE edge, and transport controls. Presentational —
    // all state + wiring lives in the editor; this emits callbacks.
    import { Play, Pause, Radio, RotateCcw } from "@lucide/svelte";
    import type {
        TimeMode,
        PlaybackSpeed,
        TimelineTick,
        TimelineRegion,
    } from "./timeContext";

    interface Props {
        mode: TimeMode;
        speed: PlaybackSpeed;
        playing: boolean;
        // Playhead position as a 0..1 fraction of the visible window.
        playheadFraction: number;
        // True when the playhead sits at the live edge (DVR "you're live").
        atLiveEdge: boolean;
        ticks: TimelineTick[];
        regions: TimelineRegion[];
        // Labels for the window's left/right edges (formatted times).
        startLabel: string;
        endLabel: string;
        playheadLabel: string;
        recording: boolean;
        onScrub: (fraction: number) => void;
        onJumpToLive: () => void;
        onTogglePlay: () => void;
        onSpeedChange: (speed: PlaybackSpeed) => void;
        // Re-run the processing chain from the playhead time (Phase 5).
        onReprocess: () => void;
    }

    let {
        mode,
        speed,
        playing,
        playheadFraction,
        atLiveEdge,
        ticks,
        regions,
        startLabel,
        endLabel,
        playheadLabel,
        recording,
        onScrub,
        onJumpToLive,
        onTogglePlay,
        onSpeedChange,
        onReprocess,
    }: Props = $props();

    const SPEEDS: PlaybackSpeed[] = [0.5, 1, 2, 4, "max"];

    let axisEl: HTMLDivElement | null = $state(null);

    function scrubFromEvent(event: MouseEvent) {
        if (!axisEl) return;
        const rect = axisEl.getBoundingClientRect();
        if (rect.width <= 0) return;
        const fraction = (event.clientX - rect.left) / rect.width;
        onScrub(Math.max(0, Math.min(1, fraction)));
    }

    let scrubbing = $state(false);
    function onAxisMouseDown(event: MouseEvent) {
        scrubbing = true;
        scrubFromEvent(event);
    }
    function onWindowMouseMove(event: MouseEvent) {
        if (scrubbing) scrubFromEvent(event);
    }
    function onWindowMouseUp() {
        scrubbing = false;
    }
</script>

<svelte:window onmousemove={onWindowMouseMove} onmouseup={onWindowMouseUp} />

<div class="timeline-strip">
    <div class="transport">
        <button
            type="button"
            class="t-btn"
            title={playing ? "Pause" : "Play"}
            onclick={onTogglePlay}
        >
            {#if playing}<Pause size={15} />{:else}<Play size={15} />{/if}
        </button>
        <button
            type="button"
            class="t-btn live-btn"
            class:live-active={atLiveEdge && mode === "live"}
            title="Jump to live"
            onclick={onJumpToLive}
        >
            <Radio size={14} />
            LIVE
        </button>
        <select
            class="speed"
            value={String(speed)}
            onchange={(e) => {
                const v = (e.currentTarget as HTMLSelectElement).value;
                onSpeedChange(v === "max" ? "max" : (Number(v) as PlaybackSpeed));
            }}
            title="Playback speed"
        >
            {#each SPEEDS as s}
                <option value={String(s)}>{s === "max" ? "max" : `${s}×`}</option>
            {/each}
        </select>
        {#if mode === "replay"}
            <button
                type="button"
                class="t-btn"
                title="Re-run the processing chain from the playhead"
                onclick={onReprocess}
            >
                <RotateCcw size={14} />
                Reprocess
            </button>
        {/if}
        <span class="mode-badge" class:replay={mode === "replay"}>
            {mode === "live" ? "LIVE" : "REPLAY"}
        </span>
        {#if recording}
            <span class="rec-badge"><span class="rec-dot"></span>REC</span>
        {/if}
        <span class="playhead-label">{playheadLabel}</span>
    </div>

    <div class="axis-row">
        <span class="edge-label">{startLabel}</span>
        <div
            class="axis"
            bind:this={axisEl}
            role="slider"
            tabindex="0"
            aria-label="Timeline scrubber"
            aria-valuenow={Math.round(playheadFraction * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            onmousedown={onAxisMouseDown}
        >
            {#each regions as region}
                <div
                    class="region"
                    class:recording={region.recording}
                    style={`left:${region.startFraction * 100}%;width:${region.widthFraction * 100}%`}
                    title={region.label}
                ></div>
            {/each}
            {#each ticks as tick}
                <div
                    class="tick"
                    class:session={tick.session}
                    style={`left:${tick.fraction * 100}%`}
                    title={`${tick.label} · ${tick.event}`}
                ></div>
            {/each}
            <!-- glowing live edge -->
            <div class="live-edge" class:hot={mode === "live"}></div>
            <!-- playhead -->
            <div
                class="playhead"
                style={`left:${playheadFraction * 100}%`}
            ></div>
        </div>
        <span class="edge-label right">{endLabel}</span>
    </div>
</div>

<style>
    .timeline-strip {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 10px 14px;
        background: #0f1720;
        border-top: 1px solid #1e2a36;
        color: #cbd5e1;
        font-size: 12px;
    }

    .transport {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .t-btn {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #1e293b;
        color: #cbd5e1;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 8px;
        cursor: pointer;
    }

    .t-btn:hover {
        background: #273449;
    }

    .live-btn {
        font-weight: 600;
        letter-spacing: 0.04em;
    }

    .live-btn.live-active {
        color: #34d399;
        border-color: #34d399;
    }

    .speed {
        background: #1e293b;
        color: #cbd5e1;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 3px 6px;
    }

    .mode-badge {
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(52, 211, 153, 0.15);
        color: #34d399;
        font-weight: 600;
        letter-spacing: 0.06em;
    }

    .mode-badge.replay {
        background: rgba(96, 165, 250, 0.15);
        color: #60a5fa;
    }

    .rec-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #f87171;
        font-weight: 600;
    }

    .rec-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #f87171;
        animation: rec-pulse 1s infinite;
    }

    @keyframes rec-pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.3;
        }
    }

    .playhead-label {
        margin-left: auto;
        font-variant-numeric: tabular-nums;
        color: #94a3b8;
    }

    .axis-row {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .edge-label {
        color: #64748b;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
        min-width: 54px;
    }

    .edge-label.right {
        text-align: right;
    }

    .axis {
        position: relative;
        flex: 1;
        height: 40px;
        background: #16212e;
        border: 1px solid #24313f;
        border-radius: 6px;
        overflow: hidden;
        cursor: pointer;
    }

    .region {
        position: absolute;
        top: 0;
        bottom: 0;
        background: rgba(96, 165, 250, 0.18);
        border-left: 1px solid rgba(96, 165, 250, 0.6);
        border-right: 1px solid rgba(96, 165, 250, 0.6);
    }

    .region.recording {
        background: rgba(248, 113, 113, 0.18);
        border-color: rgba(248, 113, 113, 0.6);
    }

    .tick {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #64748b;
        transform: translateX(-1px);
    }

    .tick.session {
        background: #34d399;
        width: 3px;
    }

    .live-edge {
        position: absolute;
        top: 0;
        bottom: 0;
        right: 0;
        width: 3px;
        background: #334155;
    }

    .live-edge.hot {
        background: #34d399;
        box-shadow: 0 0 8px 2px rgba(52, 211, 153, 0.6);
    }

    .playhead {
        position: absolute;
        top: -2px;
        bottom: -2px;
        width: 2px;
        background: #f8fafc;
        transform: translateX(-1px);
        pointer-events: none;
    }

    .playhead::before {
        content: "";
        position: absolute;
        top: 0;
        left: -4px;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #f8fafc;
    }
</style>
