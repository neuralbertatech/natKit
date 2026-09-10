<script lang="ts">
    // One marble row on a node card (TEC-NATKIT-106).
    //
    // Rx's real gift to a visual dataflow language is the marble diagram — a
    // per-operator ground truth you can look at. Drawn from real frames rather
    // than an illustration, it makes four failure modes visible that are
    // invisible anywhere else today: a combine silently misaligning, a starved
    // input, a drop-oldest gap, and an output pattern that does not follow from
    // its inputs.
    //
    // All layout arithmetic lives in marbleStrip.ts so it is testable; this file
    // is presentation only.
    import { describeStrip, layoutStrip } from "./marbleStrip";
    import type { ChannelActivity } from "../StreamViewer/types";

    interface Props {
        activity: ChannelActivity | undefined;
        // The shared right-hand edge for EVERY strip on the card. Positioning
        // each row against its own newest event would right-align them all, so
        // a stalled input would look identical to a live one.
        axisEndUs: number;
        label: string;
        lane: "data" | "markers";
    }

    let { activity, axisEndUs, label, lane }: Props = $props();

    const layout = $derived(layoutStrip(activity, axisEndUs));
    const caption = $derived(describeStrip(activity));
</script>

<div class="marble-row" class:stale={layout.stale}>
    <span class="marble-label" class:marker-lane={lane === "markers"}>{label}</span>
    <div
        class="marble-track"
        title={`${label}: ${caption}${layout.stale ? " (nothing in the window)" : ""}`}
    >
        {#if layout.mode === "exact"}
            {#each layout.marbles as marble}
                <span
                    class="marble"
                    class:marker-lane={lane === "markers"}
                    style={`left: ${(marble.position * 100).toFixed(3)}%`}
                ></span>
            {/each}
        {:else if layout.mode === "density"}
            {#each layout.columns as column}
                <span
                    class="density"
                    class:marker-lane={lane === "markers"}
                    style={`left: ${(column.position * 100).toFixed(3)}%; width: ${(column.width * 100).toFixed(3)}%; opacity: ${(0.25 + column.intensity * 0.75).toFixed(3)}`}
                ></span>
            {/each}
        {:else}
            <span class="marble-quiet">quiet</span>
        {/if}
    </div>
    <span class="marble-count">{layout.total}</span>
</div>

<style>
    .marble-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.62rem;
        line-height: 1;
        color: #7f92c4;
    }

    /* A lane whose newest event predates the window is dimmed rather than
       hidden: "this has gone quiet" is information, and removing the row would
       make it indistinguishable from a lane that never existed. */
    .marble-row.stale {
        opacity: 0.45;
    }

    .marble-label {
        flex: 0 0 2.4rem;
        text-align: right;
        color: #6d7fae;
    }

    .marble-label.marker-lane {
        color: #c9a227;
    }

    .marble-track {
        position: relative;
        flex: 1 1 auto;
        height: 10px;
        background: rgba(7, 11, 23, 0.72);
        border: 1px solid rgba(114, 142, 255, 0.14);
        border-radius: 3px;
        overflow: hidden;
    }

    .marble {
        position: absolute;
        top: 1px;
        width: 2px;
        height: 6px;
        margin-left: -1px;
        border-radius: 1px;
        background: #6f9dff;
    }

    .marble.marker-lane {
        background: #e2c14d;
    }

    .density {
        position: absolute;
        top: 1px;
        height: 6px;
        min-width: 1px;
        background: #6f9dff;
    }

    .density.marker-lane {
        background: #e2c14d;
    }

    .marble-quiet {
        position: absolute;
        left: 0.25rem;
        top: 0;
        font-size: 0.58rem;
        color: #4d5b80;
    }

    .marble-count {
        flex: 0 0 auto;
        min-width: 1.8rem;
        color: #6d7fae;
        font-variant-numeric: tabular-nums;
    }
</style>
