<script lang="ts">
    import {
        Archive,
        CircleDot,
        ClipboardList,
        Cpu,
        GitBranch,
        Monitor,
        Package,
        SlidersHorizontal,
    } from "@lucide/svelte";
    import { getNodeHeight, graphRunStateClass } from "./streamGraph";
    import type { StreamGraphNodeStatus } from "../StreamViewer/types";
    import type { EditorGraphNode } from "./composites";

    interface Props {
        node: EditorGraphNode;
        runtimeStatus: StreamGraphNodeStatus | null;
        selected: boolean;
        invalid: boolean;
        pendingConnection: { nodeId: string; portId: string } | null;
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
        selected,
        invalid,
        pendingConnection,
        onSelect,
        onStartDrag,
        onPortClick,
        onPortMouseDown,
        onExpand,
        onParamValueChange,
    }: Props = $props();

    function handleNodeMouseDown(event: MouseEvent) {
        if ((event.target as HTMLElement).closest(".port-button")) {
            return;
        }
        onStartDrag(event, node.id);
    }

    const nodeHeight = $derived(getNodeHeight(node));
    const runtimeStreamId = $derived(
        runtimeStatus?.output_stream_id
            ? String(runtimeStatus.output_stream_id)
            : null,
    );
</script>

<div
    class:selected
    class:node-invalid={invalid}
    class="node"
    role="button"
    tabindex="0"
    style={`left:${node.position.x}px; top:${node.position.y}px; height:${nodeHeight}px;`}
    onmousedown={(event) => {
        event.stopPropagation();
        handleNodeMouseDown(event);
    }}
    onclick={(event) => event.stopPropagation()}
    ondblclick={(event) => {
        event.stopPropagation();
        if (node.kind === "composite" || node.kind === "viewer") {
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
            {:else if node.kind === "session"}
                <ClipboardList size={14} />
            {:else if node.kind === "train"}
                <Cpu size={14} />
            {:else if node.kind === "param"}
                <SlidersHorizontal size={14} />
            {:else}
                <GitBranch size={14} />
            {/if}
            <span>{node.label}</span>
        </div>
        <div class="node-header-meta">
            {#if runtimeStatus}
                <span
                    class={`node-runtime-badge ${graphRunStateClass(runtimeStatus.state)}`}
                >
                    {runtimeStatus.state}
                </span>
            {/if}
            <span class="node-kind">{node.kind}</span>
        </div>
    </button>

    <div class="node-body">
        <div class="node-column">
            {#each node.input_port_ids ?? [] as portId}
                <button
                    type="button"
                    class:port-armed={pendingConnection !== null}
                    class="port-button input"
                    data-node-id={node.id}
                    data-port-id={portId}
                    onmousedown={(event) => {
                        event.stopPropagation();
                        onPortMouseDown?.(event, node.id, portId, "input");
                    }}
                    onclick={(event) => {
                        event.stopPropagation();
                        onPortClick(node.id, portId, "input");
                    }}
                >
                    <span class="port-dot"></span>
                    <span>{portId}</span>
                </button>
            {/each}
        </div>
        <div class="node-column node-meta">
            {#if node.kind === "stream_source"}
                <span>Stream {node.stream_id}</span>
                <span>{node.schema_name ?? "Descriptor pending"}</span>
            {:else if node.kind === "transform"}
                <span>{node.transform_kind}</span>
                <span>{node.output_identifier ?? "Output id pending"}</span>
            {:else if node.kind === "viewer"}
                <span>Live inspector</span>
                <span
                    >{runtimeStreamId
                        ? `Stream ${runtimeStreamId}`
                        : "Connect an upstream stream"}</span
                >
            {:else if node.kind === "sink"}
                <span>Terminal node</span>
                <span
                    >{runtimeStreamId
                        ? `Stream ${runtimeStreamId}`
                        : "Connect an upstream stream"}</span
                >
            {:else if node.kind === "composite"}
                <span>Composite</span>
                <span
                    >{(node.template?.nodes.length ?? 0)} nodes ·
                    {(node.input_port_ids?.length ?? 0)} in /
                    {(node.output_port_ids?.length ?? 0)} out</span
                >
            {:else if node.kind === "session"}
                <span>{node.config.protocol.label}</span>
                <span
                    >{node.config.protocol.classes.length} classes ·
                    {(node.input_port_ids?.length ?? 0)} sensors</span
                >
            {:else if node.kind === "train"}
                <span>Train model</span>
                <span>{node.config.families.join(", ") || "no families"}</span>
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
                    class="port-button output"
                    data-node-id={node.id}
                    data-port-id={portId}
                    onmousedown={(event) => {
                        event.stopPropagation();
                        onPortMouseDown?.(event, node.id, portId, "output");
                    }}
                    onclick={(event) => {
                        event.stopPropagation();
                        onPortClick(node.id, portId, "output");
                    }}
                >
                    <span>{portId}</span>
                    <span class="port-dot"></span>
                </button>
            {/each}
        </div>
    </div>
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
        height: 42px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 0.8rem;
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
    }

    .node-header-meta {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
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
        min-height: calc(100% - 42px);
    }

    .node-column {
        display: flex;
        flex-direction: column;
        padding: 0.55rem 0.4rem;
        gap: 0.35rem;
    }

    .node-meta {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        font-size: 0.78rem;
        color: #93a3cf;
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
</style>
