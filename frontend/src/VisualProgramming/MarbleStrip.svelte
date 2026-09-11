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
    import type { StripRow } from "./marbleStrip";
    import type { ChannelActivity } from "../StreamViewer/types";

    interface Props {
        // A row prepared by buildOperatorStrip (TEC-NATKIT-120): carries its own
        // layout, caption and silence flag, because an operator-shaped strip
        // decides those across the whole node rather than per lane. When absent
        // this falls back to the original one-lane behaviour, so kinds that have
        // not been converted yet draw exactly as before.
        row?: StripRow;
        activity?: ChannelActivity | undefined;
        // The shared right-hand edge for EVERY strip on the card. Positioning
        // each row against its own newest event would right-align them all, so
        // a stalled input would look identical to a live one.
        axisEndUs: number;
        label: string;
        lane: "data" | "markers";
    }

    let { row, activity, axisEndUs, label, lane }: Props = $props();

    const layout = $derived(row ? row.layout : layoutStrip(activity, axisEndUs));
    const caption = $derived(row ? row.caption : describeStrip(activity));
    const rowLabel = $derived(row ? row.label : label);
    // ⚠️ An operator row is silent when its lane said nothing for the WHOLE
    // window, which is a stronger claim than layout.stale alone: a lane with no
    // events at all is stale-by-default and would otherwise read the same as one
    // that genuinely stopped.
    const silent = $derived(row ? row.silent : layout.stale);
</script>

<div
    class="marble-row"
    class:stale={silent}
    class:is-input={row?.role === "input"}
    class:is-rejected={row?.role === "rejected"}
>
    <span class="marble-label" class:marker-lane={lane === "markers"}>{rowLabel}</span>
    <div
        class="marble-track"
        title={`${rowLabel}: ${caption}${silent ? " (nothing in the window)" : ""}`}
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
            <span class="marble-quiet">{silent ? "silent" : "quiet"}</span>
        {/if}
    </div>
    <span class="marble-count" class:warn={silent && row?.role === "input"}
        >{row ? caption : layout.total}</span
    >
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

    /* An input row is indented and dimmer than the output row below it, so the
       stack reads as "these went in, this came out" at a glance rather than as
       a list of equal lanes. */
    .marble-row.is-input .marble-label {
        color: #5d6e9c;
    }

    .marble-row.is-input .marble-track {
        margin-left: 0.3rem;
    }

    /* What the operator threw away, under what it kept. Dimmed because it is
       context for the output row rather than a fault: a filter that drops most
       of its input is doing its job, and the dropped row is how you see the
       ratio at all. */
    .marble-row.is-rejected {
        opacity: 0.6;
    }

    .marble-row.is-rejected .marble-label,
    .marble-row.is-rejected .marble-count {
        color: #7f8faf;
    }

    /* ⚠️ A SILENT INPUT IS THE ONE THING THIS STRIP EXISTS TO SHOW. It is called
       out in warning colour rather than merely dimmed, because a dimmed row
       beside a busy one still reads as "quiet, probably fine" — and a starved
       input is not fine. */
    .marble-count.warn {
        color: #e08b6a;
        font-weight: 600;
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
        /* Wide enough for a caption ("400/s", "silent 7s") rather than the bare
           integer this used to carry. */
        min-width: 2.9rem;
        text-align: right;
        color: #6d7fae;
        font-variant-numeric: tabular-nums;
    }
</style>
