<script lang="ts">
    import {
        Activity,
        Archive,
        Check,
        CircleDot,
        Download,
        Eye,
        GitBranch,
        Monitor,
        Package,
        Plus,
        RefreshCw,
        Save,
        ScanSearch,
        SquareDashedMousePointer,
        Square,
        Play,
        Trash2,
        Ungroup,
        Upload,
        Workflow,
        X,
    } from "@lucide/svelte";
    import { onDestroy } from "svelte";
    import {
        findCompatibleTransformInputMappingId,
    } from "../StreamViewer/schemaDescriptor";
    import type {
        ConnectionState,
    } from "../StreamViewer/websocket";
    import MuseViewer from "../StreamViewer/MuseViewer.svelte";
    import ChannelFrameViewer from "../StreamViewer/ChannelFrameViewer.svelte";
    import FeatureVectorViewer from "../StreamViewer/FeatureVectorViewer.svelte";
    import SchemaDescriptorInspector from "../StreamViewer/SchemaDescriptorInspector.svelte";
    import ClassificationViewer from "../StreamViewer/ClassificationViewer.svelte";
    import NodeConfigFields from "../StreamViewer/NodeConfigFields.svelte";
    import { chooseViewerRenderer } from "../StreamViewer/viewerRegistry";
    import StreamGraphNodeCard from "./StreamGraphNode.svelte";
    import {
        DEFAULT_VIEWPORT,
        NODE_WIDTH,
        buildDefaultTransformConfig,
        cloneGraph,
        createEmptyGraph,
        getNodeHeight,
        getOutputDescriptorForNode,
        getPortPosition,
        graphRunStateClass,
        sanitizeIdentifier,
        type GraphStreamOption,
    } from "./streamGraph";
    import {
        extractCompositeFromSelection,
        flattenGraph,
        instantiateComposite,
        ungroupInstance,
        type CompositeTemplate,
        type EditorGraphDefinition,
        type EditorGraphNode,
    } from "./composites";
    import {
        deleteCompositeTemplate,
        downloadCompositeFile,
        importCompositeTemplates,
        listCompositeTemplates,
        loadEditorGraph,
        readCompositeFile,
        resolveCompositeTemplate,
        saveCompositeTemplate,
        saveEditorGraph,
    } from "./compositeLibrary";
    import * as Command from "$lib/components/ui/command/index.js";
    import type {
        StreamGraphDefinition,
        StreamGraphDiagnostic,
        StreamGraphEdge,
        StreamGraphNode,
        StreamGraphPosition,
        StreamGraphStatusSummary,
        TransformCapability,
        TransformCapabilityConfigField,
        NodeCatalogEntry,
        MuseSample,
        BufferedEmgSample,
        DataSchemaDescriptor,
    } from "../StreamViewer/types";

    interface Props {
        availableStreams: GraphStreamOption[];
        transformCapabilities: TransformCapability[];
        nodeCatalog: NodeCatalogEntry[];
        graphDefinitions: StreamGraphDefinition[];
        graphStatuses: Record<string, StreamGraphStatusSummary>;
        latestValidation: Record<string, StreamGraphDiagnostic[]>;
        latestEdgeValidation: Record<string, StreamGraphDiagnostic[]>;
        latestGraphDiagnostics: StreamGraphDiagnostic[];
        connectionState: ConnectionState;
        listStreamGraphs: () => void;
        requestStreamGraphStatus: (graphId: string) => void;
        saveStreamGraph: (graph: StreamGraphDefinition) => boolean;
        validateStreamGraph: (graph: StreamGraphDefinition) => boolean;
        startStreamGraph: (graphId: string) => boolean;
        stopStreamGraph: (graphId: string) => boolean;
        inspectStream: (streamId: string) => void;
        liveStreamId: string | null;
        liveStreamType: "imu" | "muse" | "emg" | null;
        liveLatestMuseSample: MuseSample | undefined;
        liveEmgSamples: BufferedEmgSample[];
        livePrimaryDescriptor: DataSchemaDescriptor | undefined;
        liveDescriptorRecordValue: unknown;
        subscribeToStream: (streamId: string) => void;
        unsubscribeFromStream: (streamId: string) => void;
        formatNumber: (num: number, decimals?: number) => string;
    }

    let {
        availableStreams,
        transformCapabilities,
        nodeCatalog,
        graphDefinitions,
        graphStatuses,
        latestValidation,
        latestEdgeValidation,
        latestGraphDiagnostics,
        connectionState,
        listStreamGraphs,
        requestStreamGraphStatus,
        saveStreamGraph,
        validateStreamGraph,
        startStreamGraph,
        stopStreamGraph,
        inspectStream,
        liveStreamType,
        liveLatestMuseSample,
        liveEmgSamples,
        livePrimaryDescriptor,
        liveDescriptorRecordValue,
        subscribeToStream,
        unsubscribeFromStream,
        formatNumber,
    }: Props = $props();

    let selectedGraphId = $state<string>("");
    let draftGraph = $state<EditorGraphDefinition>(createEmptyGraph());
    let draftGraphLoadedKey = $state("");
    let graphDirty = $state(false);
    let selectedNodeId = $state<string | null>(null);
    let selectedNodeIds = $state<Set<string>>(new Set());
    let selectedEdgeId = $state<string | null>(null);
    let compositeTemplates = $state<CompositeTemplate[]>(
        listCompositeTemplates(),
    );
    let compositeFileInput = $state<HTMLInputElement | null>(null);
    let paletteOpen = $state(false);

    function runPaletteAction(action: () => void) {
        paletteOpen = false;
        action();
    }

    function handleWindowKeydown(event: KeyboardEvent) {
        if (
            (event.metaKey || event.ctrlKey) &&
            event.key.toLowerCase() === "k"
        ) {
            event.preventDefault();
            paletteOpen = !paletteOpen;
            return;
        }
        if (event.key === "Delete" || event.key === "Backspace") {
            const target = event.target as HTMLElement | null;
            const isTextEntry =
                target?.tagName === "INPUT" ||
                target?.tagName === "TEXTAREA" ||
                target?.isContentEditable;
            if (isTextEntry) {
                return;
            }
            if (selectedNodeIds.size > 0 || selectedEdgeId) {
                event.preventDefault();
                removeSelectedItem();
            }
        }
    }
    let pendingConnection = $state<{
        nodeId: string;
        portId: string;
    } | null>(null);
    let connectionDrag = $state<{
        nodeId: string;
        portId: string;
        startClientX: number;
        startClientY: number;
        pointerGraphX: number;
        pointerGraphY: number;
    } | null>(null);
    let contextMenu = $state<{
        open: boolean;
        x: number;
        y: number;
        graphPosition: StreamGraphPosition;
    }>({
        open: false,
        x: 0,
        y: 0,
        graphPosition: { x: 0, y: 0 },
    });
    let panState = $state<{
        startClientX: number;
        startClientY: number;
        startX: number;
        startY: number;
    } | null>(null);
    let dragState = $state<{
        nodeId: string;
        offsetX: number;
        offsetY: number;
    } | null>(null);
    let canvasElement = $state<HTMLDivElement | null>(null);
    // Prefer the locally-persisted editor graph (which keeps composites
    // collapsed) over the flattened backend copy. The backend store is lossy —
    // it strips composite metadata and may re-stamp updated_at_us on save — so
    // whenever we have a local editor version for this graph it is the more
    // complete source of truth. (v1 limitation: a graph edited on another
    // machine will not auto-refresh here until local state is cleared.)
    function resolveDraftForGraph(
        backendGraph: StreamGraphDefinition,
    ): EditorGraphDefinition {
        const editorGraph = loadEditorGraph(backendGraph.graph_id);
        if (editorGraph) {
            return cloneGraph(editorGraph);
        }
        return cloneGraph(backendGraph) as EditorGraphDefinition;
    }

    $effect(() => {
        if (graphDefinitions.length === 0) {
            if (!graphDirty) {
                const nextDraftGraph = createEmptyGraph();
                draftGraph = nextDraftGraph;
                selectedGraphId = nextDraftGraph.graph_id;
                draftGraphLoadedKey = nextDraftGraph.graph_id;
                selectedNodeId = null;
                selectedNodeIds = new Set();
                selectedEdgeId = null;
            }
            return;
        }

        const matchingGraph =
            graphDefinitions.find((graph) => graph.graph_id === selectedGraphId) ??
            graphDefinitions[0];
        const graphKey = `${matchingGraph.graph_id}:${matchingGraph.updated_at_us ?? 0}`;

        if (!selectedGraphId) {
            selectedGraphId = matchingGraph.graph_id;
        }

        if (!graphDirty && draftGraphLoadedKey !== graphKey) {
            const nextDraftGraph = resolveDraftForGraph(matchingGraph);
            draftGraph = nextDraftGraph;
            selectedGraphId = matchingGraph.graph_id;
            selectedNodeId = nextDraftGraph.ui?.selected_node_id ?? null;
            selectedNodeIds = selectedNodeId
                ? new Set([selectedNodeId])
                : new Set();
            selectedEdgeId = null;
            draftGraphLoadedKey = graphKey;
        }
    });

    const selectedGraphStatus = $derived(
        graphStatuses[selectedGraphId] ?? null,
    );

    const selectedNode = $derived(
        draftGraph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    );

    const selectedSourceNode = $derived(
        selectedNode?.kind === "stream_source" ? selectedNode : null,
    );

    const selectedTransformNode = $derived(
        selectedNode?.kind === "transform" ? selectedNode : null,
    );

    const selectedCombineNode = $derived(
        selectedNode?.kind === "combine" ? selectedNode : null,
    );

    const selectedNodeCapability = $derived(
        selectedTransformNode
            ? transformCapabilities.find(
                  (capability) =>
                      capability.kind === selectedTransformNode.transform_kind,
              ) ?? null
            : null,
    );

    const graphJsonPreview = $derived(JSON.stringify(draftGraph, null, 2));
    const selectedNodeRuntimeStatus = $derived(
        selectedNodeId
            ? selectedGraphStatus?.node_statuses?.[selectedNodeId] ?? null
            : null,
    );

    const graphValidationCount = $derived(
        Object.values(latestValidation).reduce(
            (count, diagnostics) => count + diagnostics.length,
            latestGraphDiagnostics.length,
        ) +
            Object.values(latestEdgeValidation).reduce(
                (count, diagnostics) => count + diagnostics.length,
                0,
            ),
    );

    // Node/edge diagnostics only render in the inspector when that specific
    // element is selected, so a failed start (which reports diagnostics
    // against unselected nodes/edges) would otherwise show no explanation
    // anywhere. Surface them here too, labeled by node/edge, so a start
    // failure is always visible without hunting through every node.
    const elementDiagnostics = $derived.by(() => {
        const nodeLabelById = new Map(
            draftGraph.nodes.map((node) => [node.id, node.label || node.id]),
        );
        const fromNodes = Object.entries(latestValidation).flatMap(
            ([nodeId, diagnostics]) =>
                diagnostics.map((diagnostic) => ({
                    label: nodeLabelById.get(nodeId) ?? nodeId,
                    diagnostic,
                })),
        );
        const fromEdges = Object.entries(latestEdgeValidation).flatMap(
            ([edgeId, diagnostics]) =>
                diagnostics.map((diagnostic) => ({
                    label: `Edge ${edgeId}`,
                    diagnostic,
                })),
        );
        return [...fromNodes, ...fromEdges];
    });

    // Same gap as elementDiagnostics, but for the graph *after* it starts:
    // a failed/blocked node's runtime status message only rendered in the
    // inspector when that exact node was selected, so a run that errors out
    // looked like silent failure unless you happened to click the right
    // node. Node ids here are the flattened (possibly composite-namespaced,
    // e.g. "instance-id::inner-id") backend ids, not the draft graph's
    // top-level node ids, so we can't always resolve a friendly label —
    // fall back to the raw id, which at least identifies the node.
    const runtimeIssues = $derived.by(() => {
        const nodeLabelById = new Map(
            draftGraph.nodes.map((node) => [node.id, node.label || node.id]),
        );
        return Object.entries(selectedGraphStatus?.node_statuses ?? {})
            .filter(([, status]) => status.state === "error" || status.state === "blocked")
            .map(([nodeId, status]) => ({
                label: nodeLabelById.get(nodeId) ?? nodeId,
                message: status.message ?? `Node is ${status.state}.`,
            }));
    });

    function markDraftChanged(nextGraph: EditorGraphDefinition) {
        nextGraph.updated_at_us = Date.now() * 1000;
        nextGraph.ui = nextGraph.ui ?? {};
        nextGraph.ui.selected_node_id = selectedNodeId;
        draftGraph = nextGraph;
        graphDirty = true;
    }

    function selectGraph(graphId: string) {
        if (graphDirty) {
            const shouldDiscard = window.confirm(
                "Discard unsaved graph edits?",
            );
            if (!shouldDiscard) {
                return;
            }
        }
        const matchingGraph =
            graphDefinitions.find((graph) => graph.graph_id === graphId) ?? null;
        if (!matchingGraph) {
            return;
        }
        selectedGraphId = graphId;
        draftGraph = resolveDraftForGraph(matchingGraph);
        draftGraphLoadedKey = `${matchingGraph.graph_id}:${matchingGraph.updated_at_us ?? 0}`;
        graphDirty = false;
        selectedNodeId = draftGraph.ui?.selected_node_id ?? null;
        selectedNodeIds = selectedNodeId ? new Set([selectedNodeId]) : new Set();
        selectedEdgeId = null;
        pendingConnection = null;
        requestStreamGraphStatus(graphId);
    }

    function createGraph() {
        if (graphDirty) {
            const shouldDiscard = window.confirm(
                "Discard unsaved graph edits?",
            );
            if (!shouldDiscard) {
                return;
            }
        }
        draftGraph = createEmptyGraph();
        selectedGraphId = draftGraph.graph_id;
        draftGraphLoadedKey = selectedGraphId;
        graphDirty = true;
        selectedNodeId = null;
        selectedNodeIds = new Set();
        selectedEdgeId = null;
        pendingConnection = null;
    }

    function getCanvasGraphPosition(clientX: number, clientY: number) {
        if (!canvasElement) {
            return { x: 0, y: 0 };
        }
        const bounds = canvasElement.getBoundingClientRect();
        const viewport = draftGraph.ui?.viewport ?? DEFAULT_VIEWPORT;
        return {
            x: (clientX - bounds.left - viewport.x) / viewport.zoom,
            y: (clientY - bounds.top - viewport.y) / viewport.zoom,
        };
    }

    function openContextMenu(event: MouseEvent) {
        event.preventDefault();
        const graphPosition = getCanvasGraphPosition(
            event.clientX,
            event.clientY,
        );
        contextMenu = {
            open: true,
            x: event.clientX,
            y: event.clientY,
            graphPosition,
        };
    }

    function openContextMenuAtCanvasCenter() {
        if (!canvasElement) {
            contextMenu = {
                open: true,
                x: window.innerWidth / 2,
                y: window.innerHeight / 2,
                graphPosition: { x: 160, y: 120 },
            };
            return;
        }
        const bounds = canvasElement.getBoundingClientRect();
        const clientX = bounds.left + Math.min(bounds.width * 0.5, 320);
        const clientY = bounds.top + Math.min(bounds.height * 0.25, 220);
        contextMenu = {
            open: true,
            x: clientX,
            y: clientY,
            graphPosition: getCanvasGraphPosition(clientX, clientY),
        };
    }

    function getDefaultInsertionPosition(): StreamGraphPosition {
        if (!canvasElement) {
            return { x: 160, y: 120 };
        }
        const bounds = canvasElement.getBoundingClientRect();
        const clientX = bounds.left + Math.min(bounds.width * 0.5, 320);
        const clientY = bounds.top + Math.min(bounds.height * 0.25, 220);
        return getCanvasGraphPosition(clientX, clientY);
    }

    function closeContextMenu() {
        contextMenu = {
            ...contextMenu,
            open: false,
        };
    }

    function handleWindowPointerDown(event: MouseEvent) {
        if (!contextMenu.open) {
            return;
        }
        const target = event.target as HTMLElement | null;
        if (
            target?.closest(".context-menu") ||
            target?.closest(".graph-canvas")
        ) {
            return;
        }
        closeContextMenu();
    }

    function addSourceNode(
        streamId: string,
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const stream =
            availableStreams.find((item) => item.streamId === streamId) ?? null;
        if (!stream) {
            return;
        }
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `source/${sanitizeIdentifier(streamId)}-${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "stream_source",
            label: `Stream ${streamId}`,
            position: { ...position },
            stream_id: streamId,
            schema_name: stream.schemaName,
            output_port_ids: ["data"],
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    function addTransformNode(
        kind: string,
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const capability =
            transformCapabilities.find((item) => item.kind === kind) ?? null;
        if (!capability) {
            return;
        }
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `transform/${sanitizeIdentifier(kind)}-${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "transform",
            label: capability.label,
            position: { ...position },
            transform_kind: capability.kind,
            input_mapping_id: capability.input_mappings[0]?.id,
            config: buildDefaultTransformConfig(capability),
            output_identifier: sanitizeIdentifier(
                `${draftGraph.graph_id}-${capability.kind}`,
            ),
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    function addViewerNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `viewer/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "viewer",
            label: "Viewer",
            position: { ...position },
            input_port_ids: ["input"],
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    function addSinkNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `sink/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "sink",
            label: "Sink",
            position: { ...position },
            input_port_ids: ["input"],
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    // Fans in >=2 upstream streams. Starts with 2 input ports; more can be
    // added from the inspector once additional upstream nodes are wired up.
    function addCombineNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `combine/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "combine",
            label: "Combine",
            position: { ...position },
            input_port_ids: ["in1", "in2"],
            output_port_ids: ["data"],
            output_identifier: sanitizeIdentifier(
                `${draftGraph.graph_id}-combine-${Date.now()}`,
            ),
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    // Non-source, non-transform node types the palette offers as fixed
    // "utility" entries (viewer, sink, combine, …). Driven by the backend
    // catalog so a new structural node type appears without editing this file.
    // Stream sources are enumerated from availableStreams instead (one per
    // live stream), and transforms have their own catalog-driven group.
    const utilityCatalog = $derived(
        nodeCatalog.filter(
            (entry) =>
                entry.kind !== "stream_source" && entry.kind !== "transform",
        ),
    );

    // Dispatch a catalog entry to the matching node-creation path. Structural
    // kinds keep their bespoke creation (ports, stream binding); this is the
    // one place that maps catalog kind → constructor.
    function addCatalogNode(
        entry: NodeCatalogEntry,
        position?: StreamGraphPosition,
    ) {
        if (entry.kind === "viewer") {
            addViewerNode(position);
        } else if (entry.kind === "sink") {
            addSinkNode(position);
        } else if (entry.kind === "combine") {
            addCombineNode(position);
        } else if (entry.kind === "transform") {
            addTransformNode(entry.node_type, position);
        }
    }

    function utilityIcon(kind: string) {
        if (kind === "viewer") return Monitor;
        if (kind === "sink") return Archive;
        return GitBranch;
    }

    function addCombineInputPort() {
        updateSelectedNode((node) => {
            if (node.kind !== "combine") {
                return node;
            }
            const ports = node.input_port_ids ?? [];
            return {
                ...node,
                input_port_ids: [...ports, `in${ports.length + 1}`],
            };
        });
    }

    function removeCombineInputPort() {
        updateSelectedNode((node) => {
            if (node.kind !== "combine") {
                return node;
            }
            const ports = node.input_port_ids ?? [];
            if (ports.length <= 2) {
                return node;
            }
            return { ...node, input_port_ids: ports.slice(0, -1) };
        });
    }

    function selectNode(nodeId: string, event?: MouseEvent) {
        const additive = Boolean(
            event && (event.shiftKey || event.ctrlKey || event.metaKey),
        );
        if (additive) {
            const nextSelection = new Set(selectedNodeIds);
            if (nextSelection.has(nodeId)) {
                nextSelection.delete(nodeId);
            } else {
                nextSelection.add(nodeId);
            }
            selectedNodeIds = nextSelection;
            selectedNodeId =
                nextSelection.size > 0 ? nodeId : null;
        } else {
            selectedNodeIds = new Set([nodeId]);
            selectedNodeId = nodeId;
        }
        selectedEdgeId = null;
        const nextGraph = cloneGraph(draftGraph);
        nextGraph.ui = nextGraph.ui ?? {};
        nextGraph.ui.selected_node_id = selectedNodeId;
        markDraftChanged(nextGraph);
    }

    function selectEdge(edgeId: string) {
        selectedEdgeId = edgeId;
        selectedNodeId = null;
        selectedNodeIds = new Set();
    }

    function removeSelectedItem() {
        if (selectedNodeIds.size > 0) {
            const removed = selectedNodeIds;
            const nextGraph = cloneGraph(draftGraph);
            nextGraph.nodes = nextGraph.nodes.filter(
                (node) => !removed.has(node.id),
            );
            nextGraph.edges = nextGraph.edges.filter(
                (edge) =>
                    !removed.has(edge.source_node_id) &&
                    !removed.has(edge.target_node_id),
            );
            selectedNodeId = null;
            selectedNodeIds = new Set();
            pendingConnection = null;
            markDraftChanged(nextGraph);
            return;
        }

        if (selectedEdgeId) {
            const nextGraph = cloneGraph(draftGraph);
            nextGraph.edges = nextGraph.edges.filter(
                (edge) => edge.id !== selectedEdgeId,
            );
            selectedEdgeId = null;
            markDraftChanged(nextGraph);
        }
    }

    function startNodeDrag(event: MouseEvent, nodeId: string) {
        event.stopPropagation();
        const node = draftGraph.nodes.find((entry) => entry.id === nodeId);
        if (!node) {
            return;
        }
        const graphPosition = getCanvasGraphPosition(
            event.clientX,
            event.clientY,
        );
        dragState = {
            nodeId,
            offsetX: graphPosition.x - node.position.x,
            offsetY: graphPosition.y - node.position.y,
        };
        selectNode(nodeId, event);
    }

    function startPan(event: MouseEvent) {
        if ((event.target as HTMLElement).closest(".node")) {
            return;
        }
        const viewport = draftGraph.ui?.viewport ?? { ...DEFAULT_VIEWPORT };
        panState = {
            startClientX: event.clientX,
            startClientY: event.clientY,
            startX: viewport.x,
            startY: viewport.y,
        };
        selectedEdgeId = null;
    }

    function handlePointerMove(event: MouseEvent) {
        if (dragState) {
            const graphPosition = getCanvasGraphPosition(
                event.clientX,
                event.clientY,
            );
            const nextGraph = cloneGraph(draftGraph);
            nextGraph.nodes = nextGraph.nodes.map((node) =>
                node.id === dragState?.nodeId
                    ? {
                          ...node,
                          position: {
                              x: Math.round(graphPosition.x - dragState.offsetX),
                              y: Math.round(graphPosition.y - dragState.offsetY),
                          },
                      }
                    : node,
            );
            markDraftChanged(nextGraph);
            return;
        }

        if (panState) {
            const nextGraph = cloneGraph(draftGraph);
            nextGraph.ui = nextGraph.ui ?? {};
            nextGraph.ui.viewport = {
                x: panState.startX + event.clientX - panState.startClientX,
                y: panState.startY + event.clientY - panState.startClientY,
                zoom: nextGraph.ui.viewport?.zoom ?? DEFAULT_VIEWPORT.zoom,
            };
            markDraftChanged(nextGraph);
            return;
        }

        if (connectionDrag) {
            const graphPosition = getCanvasGraphPosition(
                event.clientX,
                event.clientY,
            );
            connectionDrag = {
                ...connectionDrag,
                pointerGraphX: graphPosition.x,
                pointerGraphY: graphPosition.y,
            };
        }
    }

    function endPointerInteraction(event: MouseEvent) {
        dragState = null;
        panState = null;

        if (connectionDrag) {
            const drag = connectionDrag;
            connectionDrag = null;
            const movedDistance = Math.hypot(
                event.clientX - drag.startClientX,
                event.clientY - drag.startClientY,
            );
            const targetPort = (
                document.elementFromPoint(
                    event.clientX,
                    event.clientY,
                ) as HTMLElement | null
            )?.closest(".port-button.input") as HTMLElement | null;
            const targetNodeId = targetPort?.dataset.nodeId;
            const targetPortId = targetPort?.dataset.portId;
            if (targetNodeId && targetPortId) {
                handlePortClick(targetNodeId, targetPortId, "input");
            } else if (movedDistance > 4) {
                // A real drag ended over empty space — cancel the armed connection
                // rather than leaving it dangling for an unrelated later click.
                pendingConnection = null;
            }
        }
    }

    function handleCanvasWheel(event: WheelEvent) {
        event.preventDefault();
        const graphPosition = getCanvasGraphPosition(
            event.clientX,
            event.clientY,
        );
        const nextGraph = cloneGraph(draftGraph);
        nextGraph.ui = nextGraph.ui ?? {};
        const currentViewport = nextGraph.ui.viewport ?? {
            ...DEFAULT_VIEWPORT,
        };
        const nextZoom = Math.min(
            1.8,
            Math.max(0.45, currentViewport.zoom - event.deltaY * 0.0012),
        );
        nextGraph.ui.viewport = {
            zoom: nextZoom,
            x: event.clientX -
                (graphPosition.x * nextZoom +
                    (canvasElement?.getBoundingClientRect().left ?? 0)),
            y: event.clientY -
                (graphPosition.y * nextZoom +
                    (canvasElement?.getBoundingClientRect().top ?? 0)),
        };
        markDraftChanged(nextGraph);
    }

    function handlePortMouseDown(
        event: MouseEvent,
        nodeId: string,
        portId: string,
        side: "input" | "output",
    ) {
        if (side !== "output") {
            return;
        }
        pendingConnection = { nodeId, portId };
        selectedEdgeId = null;
        selectedNodeId = nodeId;
        const graphPosition = getCanvasGraphPosition(
            event.clientX,
            event.clientY,
        );
        connectionDrag = {
            nodeId,
            portId,
            startClientX: event.clientX,
            startClientY: event.clientY,
            pointerGraphX: graphPosition.x,
            pointerGraphY: graphPosition.y,
        };
    }

    function handlePortClick(
        nodeId: string,
        portId: string,
        side: "input" | "output",
    ) {
        if (side === "output") {
            pendingConnection = { nodeId, portId };
            selectedEdgeId = null;
            selectedNodeId = nodeId;
            return;
        }

        if (!pendingConnection || pendingConnection.nodeId === nodeId) {
            return;
        }
        const connection = pendingConnection;

        const duplicateEdge = draftGraph.edges.some(
            (edge) =>
                edge.target_node_id === nodeId &&
                edge.target_port === portId &&
                edge.source_node_id === connection.nodeId &&
                edge.source_port === connection.portId,
        );
        if (duplicateEdge) {
            pendingConnection = null;
            return;
        }

        const nextGraph = cloneGraph(draftGraph);
        nextGraph.edges = nextGraph.edges.filter(
            (edge) =>
                !(
                    edge.target_node_id === nodeId &&
                    edge.target_port === portId
                ),
        );
        nextGraph.edges.push({
            id: `edge-${Date.now()}`,
            source_node_id: connection.nodeId,
            source_port: connection.portId,
            target_node_id: nodeId,
            target_port: portId,
        });

        nextGraph.nodes = nextGraph.nodes.map((node) => {
            if (node.id !== nodeId || node.kind !== "transform") {
                return node;
            }
            const capability =
                transformCapabilities.find(
                    (item) => item.kind === node.transform_kind,
                ) ?? null;
            if (!capability) {
                return node;
            }

            const sourceNode = nextGraph.nodes.find(
                (item) => item.id === connection.nodeId,
            );
            const sourceDescriptor = getOutputDescriptorForNode(
                sourceNode,
                availableStreams,
            );
            return {
                ...node,
                input_mapping_id:
                    findCompatibleTransformInputMappingId(
                        sourceDescriptor,
                        capability,
                    ) ?? node.input_mapping_id,
            };
        });

        pendingConnection = null;
        markDraftChanged(nextGraph);
    }

    function updateGraphMetadata(
        key: "label" | "description" | "graph_id",
        value: string,
    ) {
        const nextGraph = cloneGraph(draftGraph);
        if (key === "graph_id") {
            nextGraph.graph_id = sanitizeIdentifier(value);
        } else if (key === "label") {
            nextGraph.label = value;
        } else {
            nextGraph.description = value;
        }
        markDraftChanged(nextGraph);
        if (key === "graph_id") {
            selectedGraphId = nextGraph.graph_id;
        }
    }

    function updateSelectedNode(
        update: (node: StreamGraphNode) => StreamGraphNode,
    ) {
        if (!selectedNodeId) {
            return;
        }
        const nextGraph = cloneGraph(draftGraph);
        nextGraph.nodes = nextGraph.nodes.map((node) => {
            if (node.id !== selectedNodeId || node.kind === "composite") {
                return node;
            }
            return update(node);
        });
        markDraftChanged(nextGraph);
    }

    function updateTransformConfigField(
        field: TransformCapabilityConfigField,
        rawValue: string,
    ) {
        updateSelectedNode((node) => {
            if (node.kind !== "transform") {
                return node;
            }
            const nextConfig = { ...node.config };
            nextConfig[field.id] =
                field.type === "number" ? Number(rawValue) : rawValue;
            return {
                ...node,
                config: nextConfig,
            };
        });
    }

    // Flatten composites into primitives for the backend (which only understands
    // the four primitive node kinds).
    function flattenedForBackend(): StreamGraphDefinition {
        const { graph } = flattenGraph(
            cloneGraph(draftGraph),
            resolveCompositeTemplate,
        );
        graph.ui = graph.ui ?? {};
        graph.ui.selected_node_id = selectedNodeId;
        return graph;
    }

    function saveDraftGraph() {
        // Persist the editor version (with composites collapsed) locally first.
        saveEditorGraph($state.snapshot(draftGraph) as EditorGraphDefinition);
        const flattened = flattenedForBackend();
        const sent = saveStreamGraph(flattened);
        if (sent) {
            graphDirty = false;
            draftGraphLoadedKey = `${flattened.graph_id}:${flattened.updated_at_us ?? 0}`;
        }
    }

    function runValidation() {
        validateStreamGraph(flattenedForBackend());
    }

    function startSelectedGraph() {
        if (draftGraph.graph_id) {
            startStreamGraph(draftGraph.graph_id);
        }
    }

    function stopSelectedGraph() {
        if (draftGraph.graph_id) {
            stopStreamGraph(draftGraph.graph_id);
        }
    }

    // --- Composite (higher-order node) actions ---------------------------

    const selectedIsComposite = $derived(
        selectedNode?.kind === "composite" ? selectedNode : null,
    );

    function refreshCompositeTemplates() {
        compositeTemplates = listCompositeTemplates();
    }

    function createCompositeFromSelection() {
        if (selectedNodeIds.size === 0) {
            return;
        }
        const label = window.prompt(
            "Name this composite",
            "New composite",
        );
        if (!label) {
            return;
        }
        const result = extractCompositeFromSelection(
            draftGraph,
            selectedNodeIds,
            label,
        );
        if (!result) {
            window.alert(
                "Cannot create a composite from this selection. Composites cannot contain other composites yet.",
            );
            return;
        }
        saveCompositeTemplate(result.template);
        refreshCompositeTemplates();
        selectedNodeId = result.instance.id;
        selectedNodeIds = new Set([result.instance.id]);
        selectedEdgeId = null;
        markDraftChanged(result.nextGraph);
    }

    function addCompositeInstance(
        template: CompositeTemplate,
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const instance = instantiateComposite(template, position);
        nextGraph.nodes.push(instance);
        selectedNodeId = instance.id;
        selectedNodeIds = new Set([instance.id]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    function ungroupSelectedComposite() {
        if (!selectedNodeId || selectedIsComposite === null) {
            return;
        }
        const nextGraph = ungroupInstance(draftGraph, selectedNodeId);
        selectedNodeId = null;
        selectedNodeIds = new Set();
        selectedEdgeId = null;
        markDraftChanged(nextGraph);
    }

    function exportComposite(template: CompositeTemplate) {
        downloadCompositeFile([template]);
    }

    let expandedComposite = $state<CompositeTemplate | null>(null);

    function openCompositeInternals(node: EditorGraphNode | null) {
        if (!node || node.kind !== "composite") {
            return;
        }
        expandedComposite =
            node.template ?? resolveCompositeTemplate(node.composite_id) ?? null;
    }

    function closeCompositeInternals() {
        expandedComposite = null;
    }

    let expandedViewerNodeId = $state<string | null>(null);

    const expandedViewerStreamId = $derived(
        expandedViewerNodeId
            ? nodeRuntimeStatus(expandedViewerNodeId)?.output_stream_id ??
                  null
            : null,
    );

    function openViewerData(node: EditorGraphNode | null) {
        if (!node || node.kind !== "viewer") {
            return;
        }
        const streamId = nodeRuntimeStatus(node.id)?.output_stream_id;
        if (!streamId) {
            return;
        }
        expandedViewerNodeId = node.id;
        subscribeToStream(String(streamId));
    }

    function closeViewerData() {
        if (expandedViewerStreamId) {
            unsubscribeFromStream(String(expandedViewerStreamId));
        }
        expandedViewerNodeId = null;
    }

    function handleNodeExpand(nodeId: string) {
        const node = draftGraph.nodes.find((item) => item.id === nodeId) ?? null;
        if (node?.kind === "composite") {
            openCompositeInternals(node);
        } else if (node?.kind === "viewer") {
            openViewerData(node);
        }
    }

    onDestroy(() => {
        if (expandedViewerStreamId) {
            unsubscribeFromStream(String(expandedViewerStreamId));
        }
    });

    // Composite templates are authored with node positions relative to an
    // arbitrary origin and commonly go negative (e.g. features fanned out
    // above/below a midline) since they're never panned/scrolled during
    // authoring. This preview has no pan controls, so nodes at negative
    // positions render outside the scrollable area and are unreachable.
    // Shift every node so the layout's top-left corner sits at (20, 20).
    function compositeInternalsLayout(template: CompositeTemplate) {
        const minX = Math.min(0, ...template.nodes.map((node) => node.position.x));
        const minY = Math.min(0, ...template.nodes.map((node) => node.position.y));
        const offsetX = 20 - minX;
        const offsetY = 20 - minY;
        const nodes = template.nodes.map((node) => ({
            ...node,
            position: {
                x: node.position.x + offsetX,
                y: node.position.y + offsetY,
            },
        }));
        const maxX = Math.max(
            ...nodes.map((node) => node.position.x + NODE_WIDTH),
            220,
        );
        const maxY = Math.max(
            ...nodes.map((node) => node.position.y + getNodeHeight(node)),
            140,
        );
        return { nodes, width: maxX + 20, height: maxY + 20 };
    }

    function removeCompositeTemplate(compositeId: string) {
        deleteCompositeTemplate(compositeId);
        refreshCompositeTemplates();
    }

    async function handleCompositeFileChange(event: Event) {
        const input = event.currentTarget as HTMLInputElement;
        const file = input.files?.[0];
        if (!file) {
            return;
        }
        const { templates, errors } = await readCompositeFile(file);
        input.value = "";
        if (templates.length > 0) {
            importCompositeTemplates(templates);
            refreshCompositeTemplates();
        }
        if (errors.length > 0) {
            window.alert(errors.join("\n"));
        }
    }

    function edgeDiagnostics(edgeId: string) {
        return latestEdgeValidation[edgeId] ?? [];
    }

    function nodeDiagnostics(nodeId: string) {
        return latestValidation[nodeId] ?? [];
    }

    function nodeRuntimeStatus(nodeId: string) {
        return selectedGraphStatus?.node_statuses?.[nodeId] ?? null;
    }

    // The renderer for a viewer node is chosen from the upstream output's
    // descriptor capability plus the latest frame's shape — never from a sensor
    // name. A per-window feature vector routes to the bars/heatmap viewer, a
    // classifier frame to the classification readout, a waveform to the trace,
    // and anything else to the generic inspector.
    const liveRenderer = $derived.by(() => {
        const latest = liveEmgSamples.at(-1);
        const hint = latest
            ? {
                  n_channels: latest.n_channels,
                  samples_per_channel: latest.samples_per_channel,
                  channel_labels: latest.channel_labels,
              }
            : undefined;
        return chooseViewerRenderer(livePrimaryDescriptor, hint);
    });

</script>

<svelte:window
    onmousemove={handlePointerMove}
    onmouseup={endPointerInteraction}
    onmousedown={handleWindowPointerDown}
    onkeydown={handleWindowKeydown}
/>

<div class="graph-editor">
    <div class="graph-sidebar">
        <div class="sidebar-header">
            <div>
                <p class="eyebrow">Stream Graphs</p>
                <h3>Boards</h3>
            </div>
            <div class="sidebar-actions">
                <button type="button" class="icon-btn" onclick={createGraph}>
                    <Plus size={16} />
                </button>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={listStreamGraphs}
                    title="Refresh saved graphs"
                >
                    <RefreshCw size={16} />
                </button>
            </div>
        </div>

        <div class="graph-list">
            {#if graphDefinitions.length === 0}
                <div class="empty-state">
                    <Workflow size={18} />
                    <p>No saved graphs yet.</p>
                </div>
            {:else}
                {#each graphDefinitions as graph}
                    <button
                        type="button"
                        class:selected={graph.graph_id === selectedGraphId}
                        class="graph-list-item"
                        onclick={() => selectGraph(graph.graph_id)}
                    >
                        <span class="graph-list-row">
                            <span class="graph-list-title">{graph.label}</span>
                            <span
                                class={`run-pill ${graphRunStateClass(
                                    graphStatuses[graph.graph_id]?.run_state,
                                )}`}
                            >
                                {graphStatuses[graph.graph_id]?.run_state ??
                                    "draft"}
                            </span>
                        </span>
                        <span class="graph-list-meta">{graph.graph_id}</span>
                    </button>
                {/each}
            {/if}
        </div>

        <div class="summary-card">
            <div class="summary-row">
                <span>Connection</span>
                <strong>{connectionState}</strong>
            </div>
            <div class="summary-row">
                <span>Run state</span>
                <strong class={graphRunStateClass(selectedGraphStatus?.run_state)}>
                    {selectedGraphStatus?.run_state ?? "stopped"}
                </strong>
            </div>
            <div class="summary-row">
                <span>Nodes</span>
                <strong>{draftGraph.nodes.length}</strong>
            </div>
            <div class="summary-row">
                <span>Edges</span>
                <strong>{draftGraph.edges.length}</strong>
            </div>
        </div>

        <div class="summary-card">
            <p class="eyebrow">Node Library</p>
            <div class="library-group">
                <span class="library-title">Utility</span>
                <div class="library-actions">
                    {#each utilityCatalog as entry}
                        <button
                            type="button"
                            class="graph-list-item"
                            title={entry.description}
                            onclick={() => addCatalogNode(entry)}
                        >
                            <span class="graph-list-title">{entry.label}</span>
                            <span class="graph-list-meta">{entry.description}</span>
                        </button>
                    {/each}
                </div>
            </div>

            <div class="library-group">
                <span class="library-title">Transforms</span>
                <div class="library-actions">
                    {#each transformCapabilities as capability}
                        <button
                            type="button"
                            class="graph-list-item"
                            onclick={() => addTransformNode(capability.kind)}
                        >
                            <span class="graph-list-title">{capability.label}</span>
                            <span class="graph-list-meta">{capability.kind}</span>
                        </button>
                    {/each}
                </div>
            </div>

            <div class="library-group">
                <span class="library-title">Streams</span>
                <div class="library-actions">
                    {#each availableStreams as stream}
                        <button
                            type="button"
                            class="graph-list-item"
                            onclick={() => addSourceNode(stream.streamId)}
                        >
                            <span class="graph-list-title">Stream {stream.streamId}</span>
                            <span class="graph-list-meta">{stream.schemaName}</span>
                        </button>
                    {/each}
                </div>
            </div>
        </div>

        <div class="summary-card">
            <div class="library-header">
                <p class="eyebrow">Composites</p>
                <div class="sidebar-actions">
                    <button
                        type="button"
                        class="icon-btn"
                        title="Import composites"
                        onclick={() => compositeFileInput?.click()}
                    >
                        <Upload size={15} />
                    </button>
                </div>
            </div>
            <div class="library-actions">
                {#if compositeTemplates.length === 0}
                    <div class="empty-state">
                        <Package size={16} />
                        <p>No saved composites yet.</p>
                    </div>
                {:else}
                    {#each compositeTemplates as template}
                        <div class="composite-row">
                            <button
                                type="button"
                                class="graph-list-item composite-add"
                                onclick={() => addCompositeInstance(template)}
                            >
                                <span class="graph-list-title">{template.label}</span>
                                <span class="graph-list-meta">
                                    {template.nodes.length} nodes ·
                                    {template.inputs.length} in /
                                    {template.outputs.length} out
                                </span>
                            </button>
                            <div class="composite-row-actions">
                                <button
                                    type="button"
                                    class="icon-btn"
                                    title="Export composite"
                                    onclick={() => exportComposite(template)}
                                >
                                    <Download size={14} />
                                </button>
                                <button
                                    type="button"
                                    class="icon-btn danger"
                                    title="Delete composite"
                                    onclick={() =>
                                        removeCompositeTemplate(
                                            template.composite_id,
                                        )}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        </div>
                    {/each}
                {/if}
            </div>
        </div>
    </div>

    <div class="graph-main">
        <div class="graph-toolbar">
            <div class="toolbar-group">
                <SquareDashedMousePointer size={16} />
                <input
                    class="graph-title-input"
                    value={draftGraph.label}
                    oninput={(event) =>
                        updateGraphMetadata(
                            "label",
                            (event.currentTarget as HTMLInputElement).value,
                        )}
                />
                <span class="graph-id">{draftGraph.graph_id}</span>
                {#if graphDirty}
                    <span class="dirty-pill">Unsaved</span>
                {/if}
            </div>
            <div class="toolbar-actions">
                <button
                    type="button"
                    class="action-btn secondary"
                    onclick={startSelectedGraph}
                    disabled={selectedGraphStatus?.run_state === "starting"}
                >
                    {#if selectedGraphStatus?.run_state === "starting"}
                        <RefreshCw size={16} class="spin" />
                        Starting…
                    {:else}
                        <Play size={16} />
                        Start
                    {/if}
                </button>
                <button
                    type="button"
                    class="action-btn secondary"
                    onclick={stopSelectedGraph}
                >
                    <Square size={16} />
                    Stop
                </button>
                <button type="button" class="action-btn secondary" onclick={runValidation}>
                    <ScanSearch size={16} />
                    Validate
                </button>
                <button
                    type="button"
                    class="action-btn secondary"
                    onclick={() => (paletteOpen = true)}
                    title="Add a node (⌘K / Ctrl+K)"
                >
                    <Plus size={16} />
                    Add Node
                </button>
                <button
                    type="button"
                    class="action-btn secondary"
                    onclick={createCompositeFromSelection}
                    disabled={selectedNodeIds.size === 0}
                    title="Group the selected nodes into a reusable composite"
                >
                    <Package size={16} />
                    Group
                </button>
                {#if selectedIsComposite}
                    <button
                        type="button"
                        class="action-btn secondary"
                        onclick={() => openCompositeInternals(selectedIsComposite)}
                        title="View the nodes inside this composite"
                    >
                        <Eye size={16} />
                        View internals
                    </button>
                    <button
                        type="button"
                        class="action-btn secondary"
                        onclick={ungroupSelectedComposite}
                        title="Expand this composite back into its nodes"
                    >
                        <Ungroup size={16} />
                        Ungroup
                    </button>
                {/if}
                <button type="button" class="action-btn" onclick={saveDraftGraph}>
                    <Save size={16} />
                    Save
                </button>
            </div>
        </div>

        <div class="graph-workspace">
            <div
                bind:this={canvasElement}
                class="graph-canvas"
                role="application"
                tabindex="0"
                aria-label="Stream graph canvas"
                oncontextmenu={openContextMenu}
                onmousedown={startPan}
                onwheel={handleCanvasWheel}
            >
                <div class="canvas-grid" oncontextmenu={openContextMenu}></div>
                <svg class="graph-edges" aria-hidden="true">
                    <g
                        transform={`translate(${draftGraph.ui?.viewport?.x ?? 0}, ${
                            draftGraph.ui?.viewport?.y ?? 0
                        }) scale(${draftGraph.ui?.viewport?.zoom ?? 1})`}
                    >
                    {#each draftGraph.edges as edge}
                        {@const sourceNode =
                            draftGraph.nodes.find(
                                (node) => node.id === edge.source_node_id,
                            )}
                        {@const targetNode =
                            draftGraph.nodes.find(
                                (node) => node.id === edge.target_node_id,
                            )}
                        {#if sourceNode && targetNode}
                            {@const sourcePoint = getPortPosition(
                                sourceNode,
                                edge.source_port,
                                "output",
                            )}
                            {@const targetPoint = getPortPosition(
                                targetNode,
                                edge.target_port,
                                "input",
                            )}
                            <path
                                class:selected={edge.id === selectedEdgeId}
                                class:edge-invalid={edgeDiagnostics(edge.id).length > 0}
                                class:edge-running={selectedGraphStatus?.run_state ===
                                    "running"}
                                class="graph-edge"
                                role="button"
                                tabindex="0"
                                d={`M ${sourcePoint.x} ${sourcePoint.y} C ${
                                    sourcePoint.x + 90
                                } ${sourcePoint.y}, ${targetPoint.x - 90} ${
                                    targetPoint.y
                                }, ${targetPoint.x} ${targetPoint.y}`}
                                onclick={(event) => {
                                    event.stopPropagation();
                                    selectEdge(edge.id);
                                }}
                                onkeydown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        selectEdge(edge.id);
                                    }
                                }}
                            />
                        {/if}
                    {/each}
                    {#if connectionDrag}
                        {@const dragSourceNode = draftGraph.nodes.find(
                            (node) => node.id === connectionDrag?.nodeId,
                        )}
                        {#if dragSourceNode}
                            {@const dragSourcePoint = getPortPosition(
                                dragSourceNode,
                                connectionDrag.portId,
                                "output",
                            )}
                            <path
                                class="graph-edge graph-edge-drag"
                                d={`M ${dragSourcePoint.x} ${dragSourcePoint.y} C ${
                                    dragSourcePoint.x + 90
                                } ${dragSourcePoint.y}, ${
                                    connectionDrag.pointerGraphX - 90
                                } ${connectionDrag.pointerGraphY}, ${
                                    connectionDrag.pointerGraphX
                                } ${connectionDrag.pointerGraphY}`}
                            />
                        {/if}
                    {/if}
                    </g>
                </svg>

                <div
                    class="graph-stage"
                    oncontextmenu={openContextMenu}
                    style={`transform: translate(${draftGraph.ui?.viewport?.x ?? 0}px, ${
                        draftGraph.ui?.viewport?.y ?? 0
                    }px) scale(${draftGraph.ui?.viewport?.zoom ?? 1});`}
                >
                    {#each draftGraph.nodes as node}
                        <StreamGraphNodeCard
                            {node}
                            runtimeStatus={nodeRuntimeStatus(node.id)}
                            selected={selectedNodeIds.has(node.id)}
                            invalid={nodeDiagnostics(node.id).length > 0}
                            {pendingConnection}
                            onSelect={selectNode}
                            onStartDrag={startNodeDrag}
                            onPortClick={handlePortClick}
                            onPortMouseDown={handlePortMouseDown}
                            onExpand={handleNodeExpand}
                        />
                    {/each}
                </div>

                {#if draftGraph.nodes.length === 0}
                    <div class="canvas-empty" oncontextmenu={openContextMenu}>
                        <Activity size={18} />
                        <p>Right-click the board to add a source, transform, viewer, or sink.</p>
                    </div>
                {/if}
            </div>

            <div class="graph-inspector">
                <div class="inspector-section">
                    <p class="eyebrow">Graph</p>
                    <label>
                        <span>Description</span>
                        <textarea
                            rows="3"
                            value={draftGraph.description ?? ""}
                            oninput={(event) =>
                                updateGraphMetadata(
                                    "description",
                                    (event.currentTarget as HTMLTextAreaElement)
                                        .value,
                                )}
                        ></textarea>
                    </label>
                </div>

                <div class="inspector-section">
                    <div class="inspector-section-header">
                        <p class="eyebrow">Inspector</p>
                        <button
                            type="button"
                            class="icon-btn danger"
                            onclick={removeSelectedItem}
                            disabled={!selectedNodeId && !selectedEdgeId}
                            title="Delete selected node/edge (Delete or Backspace)"
                        >
                            <Trash2 size={15} />
                        </button>
                    </div>

                    {#if selectedNode}
                        <label>
                            <span>Label</span>
                            <input
                                value={selectedNode.label}
                                oninput={(event) =>
                                    updateSelectedNode((node) => ({
                                        ...node,
                                        label: (
                                            event.currentTarget as HTMLInputElement
                                        ).value,
                                    }))}
                            />
                        </label>

                        {#if selectedSourceNode}
                            <label>
                                <span>Source stream</span>
                                <select
                                    value={selectedSourceNode.stream_id}
                                    onchange={(event) =>
                                        updateSelectedNode((node) =>
                                            node.kind === "stream_source"
                                                ? {
                                                      ...node,
                                                      stream_id: (
                                                          event.currentTarget as HTMLSelectElement
                                                      ).value,
                                                      schema_name:
                                                          availableStreams.find(
                                                              (stream) =>
                                                                  stream.streamId ===
                                                                  (
                                                                      event.currentTarget as HTMLSelectElement
                                                                  ).value,
                                                          )?.schemaName ?? "",
                                                  }
                                                : node,
                                        )}
                                >
                                    {#each availableStreams as stream}
                                        <option value={stream.streamId}>
                                            Stream {stream.streamId} - {stream.schemaName}
                                        </option>
                                    {/each}
                                </select>
                            </label>
                        {/if}

                        {#if selectedTransformNode}
                            <label>
                                <span>Transform</span>
                                <select
                                    value={selectedTransformNode.transform_kind}
                                    onchange={(event) =>
                                        updateSelectedNode((node) => {
                                            if (node.kind !== "transform") {
                                                return node;
                                            }
                                            const capability =
                                                transformCapabilities.find(
                                                    (item) =>
                                                        item.kind ===
                                                        (
                                                            event.currentTarget as HTMLSelectElement
                                                        ).value,
                                                ) ?? transformCapabilities[0];
                                            return {
                                                ...node,
                                                transform_kind: capability.kind,
                                                label: capability.label,
                                                input_mapping_id:
                                                    capability.input_mappings[0]
                                                        ?.id,
                                                config: buildDefaultTransformConfig(
                                                    capability,
                                                ),
                                                output_stream_id: undefined,
                                            };
                                        })}
                                >
                                    {#each transformCapabilities as capability}
                                        <option value={capability.kind}>
                                            {capability.label}
                                        </option>
                                    {/each}
                                </select>
                            </label>

                            <label>
                                <span>Output identifier</span>
                                <input
                                    value={selectedTransformNode.output_identifier ?? ""}
                                    oninput={(event) =>
                                        updateSelectedNode((node) =>
                                            node.kind === "transform"
                                                ? {
                                                      ...node,
                                                      output_identifier:
                                                          sanitizeIdentifier(
                                                              (
                                                                  event.currentTarget as HTMLInputElement
                                                              ).value,
                                                          ),
                                                      output_stream_id:
                                                          undefined,
                                                  }
                                                : node,
                                        )}
                                />
                            </label>

                            {#if selectedNodeCapability}
                                <label>
                                    <span>Input mapping</span>
                                    <select
                                        value={selectedTransformNode.input_mapping_id ??
                                            ""}
                                        onchange={(event) =>
                                            updateSelectedNode((node) =>
                                                node.kind === "transform"
                                                    ? {
                                                          ...node,
                                                          input_mapping_id: (
                                                              event.currentTarget as HTMLSelectElement
                                                          ).value,
                                                      }
                                                    : node,
                                            )}
                                    >
                                        {#each selectedNodeCapability.input_mappings as mapping}
                                            <option value={mapping.id}>
                                                {mapping.label}
                                            </option>
                                        {/each}
                                    </select>
                                </label>

                                <NodeConfigFields
                                    fields={selectedNodeCapability.config_fields}
                                    config={selectedTransformNode.config}
                                    onChange={updateTransformConfigField}
                                />
                            {/if}
                        {/if}

                        {#if selectedCombineNode}
                            <label>
                                <span>Output identifier</span>
                                <input
                                    value={selectedCombineNode.output_identifier ?? ""}
                                    oninput={(event) =>
                                        updateSelectedNode((node) =>
                                            node.kind === "combine"
                                                ? {
                                                      ...node,
                                                      output_identifier:
                                                          sanitizeIdentifier(
                                                              (
                                                                  event.currentTarget as HTMLInputElement
                                                              ).value,
                                                          ),
                                                      output_stream_id:
                                                          undefined,
                                                  }
                                                : node,
                                        )}
                                />
                            </label>
                            <div class="summary-row">
                                <span
                                    >Inputs ({selectedCombineNode.input_port_ids
                                        ?.length ?? 0})</span
                                >
                                <div class="inspector-action-row">
                                    <button
                                        type="button"
                                        class="action-btn secondary"
                                        onclick={removeCombineInputPort}
                                        disabled={(selectedCombineNode
                                            .input_port_ids?.length ?? 0) <= 2}
                                    >
                                        - Remove input
                                    </button>
                                    <button
                                        type="button"
                                        class="action-btn secondary"
                                        onclick={addCombineInputPort}
                                    >
                                        + Add input
                                    </button>
                                </div>
                            </div>
                        {/if}

                        {#if selectedNodeRuntimeStatus}
                            <div class="runtime-card">
                                <div class="summary-row">
                                    <span>Runtime</span>
                                    <strong class={graphRunStateClass(selectedNodeRuntimeStatus.state)}>
                                        {selectedNodeRuntimeStatus.state}
                                    </strong>
                                </div>
                                {#if selectedNodeRuntimeStatus.output_stream_id}
                                    <div class="summary-row">
                                        <span>Resolved stream</span>
                                        <strong>{selectedNodeRuntimeStatus.output_stream_id}</strong>
                                    </div>
                                {/if}
                                {#if selectedNodeRuntimeStatus.worker_id}
                                    <div class="summary-row">
                                        <span>Worker</span>
                                        <strong>{selectedNodeRuntimeStatus.worker_id}</strong>
                                    </div>
                                {/if}
                                {#if selectedNodeRuntimeStatus.message}
                                    <p class="muted-text">
                                        {selectedNodeRuntimeStatus.message}
                                    </p>
                                {/if}
                                {#if selectedNode.kind === "viewer" &&
                                    selectedNodeRuntimeStatus.output_stream_id}
                                    <button
                                        type="button"
                                        class="action-btn secondary inspector-action"
                                        onclick={() =>
                                            openViewerData(selectedNode)}
                                    >
                                        <Monitor size={15} />
                                        Open Live Stream
                                    </button>
                                {/if}
                            </div>
                        {/if}

                        {#if nodeDiagnostics(selectedNode.id).length > 0}
                            <div class="diagnostic-list">
                                {#each nodeDiagnostics(selectedNode.id) as diagnostic}
                                    <div class="diagnostic error">
                                        <X size={14} />
                                        <span>{diagnostic.message}</span>
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    {:else if selectedEdgeId}
                        <p class="muted-text">Edge {selectedEdgeId}</p>
                        {#if edgeDiagnostics(selectedEdgeId).length > 0}
                            <div class="diagnostic-list">
                                {#each edgeDiagnostics(selectedEdgeId) as diagnostic}
                                    <div class="diagnostic error">
                                        <X size={14} />
                                        <span>{diagnostic.message}</span>
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    {:else}
                        <p class="muted-text">
                            Select a node or edge to inspect it.
                        </p>
                    {/if}
                </div>

                <div class="inspector-section">
                    <p class="eyebrow">Diagnostics</p>
                    {#if graphValidationCount === 0}
                        <div class="diagnostic success">
                            <Check size={14} />
                            <span>No validation issues yet.</span>
                        </div>
                    {/if}
                    {#each latestGraphDiagnostics as diagnostic}
                        <div class="diagnostic error">
                            <X size={14} />
                            <span>{diagnostic.message}</span>
                        </div>
                    {/each}
                    {#each elementDiagnostics as { label, diagnostic }}
                        <div class="diagnostic error">
                            <X size={14} />
                            <span><strong>{label}:</strong> {diagnostic.message}</span>
                        </div>
                    {/each}
                </div>

                {#if runtimeIssues.length > 0}
                    <div class="inspector-section">
                        <p class="eyebrow">Run status</p>
                        {#each runtimeIssues as { label, message }}
                            <div class="diagnostic error">
                                <X size={14} />
                                <span><strong>{label}:</strong> {message}</span>
                            </div>
                        {/each}
                    </div>
                {/if}

                <div class="inspector-section">
                    <p class="eyebrow">Generated JSON</p>
                    <pre>{graphJsonPreview}</pre>
                </div>
            </div>
        </div>
    </div>

    {#if contextMenu.open}
        <div
            class="context-menu"
            role="menu"
            style={`left:${contextMenu.x}px; top:${contextMenu.y}px;`}
            onmousedown={(event) => event.stopPropagation()}
        >
            <div class="context-group">
                <span class="context-title">Streams</span>
                {#each availableStreams as stream}
                    <button
                        type="button"
                        class="context-item"
                        onclick={() => addSourceNode(stream.streamId)}
                    >
                        <span>Stream {stream.streamId}</span>
                        <small>{stream.schemaName}</small>
                    </button>
                {/each}
            </div>
            <div class="context-group">
                <span class="context-title">Transforms</span>
                {#each transformCapabilities as capability}
                    <button
                        type="button"
                        class="context-item"
                        onclick={() => addTransformNode(capability.kind)}
                    >
                        <span>{capability.label}</span>
                        <small>{capability.kind}</small>
                    </button>
                {/each}
            </div>
            <div class="context-group">
                <span class="context-title">Utility</span>
                {#each utilityCatalog as entry}
                    <button
                        type="button"
                        class="context-item"
                        onclick={() => addCatalogNode(entry)}
                    >
                        <span>{entry.label}</span>
                        <small>{entry.description}</small>
                    </button>
                {/each}
            </div>
            {#if compositeTemplates.length > 0}
                <div class="context-group">
                    <span class="context-title">Composites</span>
                    {#each compositeTemplates as template}
                        <button
                            type="button"
                            class="context-item"
                            onclick={() => addCompositeInstance(template)}
                        >
                            <span>{template.label}</span>
                            <small>{template.nodes.length} nodes</small>
                        </button>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}

    <input
        bind:this={compositeFileInput}
        type="file"
        accept="application/json,.json"
        class="hidden-file-input"
        onchange={handleCompositeFileChange}
    />
</div>

{#if expandedComposite}
    {@const layout = compositeInternalsLayout(expandedComposite)}
    <div
        class="composite-internals-overlay"
        role="presentation"
        onclick={closeCompositeInternals}
        onkeydown={(event) => {
            if (event.key === "Escape") {
                closeCompositeInternals();
            }
        }}
    >
        <div
            class="composite-internals-panel"
            role="dialog"
            tabindex="-1"
            aria-label={`${expandedComposite.label} internals`}
            onclick={(event) => event.stopPropagation()}
        >
            <div class="composite-internals-header">
                <div>
                    <p class="eyebrow">Composite internals</p>
                    <h3>{expandedComposite.label}</h3>
                </div>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={closeCompositeInternals}
                >
                    <X size={16} />
                </button>
            </div>
            <div class="composite-internals-canvas">
                <div
                    class="composite-internals-stage"
                    style={`width:${layout.width}px; height:${layout.height}px;`}
                >
                    <svg
                        class="composite-internals-edges"
                        width={layout.width}
                        height={layout.height}
                        aria-hidden="true"
                    >
                        {#each expandedComposite.edges as edge}
                            {@const sourceNode = layout.nodes.find(
                                (node) => node.id === edge.source_node_id,
                            )}
                            {@const targetNode = layout.nodes.find(
                                (node) => node.id === edge.target_node_id,
                            )}
                            {#if sourceNode && targetNode}
                                {@const sourcePoint = getPortPosition(
                                    sourceNode,
                                    edge.source_port,
                                    "output",
                                )}
                                {@const targetPoint = getPortPosition(
                                    targetNode,
                                    edge.target_port,
                                    "input",
                                )}
                                <path
                                    class="graph-edge"
                                    d={`M ${sourcePoint.x} ${sourcePoint.y} C ${
                                        sourcePoint.x + 90
                                    } ${sourcePoint.y}, ${
                                        targetPoint.x - 90
                                    } ${targetPoint.y}, ${targetPoint.x} ${
                                        targetPoint.y
                                    }`}
                                />
                            {/if}
                        {/each}
                    </svg>
                    {#each layout.nodes as node}
                        <StreamGraphNodeCard
                            {node}
                            runtimeStatus={null}
                            selected={false}
                            invalid={false}
                            pendingConnection={null}
                            onSelect={() => {}}
                            onStartDrag={() => {}}
                            onPortClick={() => {}}
                        />
                    {/each}
                </div>
            </div>
            <div class="composite-internals-footer">
                <span>{expandedComposite.inputs.length} inputs</span>
                <span>{expandedComposite.outputs.length} outputs</span>
                <span>{expandedComposite.nodes.length} nodes</span>
                <span>{expandedComposite.edges.length} internal edges</span>
            </div>
        </div>
    </div>
{/if}

{#if expandedViewerNodeId && expandedViewerStreamId}
    <div
        class="viewer-data-overlay"
        role="presentation"
        onclick={closeViewerData}
        onkeydown={(event) => {
            if (event.key === "Escape") {
                closeViewerData();
            }
        }}
    >
        <div
            class="viewer-data-panel"
            role="dialog"
            tabindex="-1"
            aria-label={`Stream ${expandedViewerStreamId} live data`}
            onclick={(event) => event.stopPropagation()}
        >
            <div class="viewer-data-header">
                <div>
                    <p class="eyebrow">Live data</p>
                    <h3>Stream {expandedViewerStreamId}</h3>
                </div>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={closeViewerData}
                >
                    <X size={16} />
                </button>
            </div>
            <div class="viewer-data-body">
                {#if liveRenderer === "muse"}
                    {#if liveLatestMuseSample}
                        <MuseViewer
                            sample={liveLatestMuseSample}
                            {formatNumber}
                        />
                    {:else}
                        <p class="muted-text">Waiting for data…</p>
                    {/if}
                {:else if liveRenderer === "classification"}
                    <ClassificationViewer
                        samples={liveEmgSamples}
                        {formatNumber}
                    />
                {:else if liveRenderer === "feature_vector"}
                    <FeatureVectorViewer
                        samples={liveEmgSamples}
                        {formatNumber}
                    />
                {:else if liveRenderer === "channel_frame"}
                    {#if liveEmgSamples.length > 0}
                        <ChannelFrameViewer samples={liveEmgSamples} {formatNumber} />
                    {:else}
                        <p class="muted-text">Waiting for data…</p>
                    {/if}
                {:else if livePrimaryDescriptor}
                    <SchemaDescriptorInspector
                        descriptor={livePrimaryDescriptor}
                        recordValue={liveDescriptorRecordValue}
                    />
                {:else}
                    <p class="muted-text">Waiting for data on this stream…</p>
                {/if}
            </div>
            <div class="viewer-data-footer">
                <button
                    type="button"
                    class="action-btn secondary"
                    onclick={() => inspectStream(String(expandedViewerStreamId))}
                >
                    <Monitor size={14} />
                    Open in Stream Viewer
                </button>
            </div>
        </div>
    </div>
{/if}

<Command.Dialog bind:open={paletteOpen}>
    <Command.Input placeholder="Add a node — search streams, transforms, composites…" />
    <Command.List>
        <Command.Empty>No matching nodes.</Command.Empty>
        {#if utilityCatalog.length > 0}
            <Command.Group heading="Utility">
                {#each utilityCatalog as entry}
                    {@const Icon = utilityIcon(entry.kind)}
                    <Command.Item
                        value={`${entry.node_type} ${entry.label} ${entry.description}`}
                        onSelect={() =>
                            runPaletteAction(() => addCatalogNode(entry))}
                    >
                        <Icon size={16} />
                        <span>{entry.label}</span>
                    </Command.Item>
                {/each}
            </Command.Group>
        {/if}
        {#if transformCapabilities.length > 0}
            <Command.Group heading="Transforms">
                {#each transformCapabilities as capability}
                    <Command.Item
                        value={`transform ${capability.label} ${capability.kind}`}
                        onSelect={() =>
                            runPaletteAction(() =>
                                addTransformNode(capability.kind),
                            )}
                    >
                        <GitBranch size={16} />
                        <span>{capability.label}</span>
                    </Command.Item>
                {/each}
            </Command.Group>
        {/if}
        {#if availableStreams.length > 0}
            <Command.Group heading="Streams">
                {#each availableStreams as stream}
                    <Command.Item
                        value={`stream ${stream.streamId} ${stream.schemaName}`}
                        onSelect={() =>
                            runPaletteAction(() =>
                                addSourceNode(stream.streamId),
                            )}
                    >
                        <CircleDot size={16} />
                        <span>Stream {stream.streamId}</span>
                    </Command.Item>
                {/each}
            </Command.Group>
        {/if}
        {#if compositeTemplates.length > 0}
            <Command.Group heading="Composites">
                {#each compositeTemplates as template}
                    <Command.Item
                        value={`composite ${template.label}`}
                        onSelect={() =>
                            runPaletteAction(() =>
                                addCompositeInstance(template),
                            )}
                    >
                        <Package size={16} />
                        <span>{template.label}</span>
                    </Command.Item>
                {/each}
            </Command.Group>
        {/if}
    </Command.List>
</Command.Dialog>

<style>
    .graph-editor {
        position: relative;
        display: grid;
        grid-template-columns: 260px minmax(0, 1fr);
        gap: 1rem;
        min-height: 72vh;
        color: #d6def4;
    }

    .graph-sidebar,
    .graph-inspector,
    .graph-toolbar {
        background: rgba(8, 13, 26, 0.9);
        border: 1px solid rgba(110, 138, 255, 0.18);
        box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
    }

    .graph-sidebar,
    .graph-inspector {
        border-radius: 8px;
    }

    .graph-sidebar {
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .sidebar-header,
    .inspector-section-header,
    .graph-toolbar,
    .summary-row,
    .toolbar-group,
    .toolbar-actions,
    .sidebar-actions {
        display: flex;
        align-items: center;
    }

    .sidebar-header,
    .inspector-section-header,
    .graph-toolbar {
        justify-content: space-between;
    }

    .eyebrow {
        margin: 0 0 0.2rem;
        font-size: 0.72rem;
        text-transform: uppercase;
        color: #7f91c8;
        letter-spacing: 0.04em;
    }

    h3 {
        margin: 0;
        font-size: 1rem;
    }

    .icon-btn,
    .action-btn,
    .graph-list-item,
    .context-item {
        border: 1px solid rgba(114, 142, 255, 0.18);
        background: rgba(20, 28, 48, 0.9);
        color: inherit;
    }

    .icon-btn,
    .action-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.45rem;
        border-radius: 6px;
        cursor: pointer;
    }

    .icon-btn {
        width: 32px;
        height: 32px;
    }

    .icon-btn.danger {
        color: #ff8f8f;
    }

    .graph-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        min-height: 160px;
    }

    .graph-list-item {
        border-radius: 6px;
        padding: 0.7rem 0.8rem;
        text-align: left;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        gap: 0.22rem;
    }

    .graph-list-item.selected {
        border-color: rgba(103, 229, 255, 0.48);
        background: rgba(17, 42, 64, 0.95);
    }

    .graph-list-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }

    .graph-list-title {
        font-weight: 600;
    }

    .run-pill {
        border-radius: 999px;
        padding: 0.1rem 0.5rem;
        font-size: 0.66rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border: 1px solid rgba(114, 142, 255, 0.18);
        color: #9dafdf;
        flex-shrink: 0;
    }

    .run-pill.ok {
        color: #8ef2bf;
        border-color: rgba(142, 242, 191, 0.28);
    }

    .run-pill.error {
        color: #ff8f8f;
        border-color: rgba(255, 143, 143, 0.3);
    }

    :global(.action-btn .spin) {
        animation: spin 0.9s linear infinite;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }

    .graph-list-meta {
        color: #7f91c8;
        font-size: 0.8rem;
    }

    .summary-card {
        border-radius: 6px;
        padding: 0.85rem;
        background: rgba(14, 18, 34, 0.92);
        border: 1px solid rgba(114, 142, 255, 0.12);
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
    }

    .library-group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .library-title {
        color: #9dafdf;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .library-actions {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        max-height: 240px;
        overflow: auto;
    }

    .library-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .composite-row {
        display: flex;
        align-items: stretch;
        gap: 0.4rem;
    }

    .composite-add {
        flex: 1;
        min-width: 0;
    }

    .composite-row-actions {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .composite-row-actions .icon-btn {
        width: 28px;
        height: 28px;
    }

    .hidden-file-input {
        display: none;
    }

    .summary-row {
        justify-content: space-between;
        gap: 1rem;
    }

    .summary-row strong.ok {
        color: #8ef2bf;
    }

    .summary-row strong.error {
        color: #ff8f8f;
    }

    .summary-row strong.muted {
        color: #9dafdf;
    }

    .graph-main {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
    }

    .graph-toolbar {
        border-radius: 8px;
        padding: 0.75rem 0.9rem;
        gap: 1rem;
    }

    .toolbar-group,
    .toolbar-actions,
    .sidebar-actions {
        gap: 0.6rem;
    }

    .graph-title-input,
    .graph-id,
    .dirty-pill {
        border-radius: 999px;
        padding: 0.28rem 0.72rem;
    }

    .graph-title-input {
        min-width: 220px;
        background: rgba(4, 10, 20, 0.9);
        border: 1px solid rgba(114, 142, 255, 0.18);
        color: inherit;
    }

    .graph-id {
        background: rgba(29, 36, 61, 0.9);
        color: #9dafdf;
        font-size: 0.82rem;
    }

    .dirty-pill {
        background: rgba(255, 176, 32, 0.15);
        color: #ffcf85;
        font-size: 0.8rem;
    }

    .action-btn {
        padding: 0.55rem 0.82rem;
        font-weight: 600;
    }

    .action-btn.secondary {
        background: rgba(15, 22, 40, 0.95);
    }

    .graph-workspace {
        min-height: 0;
        display: grid;
        grid-template-columns: minmax(0, 1fr) 360px;
        gap: 1rem;
    }

    .graph-canvas {
        position: relative;
        overflow: hidden;
        border-radius: 8px;
        background:
            radial-gradient(circle at top, rgba(76, 161, 255, 0.12), transparent 45%),
            linear-gradient(180deg, rgba(8, 12, 24, 0.96), rgba(5, 8, 16, 1));
        border: 1px solid rgba(110, 138, 255, 0.16);
        min-height: 720px;
        cursor: grab;
    }

    .graph-canvas:active {
        cursor: grabbing;
    }

    .canvas-grid,
    .graph-edges,
    .graph-stage {
        position: absolute;
        inset: 0;
    }

    .graph-edges {
        /* <svg> is a replaced element — `inset: 0` alone doesn't stretch it the
           way it does the plain divs above, so it falls back to the browser's
           default intrinsic 300x150 size and clips every edge outside that box. */
        width: 100%;
        height: 100%;
    }

    .canvas-grid {
        background-image:
            linear-gradient(rgba(126, 153, 255, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(126, 153, 255, 0.08) 1px, transparent 1px);
        background-size: 36px 36px;
        opacity: 0.65;
    }

    .graph-stage {
        transform-origin: 0 0;
    }

    .graph-edge {
        fill: none;
        stroke: rgba(104, 215, 255, 0.58);
        stroke-width: 3;
        cursor: pointer;
        transition: stroke 0.15s ease, stroke-width 0.15s ease;
    }

    .graph-edge:hover {
        stroke: #89f4ff;
        stroke-width: 4;
    }

    .graph-edge.selected {
        stroke: #89f4ff;
        stroke-width: 4;
        filter: drop-shadow(0 0 4px rgba(137, 244, 255, 0.55));
    }

    .graph-edge.edge-invalid {
        stroke: rgba(255, 121, 121, 0.9);
    }

    .graph-edge.edge-running {
        stroke-dasharray: 6 6;
        animation: edge-flow 0.6s linear infinite;
    }

    .graph-edge.graph-edge-drag {
        stroke: #ffcf85;
        stroke-dasharray: 5 5;
        pointer-events: none;
    }

    @keyframes edge-flow {
        to {
            stroke-dashoffset: -12;
        }
    }

    .context-item,
    .empty-state,
    .canvas-empty,
    .diagnostic {
        display: flex;
        align-items: center;
    }

    .canvas-empty,
    .empty-state {
        justify-content: center;
        gap: 0.55rem;
        color: #8ca0d8;
    }

    .canvas-empty {
        position: absolute;
        inset: 0;
    }

    .graph-inspector {
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        overflow: auto;
    }

    .inspector-section {
        display: flex;
        flex-direction: column;
        gap: 0.65rem;
    }

    label {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        font-size: 0.86rem;
        color: #9dafdf;
    }

    input,
    select,
    textarea,
    pre {
        background: rgba(7, 11, 23, 0.96);
        border: 1px solid rgba(114, 142, 255, 0.14);
        border-radius: 6px;
        color: inherit;
    }

    input,
    select,
    textarea {
        padding: 0.62rem 0.72rem;
    }

    textarea {
        resize: vertical;
        min-height: 70px;
    }

    .config-grid {
        display: grid;
        gap: 0.65rem;
    }

    .runtime-card {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
        padding: 0.75rem;
        border-radius: 6px;
        border: 1px solid rgba(114, 142, 255, 0.12);
        background: rgba(14, 18, 34, 0.92);
    }

    .inspector-action {
        align-self: flex-start;
    }

    .inspector-action-row {
        display: flex;
        gap: 0.4rem;
    }

    .muted-text {
        margin: 0;
        color: #7f91c8;
    }

    .diagnostic-list {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
    }

    .diagnostic {
        gap: 0.45rem;
        border-radius: 6px;
        padding: 0.55rem 0.65rem;
        font-size: 0.84rem;
    }

    .diagnostic.error {
        background: rgba(70, 18, 26, 0.72);
        color: #ffb9b9;
    }

    .diagnostic.success {
        background: rgba(18, 64, 42, 0.72);
        color: #b5f4d0;
    }

    pre {
        margin: 0;
        padding: 0.8rem;
        font-size: 0.74rem;
        overflow: auto;
        max-height: 260px;
        line-height: 1.45;
    }

    .context-menu {
        position: fixed;
        z-index: 40;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.85rem;
        padding: 0.9rem;
        border-radius: 8px;
        background: rgba(7, 11, 22, 0.98);
        border: 1px solid rgba(110, 138, 255, 0.24);
        box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
        max-width: min(80vw, 720px);
        max-height: 70vh;
        overflow: auto;
    }

    .context-group {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
    }

    .context-title {
        color: #7f91c8;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .context-item {
        width: 100%;
        justify-content: space-between;
        text-align: left;
        gap: 1rem;
        padding: 0.65rem 0.72rem;
        border-radius: 6px;
        cursor: pointer;
    }

    .context-item small {
        color: #7f91c8;
    }

    @media (max-width: 1200px) {
        .graph-workspace {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 980px) {
        .graph-editor {
            grid-template-columns: 1fr;
        }

        .graph-canvas {
            min-height: 560px;
        }
    }

    .composite-internals-overlay {
        position: fixed;
        inset: 0;
        z-index: 60;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(3, 6, 14, 0.72);
        padding: 2rem;
        /* This overlay is a sibling of .graph-editor, not a descendant, so
           it doesn't inherit the app's light text color and would otherwise
           fall back to the browser default (near-invisible on this dark
           background). */
        color: #d6def4;
    }

    .composite-internals-panel {
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        width: min(90vw, 1080px);
        max-height: 85vh;
        padding: 1rem;
        border-radius: 10px;
        background: rgba(8, 13, 26, 0.98);
        border: 1px solid rgba(110, 138, 255, 0.24);
        box-shadow: 0 30px 90px rgba(0, 0, 0, 0.5);
    }

    .composite-internals-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .composite-internals-header h3 {
        margin: 0;
    }

    .composite-internals-canvas {
        position: relative;
        overflow: auto;
        border-radius: 8px;
        min-height: 320px;
        max-height: 60vh;
        background:
            radial-gradient(circle at top, rgba(76, 161, 255, 0.1), transparent 45%),
            linear-gradient(180deg, rgba(8, 12, 24, 0.96), rgba(5, 8, 16, 1));
        border: 1px solid rgba(110, 138, 255, 0.16);
    }

    .composite-internals-stage {
        position: relative;
    }

    .composite-internals-edges {
        position: absolute;
        inset: 0;
        pointer-events: none;
    }

    .composite-internals-footer {
        display: flex;
        gap: 1.2rem;
        color: #9dafdf;
        font-size: 0.82rem;
    }

    .viewer-data-overlay {
        position: fixed;
        inset: 0;
        z-index: 60;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(3, 6, 14, 0.72);
        padding: 2rem;
        /* Sibling of .graph-editor, not a descendant — see the matching
           comment on .composite-internals-overlay. */
        color: #d6def4;
    }

    .viewer-data-panel {
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        width: min(90vw, 900px);
        max-height: 85vh;
        padding: 1rem;
        border-radius: 10px;
        background: rgba(8, 13, 26, 0.98);
        border: 1px solid rgba(110, 138, 255, 0.24);
        box-shadow: 0 30px 90px rgba(0, 0, 0, 0.5);
    }

    .viewer-data-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .viewer-data-header h3 {
        margin: 0;
    }

    .viewer-data-body {
        overflow: auto;
        max-height: 60vh;
        border-radius: 8px;
        padding: 0.75rem;
        background:
            radial-gradient(circle at top, rgba(76, 161, 255, 0.1), transparent 45%),
            linear-gradient(180deg, rgba(8, 12, 24, 0.96), rgba(5, 8, 16, 1));
        border: 1px solid rgba(110, 138, 255, 0.16);
    }

    .viewer-data-footer {
        display: flex;
        justify-content: flex-end;
    }
</style>
