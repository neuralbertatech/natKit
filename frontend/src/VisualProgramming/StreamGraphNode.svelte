<script lang="ts">
    import MarbleStrip from "./MarbleStrip.svelte";
    import {
        Archive,
        CircleDot,
        ClipboardList,
        Cpu,
        FileDown,
        GitBranch,
        LineChart,
        Maximize2,
        Monitor,
        Package,
        SlidersHorizontal,
    } from "@lucide/svelte";
    import {
        getNodeHeight,
        graphRunStateClass,
        isProvenancePort,
        BOTH_LABEL,
    } from "./streamGraph";
    import type { StreamGraphNodeStatus } from "../StreamViewer/types";
    import type { EditorGraphNode } from "./composites";
    import { onMount, type Snippet } from "svelte";

    /**
     * What a port carries: data, markers, or BOTH.
     *
     * ⚠️ Three states, not two. A combine's single output is a bundle — data and
     * markers travelling together — and calling that either "data" or "markers"
     * loses half of it. An earlier pass gave combine two separate output ports
     * instead; this says the same thing without splitting a channel that is not
     * actually split.
     *
     * The LABEL wins over the port id when there is one: port ids are fixed at
     * creation (`data`, `in1`), while the label is computed from what the
     * channel actually resolved to.
     */
    function portTone(
        portId: string,
        side: "input" | "output",
    ): "data" | "markers" | "both" {
        const label =
            side === "input"
                ? inputPortLabels?.[portId]
                : outputPortLabels?.[portId];
        if (label) {
            if (label === BOTH_LABEL) return "both";
            if (label === "markers") return "markers";
            return "data";
        }
        return portId === "markers" ? "markers" : "data";
    }

    export interface PortAnchor {
        portId: string;
        side: "input" | "output";
        dx: number;
        dy: number;
    }

    interface Props {
        node: EditorGraphNode;
        runtimeStatus: StreamGraphNodeStatus | null;
        // The shared right-hand edge for this card's marble strips, resolved
        // across the WHOLE graph by the editor (TEC-NATKIT-106). Per-card axes
        // would right-align every row and make a stalled input look healthy.
        marbleAxisEndUs?: number;
        selected: boolean;
        invalid: boolean;
        pendingConnection: { nodeId: string; portId: string } | null;
        // Renders a viewer node's live chart on the card when inline_graph is on.
        inlineViewerChart?: Snippet<[EditorGraphNode]>;
        // Renders the bound experiment's run panel on a markers node's card when
        // inline_experiment is on.
        inlineExperiment?: Snippet<[EditorGraphNode]>;
        // Label of the experiment bound to this board, for a markers node's meta
        // line (the node itself carries no experiment config).
        boundExperimentLabel?: string | null;
        // Friendly device names per stream id (from the metadata/device_id); a
        // source node prefers this over its raw stream id.
        streamDeviceNames?: Record<string, string>;
        // Topic-aware channels (Part B): per-input-port label override, keyed by
        // port id — e.g. a combine input relabels itself data/markers/stream from
        // the channel it is fed. Falls back to the raw port id when absent.
        inputPortLabels?: Record<string, string>;
        // Same, for OUTPUT ports. A combine whose inputs carry both types
        // relabels its single output "data and markers" rather than growing a
        // second port — the channel is one channel; it just has two things in it.
        outputPortLabels?: Record<string, string>;
        // What this viewer/sink is actually reading, or why it is reading
        // nothing — resolved upstream, since a viewer shows a source-bound
        // stream without the graph running.
        sourceLabel?: string | null;
        // Part D: a viewer's phantom markers input — shown only when the incoming
        // channel carries markers. "available" = overlay off, "on" = enabled.
        markersPhantom?: "on" | "available";
        // Toggles the marker overlay (the phantom markers input click).
        onToggleMarkers?: (nodeId: string) => void;
        // Reports each port dot's offset from the node's top-left (unscaled graph
        // px) so edges can anchor to the real dots regardless of node size.
        onPortLayout?: (nodeId: string, anchors: PortAnchor[]) => void;
        // Reports a live resize from the corner handle.
        onResize?: (nodeId: string, width: number, height: number) => void;
        // Toggles a viewer node's inline live graph from the node card itself.
        onToggleInlineGraph?: (nodeId: string, enabled: boolean) => void;
        // Toggles a markers node's inline run panel from the node card.
        onToggleInlineExperiment?: (nodeId: string, enabled: boolean) => void;
        onSelect: (nodeId: string, event?: MouseEvent) => void;
        onStartDrag: (event: MouseEvent, nodeId: string) => void;
        onPortClick: (
            nodeId: string,
            portId: string,
            side: "input" | "output",
        ) => void;
        onPortMouseDown?: (
            event: MouseEvent,
            nodeId: string,
            portId: string,
            side: "input" | "output",
        ) => void;
        onExpand?: (nodeId: string) => void;
        // Phase 7: a param node's inline slider reports value changes here.
        onParamValueChange?: (nodeId: string, value: number) => void;
    }

    let {
        node,
        runtimeStatus,
        marbleAxisEndUs = 0,
        selected,
        invalid,
        pendingConnection,
        inlineViewerChart,
        inlineExperiment,
        boundExperimentLabel,
        streamDeviceNames,
        inputPortLabels,
        outputPortLabels,
        sourceLabel,
        markersPhantom,
        onToggleMarkers,
        onPortLayout,
        onResize,
        onToggleInlineGraph,
        onToggleInlineExperiment,
        onSelect,
        onStartDrag,
        onPortClick,
        onPortMouseDown,
        onExpand,
        onParamValueChange,
    }: Props = $props();

    const showInlineGraph = $derived(
        node.kind === "viewer" && node.inline_graph === true,
    );
    // The run panel lives on the markers node now that the experiment is a
    // board-level object; a legacy `experiment` node keeps it so an unconverted
    // board still records.
    const isMarkerSource = $derived(
        node.kind === "markers" || node.kind === "experiment",
    );
    const showInlineExperiment = $derived(
        (node.kind === "markers" || node.kind === "experiment") &&
            node.inline_experiment === true,
    );

    function handleNodeMouseDown(event: MouseEvent) {
        if ((event.target as HTMLElement).closest(".port-button")) {
            return;
        }
        onStartDrag(event, node.id);
    }

    // A manually-resized node overrides the computed height/width; otherwise
    // fall back to the content-driven defaults.
    // How many strip rows this card will draw, from what the backend actually
    // reported. Derived here rather than in getNodeHeight because the lanes are
    // a RUNTIME fact and that function only sees the node definition.
    const marbleRows = $derived(
        (runtimeStatus?.data_activity ? 1 : 0) +
            (runtimeStatus?.marker_activity ? 1 : 0),
    );
    const nodeHeight = $derived(node.height ?? getNodeHeight(node, marbleRows));
    const runtimeStreamId = $derived(
        runtimeStatus?.output_stream_id
            ? String(runtimeStatus.output_stream_id)
            : null,
    );

    // A source node prefers the metadata device name (e.g. "emg01") over its raw
    // "Stream <id>" label, falling back to the stream id when no frame has named
    // it yet.
    const displayLabel = $derived(
        node.kind === "stream_source" && node.stream_id
            ? (streamDeviceNames?.[node.stream_id] ?? node.label)
            : node.label,
    );

    let nodeEl = $state<HTMLElement | undefined>(undefined);

    // Measure each port dot's center offset from the node's top-left in UNSCALED
    // graph pixels (getBoundingClientRect is scaled by the canvas zoom, so divide
    // it out via the node's boundingWidth/offsetWidth ratio). Offsets are
    // invariant under pan/zoom/drag and only change on resize/content change, so
    // edges anchored to node.position + offset stay glued to the real dots.
    function measurePorts() {
        if (!nodeEl || !onPortLayout) return;
        const nodeRect = nodeEl.getBoundingClientRect();
        const scale = nodeEl.offsetWidth ? nodeRect.width / nodeEl.offsetWidth : 1;
        if (!scale) return;
        const anchors: PortAnchor[] = [];
        for (const dot of nodeEl.querySelectorAll<HTMLElement>("[data-port-anchor]")) {
            const r = dot.getBoundingClientRect();
            anchors.push({
                portId: dot.dataset.portId ?? "",
                side: (dot.dataset.portSide as "input" | "output") ?? "input",
                dx: (r.left + r.width / 2 - nodeRect.left) / scale,
                dy: (r.top + r.height / 2 - nodeRect.top) / scale,
            });
        }
        onPortLayout(node.id, anchors);
    }

    onMount(() => {
        measurePorts();
        // Re-measure whenever the card's size changes (resize handle, inline
        // graph toggle, port add/remove, font load).
        const observer = new ResizeObserver(() => measurePorts());
        if (nodeEl) observer.observe(nodeEl);
        return () => observer.disconnect();
    });

    // --- Corner resize handle -------------------------------------------------
    let resizeState: {
        startX: number;
        startY: number;
        startW: number;
        startH: number;
        scale: number;
    } | null = null;

    function startResize(event: MouseEvent) {
        event.stopPropagation();
        event.preventDefault();
        const rect = nodeEl?.getBoundingClientRect();
        const scale =
            nodeEl && nodeEl.offsetWidth && rect
                ? rect.width / nodeEl.offsetWidth
                : 1;
        resizeState = {
            startX: event.clientX,
            startY: event.clientY,
            startW: nodeEl?.offsetWidth ?? 220,
            startH: nodeEl?.offsetHeight ?? nodeHeight,
            scale: scale || 1,
        };
        window.addEventListener("mousemove", onResizeMove);
        window.addEventListener("mouseup", endResize);
    }

    function onResizeMove(event: MouseEvent) {
        if (!resizeState) return;
        const { scale } = resizeState;
        const width = Math.max(
            160,
            resizeState.startW + (event.clientX - resizeState.startX) / scale,
        );
        const height = Math.max(
            80,
            resizeState.startH + (event.clientY - resizeState.startY) / scale,
        );
        onResize?.(node.id, Math.round(width), Math.round(height));
    }

    function endResize() {
        resizeState = null;
        window.removeEventListener("mousemove", onResizeMove);
        window.removeEventListener("mouseup", endResize);
    }
