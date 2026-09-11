<script lang="ts">
    // The tracks grammar (TEC-NATKIT-122): marbles ride tracks that physically
    // converge for a merge and split for a fork, so the card says what the
    // operator DOES rather than implying it by layout.
    //
    // All geometry lives in marbleStrip.ts and arrives here already placed —
    // this file draws and nothing else, the same split the rows grammar uses.
    import type { TrackDiagram } from "./marbleStrip";

    interface Props {
        diagram: TrackDiagram;
    }

    let { diagram }: Props = $props();
</script>

<svg
    class="marble-tracks"
    viewBox={`0 0 ${diagram.width} ${diagram.height}`}
    preserveAspectRatio="xMidYMid meet"
    role="img"
    aria-label={`${diagram.glyph}: ${diagram.lanes
        .filter((lane) => lane.label)
        .map((lane) => `${lane.label} ${lane.caption}`)
        .join(", ")}`}
>
    <!-- The rails first, so marbles sit on top of them. -->
    {#each diagram.lanes as lane}
        <line
            class="rail"
            class:silent={lane.silent}
            class:passthrough={lane.role === "passthrough"}
            x1={lane.x1}
            y1={lane.y}
            x2={lane.x2}
            y2={lane.y}
        />
    {/each}
    {#each diagram.joins as join}
        <line
            class="rail join"
            class:silent={join.silent}
            x1={join.x1}
            y1={join.y1}
            x2={join.x2}
            y2={join.y2}
        />
    {/each}

    {#each diagram.lanes as lane}
        {#each lane.columns as column}
            <rect
                class="track-density"
                class:marker-lane={lane.lane === "markers"}
                class:passthrough={lane.role === "passthrough"}
                x={column.x}
                y={lane.y - 3}
                width={Math.max(column.width, 0.8)}
                height={6}
                opacity={(lane.role === "passthrough" ? 0.12 : 0.28) +
                    column.intensity * (lane.role === "passthrough" ? 0.18 : 0.72)}
            />
        {/each}
        {#each lane.marbles as marble}
            <circle
                class="track-marble"
                class:marker-lane={lane.lane === "markers"}
                cx={marble.x}
                cy={marble.y}
                r="2.4"
            />
        {/each}
    {/each}

    <!-- The junction, and the operation it performs. -->
    <circle class="hub" cx={diagram.hub.x} cy={diagram.hub.y} r="2.6" />
    <text class="glyph" x={diagram.glyphX} y={diagram.glyphY}>{diagram.glyph}</text>

    {#each diagram.lanes as lane}
        {#if lane.label}
            <text class="lane-label" x={lane.x1 - 4} y={lane.y + 2.8}>{lane.label}</text>
        {/if}
        {#if lane.caption}
            <text
                class="lane-caption"
                class:warn={lane.silent && lane.role === "input"}
                x={diagram.width}
                y={lane.y + 2.8}>{lane.caption}</text
            >
        {/if}
    {/each}
</svg>

<style>
    .marble-tracks {
        display: block;
        width: 100%;
        /* ⚠️ height:auto, NOT a fixed px. The viewBox's own aspect ratio then
           sets the height, so the whole diagram scales uniformly to the card
           width and text stays proportional.
           Two earlier cuts got this wrong in opposite directions:
           preserveAspectRatio="none" with a normalised box distorted every
           label, and a hand-computed pixel height letterboxed the diagram into
           a third of the space because "meet" scales to the SMALLER dimension. */
        height: auto;
        overflow: visible;
    }

    .rail {
        stroke: rgba(114, 142, 255, 0.28);
        stroke-width: 1;
        vector-effect: non-scaling-stroke;
    }

    .rail.join {
        stroke: rgba(114, 142, 255, 0.34);
    }

    /* ⚠️ A SILENT RAIL IS THE READING. Dashed rather than merely dim, because a
       dim line beside a solid one still reads as "quiet, probably fine" — and a
       starved input is not fine. */
    .rail.silent {
        stroke: rgba(224, 139, 106, 0.55);
        stroke-dasharray: 3 3;
        vector-effect: non-scaling-stroke;
    }

    .rail.passthrough {
        stroke: rgba(114, 142, 255, 0.14);
    }

    .track-density {
        fill: #6f9dff;
    }

    .track-density.marker-lane {
        fill: #e2c14d;
    }

    .track-marble {
        fill: #6f9dff;
    }

    .track-marble.marker-lane {
        fill: #e2c14d;
    }

    .hub {
        fill: rgba(10, 15, 30, 0.95);
        stroke: rgba(114, 142, 255, 0.5);
        stroke-width: 1;
        vector-effect: non-scaling-stroke;
    }

    .glyph {
        fill: #8fa4d8;
        font-size: 9px;
        text-anchor: middle;
        letter-spacing: 0.03em;
    }

    .lane-label {
        fill: #6d7fae;
        font-size: 9px;
        text-anchor: end;
    }

    .lane-caption {
        fill: #6d7fae;
        font-size: 9px;
        text-anchor: end;
        font-variant-numeric: tabular-nums;
    }

    .lane-caption.warn {
        fill: #e08b6a;
        font-weight: 600;
    }
</style>