</script>

<div
    bind:this={nodeEl}
    class:selected
    class:node-invalid={invalid}
    class:inline-viewer={showInlineGraph}
    class:resized={node.width != null || node.height != null}
    class="node"
    role="button"
    tabindex="0"
    style={`left:${node.position.x}px; top:${node.position.y}px; height:${nodeHeight}px;${
        node.width != null ? ` width:${node.width}px;` : ""
    }`}
    onmousedown={(event) => {
        event.stopPropagation();
        handleNodeMouseDown(event);
    }}
    onclick={(event) => event.stopPropagation()}
    ondblclick={(event) => {
        event.stopPropagation();
        if (
            node.kind === "composite" ||
            node.kind === "viewer" ||
            isMarkerSource
        ) {
            onExpand?.(node.id);
        }
    }}
    onkeydown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            onSelect(node.id);
        }
    }}
>
    <button type="button" class="node-header">
        <div class="node-title">
            {#if node.kind === "stream_source"}
                <CircleDot size={14} />
            {:else if node.kind === "viewer"}
                <Monitor size={14} />
            {:else if node.kind === "sink"}
                <Archive size={14} />
            {:else if node.kind === "composite"}
                <Package size={14} />
            {:else if isMarkerSource}
                <ClipboardList size={14} />
            {:else if node.kind === "train"}
                <Cpu size={14} />
            {:else if node.kind === "export"}
                <FileDown size={14} />
            {:else if node.kind === "param"}
                <SlidersHorizontal size={14} />
            {:else}
                <GitBranch size={14} />
            {/if}
            <span class="node-label" title={displayLabel}>{displayLabel}</span>
        </div>
        <div class="node-header-meta">
            {#if runtimeStatus}
                <span
                    class={`node-runtime-badge ${graphRunStateClass(runtimeStatus.state)}`}
                >
                    {runtimeStatus.state}
                </span>
            {/if}
            <span class="node-kind"
                >{node.kind === "stream_source" ? "source" : node.kind}</span
            >
        </div>
    </button>

    <div class="node-body">
        <div class="node-column">
            {#each node.input_port_ids ?? [] as portId}
                <button
                    type="button"
                    class:port-armed={pendingConnection !== null}
                    class:port-provenance={isProvenancePort(portId)}
                    class="port-button input"
                    data-node-id={node.id}
                    data-port-id={portId}
                    title={isProvenancePort(portId)
                        ? "Lineage input (provenance edge)"
                        : undefined}
                    onmousedown={(event) => {
                        event.stopPropagation();
                        onPortMouseDown?.(event, node.id, portId, "input");
                    }}
                    onclick={(event) => {
                        event.stopPropagation();
                        onPortClick(node.id, portId, "input");
                    }}
                >
                    <span
                        class="port-dot"
                        class:port-dot-provenance={isProvenancePort(portId)}
                        class:port-dot-marker={portTone(portId, "input") ===
                            "markers"}
                        class:port-dot-both={portTone(portId, "input") === "both"}
                        data-port-anchor
                        data-port-id={portId}
                        data-port-side="input"
                    ></span>
                    <span>{inputPortLabels?.[portId] ?? portId}</span>
                </button>
            {/each}
            {#if markersPhantom}
                <button
                    type="button"
                    class="port-button input port-phantom"
                    class:port-phantom-on={markersPhantom === "on"}
                    title={markersPhantom === "on"
                        ? "Markers overlay on — click to hide"
                        : "This link carries markers — click to overlay them"}
                    onmousedown={(event) => event.stopPropagation()}
                    onclick={(event) => {
                        event.stopPropagation();
                        onToggleMarkers?.(node.id);
                    }}
                >
                    <span class="port-dot port-dot-marker"></span>
                    <span>markers</span>
                </button>
            {/if}
        </div>
        <div class="node-column node-meta">
            {#if node.kind === "stream_source"}
                <span title={`Stream ${node.stream_id}`}>Stream {node.stream_id}</span>
                <span title={node.schema_name}>{node.schema_name ?? "Descriptor pending"}</span>
            {:else if node.kind === "transform"}
                <span>{node.transform_kind}</span>
                <span>{node.output_identifier ?? "Output id pending"}</span>
            {:else if node.kind === "viewer"}
                <span>Live inspector</span>
                <!-- ⚠️ runtimeStreamId is set only while the graph RUNS, so this
                     line read "Connect an upstream stream" over a viewer that was
                     connected, bound, and drawing live traces — the one reading
                     that makes a working node look broken. sourceLabel is
                     resolved the same way the viewer resolves what to draw. -->
                <span title={sourceLabel ?? undefined}
                    >{sourceLabel ?? "Connect an upstream stream"}</span
                >
                <button
                    type="button"
                    class="inline-graph-btn"
                    class:active={showInlineGraph}
                    title={showInlineGraph
                        ? "Hide live graph on node"
                        : "Show live graph on node"}
                    aria-pressed={showInlineGraph}
                    onmousedown={(event) => event.stopPropagation()}
                    onclick={(event) => {
                        event.stopPropagation();
                        onToggleInlineGraph?.(node.id, !showInlineGraph);
                    }}
                >
                    <LineChart size={13} />
                    <span>{showInlineGraph ? "Graph on" : "Show graph"}</span>
                </button>
            {:else if node.kind === "sink"}
                <span>Terminal node</span>
                <span title={sourceLabel ?? undefined}
                    >{sourceLabel ?? "Connect an upstream stream"}</span
                >
            {:else if node.kind === "composite"}
                <span>Composite</span>
                <span
                    >{(node.template?.nodes.length ?? 0)} nodes ·
                    {(node.input_port_ids?.length ?? 0)} in /
                    {(node.output_port_ids?.length ?? 0)} out</span
                >
            {:else if isMarkerSource}
                <span>{boundExperimentLabel ?? "No experiment bound"}</span>
                <span>markers</span>
                <div class="experiment-controls">
                    <button
                        type="button"
                        class="inline-graph-btn"
                        class:active={showInlineExperiment}
                        title={showInlineExperiment
                            ? "Hide run panel on node"
                            : "Run inline on node"}
                        aria-pressed={showInlineExperiment}
                        onmousedown={(event) => event.stopPropagation()}
                        onclick={(event) => {
                            event.stopPropagation();
                            onToggleInlineExperiment?.(
                                node.id,
                                !showInlineExperiment,
                            );
                        }}
                    >
                        <CircleDot size={13} />
                        <span>{showInlineExperiment ? "Inline on" : "Run inline"}</span>
                    </button>
                    <button
                        type="button"
                        class="inline-graph-btn"
                        title="Open the experiment in a large window"
                        onmousedown={(event) => event.stopPropagation()}
                        onclick={(event) => {
                            event.stopPropagation();
                            onExpand?.(node.id);
                        }}
                    >
                        <Maximize2 size={13} />
                        <span>Open</span>
                    </button>
                </div>
            {:else if node.kind === "train"}
                <span>Train model</span>
                <span>{node.config.families.join(", ") || "no families"}</span>
            {:else if node.kind === "export"}
                <span>Export {node.config.format}</span>
                <span>label: {node.config.label_field || "label"}</span>
            {:else if node.kind === "param"}
                <input
                    class="param-slider"
                    type="range"
                    min={node.min}
                    max={node.max}
                    step={node.step}
                    value={node.value}
                    onmousedown={(event) => event.stopPropagation()}
                    oninput={(event) =>
                        onParamValueChange?.(
                            node.id,
                            Number((event.currentTarget as HTMLInputElement).value),
                        )}
                />
                <span
                    >{node.target_field
                        ? `${node.target_field} = ${node.value}`
                        : `${node.value} (unbound)`}</span
                >
            {/if}
        </div>
        <div class="node-column outputs">
            {#each node.output_port_ids ?? [] as portId}
                <button
                    type="button"
                    class:port-selected={pendingConnection?.nodeId ===
                        node.id && pendingConnection?.portId === portId}
                    class:port-provenance={isProvenancePort(portId)}
                    class="port-button output"
                    data-node-id={node.id}
                    data-port-id={portId}
                    title={isProvenancePort(portId)
                        ? "Lineage output (provenance edge)"
                        : undefined}
                    onmousedown={(event) => {
                        event.stopPropagation();
                        onPortMouseDown?.(event, node.id, portId, "output");
                    }}
                    onclick={(event) => {
                        event.stopPropagation();
                        onPortClick(node.id, portId, "output");
                    }}
                >
                    <span>{outputPortLabels?.[portId] ?? portId}</span>
                    <span
                        class="port-dot"
                        class:port-dot-provenance={isProvenancePort(portId)}
                        class:port-dot-marker={portTone(portId, "output") ===
                            "markers"}
                        class:port-dot-both={portTone(portId, "output") === "both"}
                        data-port-anchor
                        data-port-id={portId}
                        data-port-side="output"
                    ></span>
                </button>
            {/each}
        </div>
    </div>

    <!-- Marble strips (TEC-NATKIT-106). Rendered only for a lane the
         backend actually reported: an ABSENT lane means "this node has
         no such lane", which is a different claim from an empty one, so
         drawing an empty row for it would say the markers had stopped.
         Both rows share one axis, resolved across the whole graph. -->
    {#if runtimeStatus?.data_activity || runtimeStatus?.marker_activity}
        <div class="marble-strips">
            {#if runtimeStatus.data_activity}
                <MarbleStrip
                    activity={runtimeStatus.data_activity}
                    axisEndUs={marbleAxisEndUs}
                    label="data"
                    lane="data"
                />
            {/if}
            {#if runtimeStatus.marker_activity}
                <MarbleStrip
                    activity={runtimeStatus.marker_activity}
                    axisEndUs={marbleAxisEndUs}
                    label="marks"
                    lane="markers"
                />
            {/if}
        </div>
    {/if}

    {#if showInlineGraph && inlineViewerChart}
        <div
            class="node-inline"
            role="presentation"
            onmousedown={(event) => event.stopPropagation()}
            ondblclick={(event) => event.stopPropagation()}
        >
            {@render inlineViewerChart(node)}
        </div>
    {/if}

    {#if showInlineExperiment && inlineExperiment}
        <div
            class="node-inline"
            role="presentation"
            onmousedown={(event) => event.stopPropagation()}
            ondblclick={(event) => event.stopPropagation()}
        >
            {@render inlineExperiment(node)}
        </div>
    {/if}

    <!-- Drag to resize; stops propagation so it doesn't move or select the node. -->
    <span
        class="node-resize-handle"
        role="presentation"
        title="Drag to resize"
        onmousedown={startResize}
    ></span>
</div>

<style>
    .node {
        position: absolute;
        width: 220px;
        border-radius: 8px;
        border: 1px solid rgba(122, 148, 255, 0.22);
        background: linear-gradient(
            180deg,
            rgba(15, 24, 44, 0.98),
            rgba(10, 16, 29, 0.98)
        );
        box-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
        overflow: hidden;
        /* Flex column so the body / inline chart fill any (resized) card height. */
        display: flex;
        flex-direction: column;
    }

    /* A viewer node hosting an inline live chart is wider to give the plot room;
       ports are top-anchored so width/height changes never detach edges. */
    .node.inline-viewer {
        width: 360px;
    }

    /* On an inline viewer the body is just ports + meta (natural height) and the
       chart region takes the rest; a plain node lets its body fill the card. */
    .node.inline-viewer .node-body {
        flex: 0 0 auto;
        min-height: 0;
    }

    .node-inline {
        flex: 1 1 auto;
        min-height: 120px;
        overflow: hidden;
        padding: 6px 8px 8px;
        border-top: 1px solid rgba(122, 148, 255, 0.16);
        background: rgba(6, 10, 20, 0.6);
        cursor: default;
    }

    .experiment-controls {
        display: flex;
        gap: 0.35rem;
        flex-wrap: wrap;
    }

    .inline-graph-btn {
        margin-top: 0.35rem;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.18rem 0.5rem;
        border-radius: 999px;
        border: 1px solid rgba(122, 148, 255, 0.28);
        background: rgba(20, 28, 48, 0.9);
        color: #aebbe4;
        font-size: 0.7rem;
        cursor: pointer;
    }

    .inline-graph-btn.active {
        background: rgba(76, 161, 255, 0.22);
        border-color: rgba(76, 161, 255, 0.5);
        color: #cfe2ff;
    }

    .node-resize-handle {
        position: absolute;
        right: 2px;
        bottom: 2px;
        width: 14px;
        height: 14px;
        cursor: nwse-resize;
        border-right: 2px solid rgba(122, 148, 255, 0.45);
        border-bottom: 2px solid rgba(122, 148, 255, 0.45);
        border-bottom-right-radius: 6px;
        opacity: 0;
        transition: opacity 0.12s ease;
    }

    .node:hover .node-resize-handle,
    .node.selected .node-resize-handle,
    .node.resized .node-resize-handle {
        opacity: 1;
    }

    .node-inline :global(.inline-note) {
        margin: 0;
        padding: 0.75rem 0.25rem;
        font-size: 0.78rem;
        color: #8a9ac8;
        text-align: center;
    }

    /* Keep the embedded viewer components contained within the card. */
    .node-inline > :global(*) {
        max-height: 100%;
        overflow: hidden;
    }

    .node.selected {
        border-color: rgba(103, 229, 255, 0.62);
        box-shadow: 0 0 0 1px rgba(103, 229, 255, 0.3);
    }

    .node.node-invalid {
        border-color: rgba(255, 120, 120, 0.56);
    }

    .node-header {
        width: 100%;
        /* Keep in step with HEADER_HEIGHT in streamGraph.ts. */
        height: 32px;
        flex: 0 0 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        padding: 0 0.6rem;
        cursor: grab;
        background: rgba(18, 33, 60, 0.95);
        border: 0;
        border-bottom: 1px solid rgba(122, 148, 255, 0.16);
        color: inherit;
    }

    .node-title {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        font-weight: 600;
        min-width: 52px;
        flex: 1 1 auto;
    }

    /* Icons keep their size; the label truncates instead of wrapping the 32px
       header or overflowing the fixed-width card. */
    .node-title > :global(svg) {
        flex-shrink: 0;
    }

    .node-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .node-header-meta {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        min-width: 0;
        flex: 0 1 auto;
    }

    .node-runtime-badge {
        flex-shrink: 0;
    }

    .node-kind {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .node-kind {
        display: flex;
        align-items: center;
        color: #88a0dd;
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .node-runtime-badge {
        border-radius: 999px;
        padding: 0.16rem 0.45rem;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border: 1px solid rgba(114, 142, 255, 0.18);
        background: rgba(10, 15, 29, 0.95);
    }

    .node-runtime-badge.ok {
        color: #8ef2bf;
        border-color: rgba(142, 242, 191, 0.28);
    }

    .node-runtime-badge.error {
        color: #ff8f8f;
        border-color: rgba(255, 143, 143, 0.3);
    }

    .node-runtime-badge.muted {
        color: #9dafdf;
    }

    .node-body {
        display: grid;
        grid-template-columns: 68px minmax(0, 1fr) 68px;
        flex: 1 1 auto;
        min-height: 0;
    }

    .node-column {
        display: flex;
        flex-direction: column;
        padding: 0.55rem 0.4rem;
        gap: 0.35rem;
    }

    /* Full card width, below the port columns. The track needs real width to
       say anything: squeezed into the meta column it was 2px across. */
    .marble-strips {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 0 0.5rem 0.35rem;
    }

    .node-meta {
        display: flex;
        justify-content: center;
        align-items: stretch;
        min-width: 0;
        text-align: center;
        font-size: 0.78rem;
        color: #93a3cf;
    }

    /* Long values (19-digit stream ids, schema names) truncate with a hover
       tooltip rather than overflowing the fixed-width card. */
    .node-meta > span {
        display: block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .outputs {
        align-items: flex-end;
    }

    .port-button {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.4rem;
        border-radius: 6px;
        padding: 0.35rem 0.4rem;
        font-size: 0.76rem;
        cursor: pointer;
        border: 1px solid rgba(114, 142, 255, 0.18);
        background: rgba(20, 28, 48, 0.9);
        color: inherit;
    }

    .port-button.input {
        justify-content: flex-start;
    }

    .port-button.output {
        justify-content: flex-end;
    }

    .port-button.port-selected,
    .port-button.port-armed:hover {
        border-color: rgba(103, 229, 255, 0.55);
        background: rgba(20, 52, 74, 0.96);
    }

    .port-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: #78d8ff;
        box-shadow: 0 0 0 3px rgba(120, 216, 255, 0.15);
    }

    /* Provenance ports: lineage/control wiring (source→experiment, experiment→
       train, train→classify), visually distinct from data ports (blue, dashed
       halo) to match the dashed-blue provenance edges. */
    .port-button.port-provenance {
        color: #aeb9ee;
    }
    .port-dot-provenance {
        background: #5b7bdb;
        box-shadow: 0 0 0 3px rgba(91, 123, 219, 0.18);
        outline: 1px dashed rgba(142, 162, 245, 0.75);
        outline-offset: 2px;
    }

    /* Part D: the viewer's phantom markers input — dashed/dim until enabled. */
    .port-phantom {
        opacity: 0.62;
    }
    .port-phantom:hover {
        opacity: 1;
    }
    .port-phantom-on {
        opacity: 1;
        color: #d3c1ff;
    }
    .port-dot-marker {
        background: #b491ff;
        box-shadow: 0 0 0 3px rgba(180, 145, 255, 0.18);
        outline: 1px dashed rgba(180, 145, 255, 0.7);
        outline-offset: 2px;
    }
    /* A bundle port is literally half of each: data below, markers above. */
    .port-dot-both {
        background: linear-gradient(135deg, #b491ff 0 50%, #68d7ff 50% 100%);
        box-shadow: 0 0 0 3px rgba(140, 180, 255, 0.18);
    }
    .port-phantom-on .port-dot-marker {
        outline-style: solid;
    }
</style>
