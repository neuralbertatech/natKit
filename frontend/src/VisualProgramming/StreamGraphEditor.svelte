<script lang="ts">
    import {
        Activity,
        Archive,
        Cpu,
        SlidersHorizontal,
        Check,
        CircleDot,
        Download,
        Eye,
        GitBranch,
        Monitor,
        Package,
        PanelLeft,
        PanelRight,
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
    import {
        STARTER_TEMPLATES,
        type StarterTemplate,
    } from "./starterTemplates";
    import {
        buildCueScheduleForProtocol,
        scheduleDurationMs,
        activeCueAtElapsedMs,
        buildDefaultSessionId,
        buildSessionMetadataRecordPayload,
        buildSessionLifecycleMarkerPayload,
        buildCueMarkerPayloads,
        type EmgCueEvent,
        type SessionPublishBundleInput,
    } from "../StreamViewer/experiment";
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
        isParamNode,
        ungroupInstance,
        type CompositeTemplate,
        type EditorGraphDefinition,
        type EditorGraphNode,
        type ParamNode,
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
        SessionNodeConfig,
        SessionProtocol,
        StreamGraphSessionNode,
        StreamGraphTrainNode,
        TrainNodeConfig,
        LiveStreamData,
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
        // Phase 7: incremental reactivity — restart a node + downstream after a
        // debounced config edit while the graph is running.
        restartStreamGraphNode: (graphId: string, nodeId: string) => boolean;
        publishSessionBundle: (payload: SessionPublishBundleInput) => boolean;
        // Phase 5: submit a train_validate job via the backend ML proxy, and
        // surface the latest job status + resulting model path for train nodes.
        submitTrainJob: (config: TrainNodeConfig) => void;
        trainJobStatus: string | null;
        trainModelPath: string | null;
        validateStreamGraph: (graph: StreamGraphDefinition) => boolean;
        startStreamGraph: (graphId: string) => boolean;
        stopStreamGraph: (graphId: string) => boolean;
        inspectStream: (streamId: string) => void;
        // Per-stream live buffers (keyed by stream id) so multiple inspectors can
        // be live at once, plus friendly device names per stream.
        liveStreams: Record<string, LiveStreamData>;
        streamDeviceNames: Record<string, string>;
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
        restartStreamGraphNode,
        publishSessionBundle,
        submitTrainJob,
        trainJobStatus,
        trainModelPath,
        validateStreamGraph,
        startStreamGraph,
        stopStreamGraph,
        inspectStream,
        liveStreams,
        streamDeviceNames,
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
    // Floating-panel visibility. The canvas fills the page and these menus float
    // over it; each can be hidden to reclaim canvas space.
    let showSidebar = $state(true);
    let showInspector = $state(true);

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
        // Fall back to the backend-persisted composite tree (Phase 7) so a graph
        // saved elsewhere still reloads with its composites intact — no local
        // copy required. Only the flattened primitives remain otherwise.
        if (backendGraph.editor_metadata) {
            return cloneGraph(
                backendGraph.editor_metadata as EditorGraphDefinition,
            );
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

    const selectedSessionNode = $derived(
        selectedNode?.kind === "session" ? selectedNode : null,
    );

    const selectedTrainNode = $derived(
        selectedNode?.kind === "train" ? selectedNode : null,
    );

    const selectedParamNode = $derived(
        selectedNode && isParamNode(selectedNode) ? selectedNode : null,
    );

    // Transform nodes in the draft (targets a param can drive).
    const transformNodeOptions = $derived(
        draftGraph.nodes.filter(
            (node): node is Extract<EditorGraphNode, { kind: "transform" }> =>
                node.kind === "transform",
        ),
    );

    // Numeric config fields of the selected param's target transform.
    const paramTargetFields = $derived.by(() => {
        const targetId = selectedParamNode?.target_node_id;
        if (!targetId) {
            return [];
        }
        const target = transformNodeOptions.find((node) => node.id === targetId);
        if (!target) {
            return [];
        }
        const capability = transformCapabilities.find(
            (cap) => cap.kind === target.transform_kind,
        );
        return (capability?.config_fields ?? []).filter(
            (field) => field.type === "number",
        );
    });

    const selectedNodeCapability = $derived(
        selectedTransformNode
            ? transformCapabilities.find(
                  (capability) =>
                      capability.kind === selectedTransformNode.transform_kind,
              ) ?? null
            : null,
    );

    // Phase 8 (guided flows): transforms compatible with the selected node's
    // OUTPUT descriptor — the "recommended next" nodes a user can add in one
    // click, so a pipeline builds itself from what fits.
    const selectedNodeOutputDescriptor = $derived(
        getOutputDescriptorForNode(selectedNode ?? undefined, availableStreams),
    );
    const recommendedNextTransforms = $derived(
        selectedNodeOutputDescriptor
            ? transformCapabilities.filter(
                  (capability) =>
                      findCompatibleTransformInputMappingId(
                          selectedNodeOutputDescriptor,
                          capability,
                      ) !== undefined,
              )
            : [],
    );

    // Phase 8 (typed connection feedback): a transient note when a just-made
    // connection looks descriptor-incompatible.
    let connectionMessage = $state<string | null>(null);

    // Add a recommended transform downstream of the selected node and wire it up.
    function addRecommendedTransform(kind: string) {
        if (!selectedNode) {
            return;
        }
        const capability = transformCapabilities.find(
            (item) => item.kind === kind,
        );
        if (!capability) {
            return;
        }
        const source = selectedNode;
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `transform/${sanitizeIdentifier(kind)}-${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "transform",
            label: capability.label,
            position: {
                x: source.position.x + 260,
                y: source.position.y,
            },
            transform_kind: kind,
            input_mapping_id: capability.input_mappings[0]?.id,
            config: buildDefaultTransformConfig(capability),
            output_identifier: sanitizeIdentifier(
                `${draftGraph.graph_id}-${kind}-${Date.now()}`,
            ),
            input_port_ids: ["input"],
            output_port_ids: ["output"],
        });
        nextGraph.edges.push({
            id: `edge-${Date.now()}`,
            source_node_id: source.id,
            source_port: source.output_port_ids?.[0] ?? "output",
            target_node_id: nodeId,
            target_port: "input",
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        markDraftChanged(nextGraph);
    }

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

    // Phase 8: load a starter preset as a new board, binding its source to the
    // first available stream (the user can rebind in the inspector).
    function loadStarterTemplate(template: StarterTemplate) {
        if (graphDirty) {
            const shouldDiscard = window.confirm("Discard unsaved graph edits?");
            if (!shouldDiscard) {
                return;
            }
        }
        const firstStreamId = availableStreams[0]?.streamId ?? null;
        draftGraph = template.build(firstStreamId);
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
            inline_graph: false,
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
        } else if (entry.kind === "session") {
            addSessionNode(position);
        } else if (entry.kind === "train") {
            addTrainNode(position);
        }
    }

    function buildDefaultTrainConfig(): TrainNodeConfig {
        return {
            families: ["lda"],
            train_runs: [],
            eval_runs: [],
            selected_fields: [],
            window_ms: 200,
            hop_ms: 50,
            vote_windows: 5,
            confidence_threshold: 0.6,
            min_hold_windows: 2,
            rest_gesture: "rest",
            active_gesture: "fist",
        };
    }

    function addTrainNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `train/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "train",
            label: "Train",
            position: { ...position },
            config: buildDefaultTrainConfig(),
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    // A blank generic protocol — deliberately NOT the EMG gesture defaults, to
    // keep the session node sensor-agnostic. The user authors classes/timing in
    // the inspector. (Phase 4.)
    function buildDefaultSessionConfig(): SessionNodeConfig {
        return {
            protocol: {
                protocol_id: "session",
                label: "New session",
                classes: ["class_a", "class_b"],
                rest_class: "rest",
                repetitions: 3,
                hold_s: 3,
                rest_s: 2,
                lead_in_s: 3,
                tail_rest_s: 2,
                seed: 1,
            },
            participant_id: "",
            notes: "",
        };
    }

    // Starts with 2 input ports (record two sensors); more can be wired up.
    function addSessionNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `session/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "session",
            label: "Session",
            position: { ...position },
            input_port_ids: ["in1", "in2"],
            config: buildDefaultSessionConfig(),
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    // Param nodes are editor-only (Phase 7, part C): dropped by flattenGraph, so
    // they're not in the backend catalog and get a fixed palette entry here.
    function addParamNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `param/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "param",
            label: "Param",
            position: { ...position },
            output_port_ids: ["value"],
            value: 20,
            min: 0,
            max: 100,
            step: 1,
        } as ParamNode);
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    function utilityIcon(kind: string) {
        if (kind === "viewer") return Monitor;
        if (kind === "sink") return Archive;
        if (kind === "session") return CircleDot;
        if (kind === "train") return Cpu;
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
            const compatibleMapping = findCompatibleTransformInputMappingId(
                sourceDescriptor,
                capability,
            );
            // Typed connection feedback (Phase 8): warn if the upstream output
            // doesn't match any of this transform's input mappings. Non-blocking
            // — the descriptor may still be arriving — but flagged clearly.
            if (sourceDescriptor && !compatibleMapping) {
                connectionMessage = `⚠ ${sourceNode?.label ?? "upstream"} output may not be compatible with ${capability.label}.`;
            } else {
                connectionMessage = null;
            }
            return {
                ...node,
                input_mapping_id:
                    compatibleMapping ?? node.input_mapping_id,
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
            // Composite + param nodes are editor-only; `update` only handles the
            // primitive StreamGraphNode kinds.
            if (
                node.id !== selectedNodeId ||
                node.kind === "composite" ||
                node.kind === "param"
            ) {
                return node;
            }
            return update(node);
        });
        markDraftChanged(nextGraph);
    }

    // --- Param nodes (Phase 7, part C) --------------------------------------
    // A param's value is written into the bound transform's config; while the
    // graph runs, the change drives the same debounced incremental restart.
    function applyParamValue(param: ParamNode, value: number) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (node.id === param.id && node.kind === "param") {
                node.value = value;
            }
            if (
                param.target_node_id &&
                param.target_field &&
                node.id === param.target_node_id &&
                node.kind === "transform"
            ) {
                node.config = {
                    ...node.config,
                    [param.target_field]: value,
                };
            }
        }
        markDraftChanged(nextGraph);
        if (param.target_node_id) {
            scheduleReactiveRestart(param.target_node_id);
        }
    }

    function updateParamBinding(patch: Partial<ParamNode>) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (node.id === selectedNodeId && node.kind === "param") {
                Object.assign(node, patch);
            }
        }
        markDraftChanged(nextGraph);
    }

    function updateSessionProtocol(patch: Partial<SessionProtocol>) {
        updateSelectedNode((node) => {
            if (node.kind !== "session") {
                return node;
            }
            return {
                ...node,
                config: {
                    ...node.config,
                    protocol: { ...node.config.protocol, ...patch },
                },
            };
        });
    }

    function updateSessionMeta(
        patch: Partial<Pick<SessionNodeConfig, "participant_id" | "notes">>,
    ) {
        updateSelectedNode((node) => {
            if (node.kind !== "session") {
                return node;
            }
            return { ...node, config: { ...node.config, ...patch } };
        });
    }

    // Parse the comma-separated class editor into a clean vocabulary.
    function parseClassList(raw: string): string[] {
        return raw
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function updateTrainConfig(patch: Partial<TrainNodeConfig>) {
        updateSelectedNode((node) => {
            if (node.kind !== "train") {
                return node;
            }
            return { ...node, config: { ...node.config, ...patch } };
        });
    }

    const selectedSessionSummary = $derived.by(() => {
        if (!selectedSessionNode) {
            return null;
        }
        const schedule = buildCueScheduleForProtocol(
            selectedSessionNode.config.protocol,
        );
        return {
            holdCues: schedule.filter((cue) => cue.phase === "hold").length,
            durationS: Math.round(scheduleDurationMs(schedule) / 1000),
        };
    });

    // --- Session recording (Phase 4, slice C) -------------------------------
    // Recording is client-side: run the protocol cue timeline and publish the
    // session bundle (metadata + lifecycle + cue markers) via the backend under
    // one session_id spanning every recorded upstream stream. The raw sensor
    // data is already in Kafka (the source/transform streams); the session emits
    // the marker timeline that labels and delimits the runs.
    interface SessionRecordingState {
        nodeId: string;
        sessionId: string;
        protocolId: string;
        participantId: string;
        notes: string;
        schedule: EmgCueEvent[];
        durationMs: number;
        streamIds: string[];
        startedAtEpochMs: number;
        startedAtUs: number;
        elapsedMs: number;
    }
    let sessionRecording = $state<SessionRecordingState | null>(null);
    let sessionRecordTimer: ReturnType<typeof setInterval> | null = null;
    let sessionRecordMessage = $state<string | null>(null);

    const activeSessionCue = $derived(
        sessionRecording
            ? activeCueAtElapsedMs(
                  sessionRecording.schedule,
                  sessionRecording.elapsedMs,
              )
            : null,
    );

    // Resolve the concrete stream ids feeding a session node: stream_source
    // inputs contribute their stream_id, transform/combine inputs their resolved
    // runtime output_stream_id.
    function resolveSessionInputStreamIds(
        node: StreamGraphSessionNode,
    ): string[] {
        const ids: string[] = [];
        for (const edge of draftGraph.edges) {
            if (edge.target_node_id !== node.id) {
                continue;
            }
            const src = draftGraph.nodes.find(
                (candidate) => candidate.id === edge.source_node_id,
            );
            if (!src) {
                continue;
            }
            if (src.kind === "stream_source") {
                if (src.stream_id) {
                    ids.push(String(src.stream_id));
                }
            } else {
                const rt = nodeRuntimeStatus(src.id);
                if (rt?.output_stream_id) {
                    ids.push(String(rt.output_stream_id));
                }
            }
        }
        return Array.from(new Set(ids));
    }

    function startSessionRecording(node: StreamGraphSessionNode) {
        if (sessionRecording) {
            return;
        }
        const protocol = node.config.protocol;
        const schedule = buildCueScheduleForProtocol(protocol);
        if (schedule.length === 0) {
            sessionRecordMessage =
                "Protocol has no cues — add classes and timing first.";
            return;
        }
        const streamIds = resolveSessionInputStreamIds(node);
        if (streamIds.length === 0) {
            sessionRecordMessage =
                "No upstream streams resolved — connect sources and start the graph first.";
            return;
        }
        const sessionId = sanitizeIdentifier(
            buildDefaultSessionId(protocol.protocol_id || "session"),
        );
        const startedAtEpochMs = Date.now();
        const startedAtUs = startedAtEpochMs * 1000;
        const participantId = node.config.participant_id ?? "";
        const notes = node.config.notes ?? "";
        const meta = buildSessionMetadataRecordPayload({
            sessionId,
            purpose: "training",
            participantId,
            protocolId: protocol.protocol_id,
            deviceIds: streamIds,
            tags: streamIds.map((id) => `stream:${id}`),
            notes,
            createdAtUs: startedAtUs,
        });
        publishSessionBundle({
            requestId: `vp-session-start:${startedAtUs}`,
            sessionId,
            metaRecords: [meta],
            markerEvents: [
                buildSessionLifecycleMarkerPayload({
                    sessionId,
                    purpose: "training",
                    participantId,
                    protocolId: protocol.protocol_id,
                    deviceIds: streamIds,
                    event: "start",
                    emittedAtUs: startedAtUs,
                }),
            ],
        });
        sessionRecording = {
            nodeId: node.id,
            sessionId,
            protocolId: protocol.protocol_id,
            participantId,
            notes,
            schedule,
            durationMs: scheduleDurationMs(schedule),
            streamIds,
            startedAtEpochMs,
            startedAtUs,
            elapsedMs: 0,
        };
        sessionRecordMessage = `Recording ${streamIds.length} stream(s) as ${sessionId}…`;
        sessionRecordTimer = setInterval(tickSessionRecording, 100);
    }

    function tickSessionRecording() {
        if (!sessionRecording) {
            return;
        }
        const elapsedMs = Date.now() - sessionRecording.startedAtEpochMs;
        sessionRecording = { ...sessionRecording, elapsedMs };
        if (elapsedMs >= sessionRecording.durationMs) {
            finishSessionRecording(true);
        }
    }

    function finishSessionRecording(completed: boolean) {
        const rec = sessionRecording;
        if (!rec) {
            return;
        }
        if (sessionRecordTimer) {
            clearInterval(sessionRecordTimer);
            sessionRecordTimer = null;
        }
        const endedAtUs = Date.now() * 1000;
        const cueMarkers = buildCueMarkerPayloads({
            sessionId: rec.sessionId,
            cues: rec.schedule,
            sessionStartedAtUs: rec.startedAtUs,
        }).filter((marker) => marker.emitted_at_us <= endedAtUs);
        const meta = buildSessionMetadataRecordPayload({
            sessionId: rec.sessionId,
            purpose: "training",
            participantId: rec.participantId,
            protocolId: rec.protocolId,
            deviceIds: rec.streamIds,
            tags: rec.streamIds.map((id) => `stream:${id}`),
            notes: rec.notes,
            createdAtUs: rec.startedAtUs,
            updatedAtUs: endedAtUs,
        });
        publishSessionBundle({
            requestId: `vp-session-complete:${endedAtUs}`,
            sessionId: rec.sessionId,
            metaRecords: [meta],
            markerEvents: [
                ...cueMarkers,
                buildSessionLifecycleMarkerPayload({
                    sessionId: rec.sessionId,
                    purpose: "training",
                    participantId: rec.participantId,
                    protocolId: rec.protocolId,
                    deviceIds: rec.streamIds,
                    event: "end",
                    emittedAtUs: endedAtUs,
                }),
            ],
        });
        sessionRecordMessage = completed
            ? `Recorded ${rec.sessionId} (${rec.streamIds.length} stream(s)).`
            : `Stopped ${rec.sessionId} early; partial session published.`;
        sessionRecording = null;
    }

    // Phase 7 incremental reactivity: when a transform config changes while the
    // graph is RUNNING, debounce then save the new config and restart only that
    // node's downstream subgraph — no manual stop/start. Debounced so a slider
    // drag doesn't thrash the hot path.
    let reactiveRestartTimer: ReturnType<typeof setTimeout> | null = null;
    function scheduleReactiveRestart(nodeId: string | null) {
        if (!nodeId || selectedGraphStatus?.run_state !== "running") {
            return;
        }
        const graphId = draftGraph.graph_id;
        if (!graphId) {
            return;
        }
        if (reactiveRestartTimer) {
            clearTimeout(reactiveRestartTimer);
        }
        reactiveRestartTimer = setTimeout(() => {
            reactiveRestartTimer = null;
            saveDraftGraph();
            restartStreamGraphNode(graphId, nodeId);
        }, 350);
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
        scheduleReactiveRestart(selectedNodeId);
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
        const editorSnapshot = $state.snapshot(draftGraph) as EditorGraphDefinition;
        saveEditorGraph(editorSnapshot);
        const flattened = flattenedForBackend();
        // Round-trip the composite tree through the backend (Phase 7): attach the
        // unflattened editor graph as opaque metadata, stripping any nested
        // editor_metadata so it doesn't grow on every save.
        const { editor_metadata: _nested, ...editorTree } = editorSnapshot;
        flattened.editor_metadata = editorTree;
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
        if (!nodeRuntimeStatus(node.id)?.output_stream_id) {
            return;
        }
        // Subscription is reconciled by the $effect below (keyed on the expanded
        // node + inline viewers); this just opens the overlay.
        expandedViewerNodeId = node.id;
    }

    function closeViewerData() {
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

    function setInlineViewerGraph(nodeId: string, enabled: boolean) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (node.id === nodeId && node.kind === "viewer") {
                node.inline_graph = enabled;
            }
        }
        markDraftChanged(nextGraph);
        // Subscriptions are reconciled by the effect below — each inline viewer
        // (and the expanded overlay) subscribes its own stream, so any number
        // render live at once.
    }

    // Keep the set of live subscriptions in sync with the streams currently being
    // inspected: every inline-enabled viewer node with a resolved output stream,
    // plus the expanded overlay. Ref-counted on the page side, so two viewers on
    // the same stream share one feed and neither closes the other's.
    const editorSubscribed = new Set<string>();
    $effect(() => {
        const desired = new Set<string>();
        for (const node of draftGraph.nodes) {
            if (node.kind === "viewer" && node.inline_graph) {
                const streamId = nodeRuntimeStatus(node.id)?.output_stream_id;
                if (streamId) {
                    desired.add(String(streamId));
                }
            }
            // Briefly sniff a source stream we don't yet have a name for, so the
            // node can show its device name; once named it drops out of `desired`
            // and is released (the name persists in the cache).
            if (
                node.kind === "stream_source" &&
                node.stream_id &&
                !streamDeviceNames[node.stream_id]
            ) {
                desired.add(node.stream_id);
            }
        }
        if (expandedViewerStreamId) {
            desired.add(String(expandedViewerStreamId));
        }
        for (const streamId of desired) {
            if (!editorSubscribed.has(streamId)) {
                editorSubscribed.add(streamId);
                subscribeToStream(streamId);
            }
        }
        for (const streamId of [...editorSubscribed]) {
            if (!desired.has(streamId)) {
                editorSubscribed.delete(streamId);
                unsubscribeFromStream(streamId);
            }
        }
    });

    // --- Port anchors + node resize ------------------------------------------
    // Each node reports its port dots' offsets from its top-left (unscaled graph
    // px); an edge endpoint is then node.position + offset, so wires stay glued
    // to the real dots at any node size, pan, or zoom. Falls back to the
    // constant-based layout until the first measurement lands.
    let portOffsets = $state<Record<string, { dx: number; dy: number }>>({});

    function portKey(nodeId: string, side: string, portId: string): string {
        return `${nodeId}::${side}::${portId}`;
    }

    function handlePortLayout(
        nodeId: string,
        anchors: {
            portId: string;
            side: "input" | "output";
            dx: number;
            dy: number;
        }[],
    ) {
        const next = { ...portOffsets };
        for (const key of Object.keys(next)) {
            if (key.startsWith(`${nodeId}::`)) {
                delete next[key];
            }
        }
        for (const anchor of anchors) {
            next[portKey(nodeId, anchor.side, anchor.portId)] = {
                dx: anchor.dx,
                dy: anchor.dy,
            };
        }
        portOffsets = next;
    }

    function getPortPoint(
        node: EditorGraphNode,
        portId: string,
        side: "input" | "output",
    ): { x: number; y: number } {
        const offset = portOffsets[portKey(node.id, side, portId)];
        if (offset) {
            return {
                x: node.position.x + offset.dx,
                y: node.position.y + offset.dy,
            };
        }
        return getPortPosition(node, portId, side);
    }

    function handleNodeResize(nodeId: string, width: number, height: number) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (node.id === nodeId) {
                node.width = width;
                node.height = height;
            }
        }
        markDraftChanged(nextGraph);
    }

    onDestroy(() => {
        for (const streamId of editorSubscribed) {
            unsubscribeFromStream(streamId);
        }
        editorSubscribed.clear();
        if (sessionRecordTimer) {
            clearInterval(sessionRecordTimer);
            sessionRecordTimer = null;
        }
        if (reactiveRestartTimer) {
            clearTimeout(reactiveRestartTimer);
            reactiveRestartTimer = null;
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
    // Resolve everything a renderer needs for ONE stream id from the per-stream
    // buffers, so any number of viewers render independently.
    function liveStreamView(streamId: string | null | undefined) {
        const data = streamId ? liveStreams[streamId] : undefined;
        const emgSamples = data?.emgSamples ?? [];
        const latestMuse = data?.museSamples.at(-1);
        const latestEmg = emgSamples.at(-1);
        const descriptor = streamId
            ? availableStreams.find((option) => option.streamId === streamId)
                  ?.descriptor
            : undefined;
        const hint = latestEmg
            ? {
                  n_channels: latestEmg.n_channels,
                  samples_per_channel: latestEmg.samples_per_channel,
                  channel_labels: latestEmg.channel_labels,
              }
            : undefined;
        return {
            subscribed: data != null,
            emgSamples,
            latestMuse,
            descriptor,
            renderer: chooseViewerRenderer(descriptor, hint),
            recordValue: latestEmg ?? latestMuse ?? data?.imuSamples.at(-1),
        };
    }

</script>

<svelte:window
    onmousemove={handlePointerMove}
    onmouseup={endPointerInteraction}
    onmousedown={handleWindowPointerDown}
    onkeydown={handleWindowKeydown}
/>

{#snippet streamRenderer(streamId: string | null, compact: boolean)}
    {@const view = liveStreamView(streamId)}
    {#if !streamId}
        <p class="inline-note">Start the graph to see live data.</p>
    {:else if !view.subscribed}
        <p class="inline-note">Connecting…</p>
    {:else if view.renderer === "muse"}
        {#if view.latestMuse}
            <MuseViewer sample={view.latestMuse} {formatNumber} />
        {:else}
            <p class="inline-note">Waiting for data…</p>
        {/if}
    {:else if view.renderer === "classification"}
        <ClassificationViewer samples={view.emgSamples} {formatNumber} />
    {:else if view.renderer === "feature_vector"}
        <FeatureVectorViewer samples={view.emgSamples} {formatNumber} />
    {:else if view.renderer === "channel_frame"}
        {#if view.emgSamples.length > 0}
            <ChannelFrameViewer samples={view.emgSamples} {formatNumber} {compact} />
        {:else}
            <p class="inline-note">Waiting for data…</p>
        {/if}
    {:else if view.descriptor}
        <SchemaDescriptorInspector
            descriptor={view.descriptor}
            recordValue={view.recordValue}
        />
    {:else}
        <p class="inline-note">Waiting for data on this stream…</p>
    {/if}
{/snippet}

{#snippet inlineViewerChart(node: EditorGraphNode)}
    {@const streamId = nodeRuntimeStatus(node.id)?.output_stream_id}
    {@render streamRenderer(streamId ? String(streamId) : null, true)}
{/snippet}

<div class="graph-editor">
    <div class="graph-sidebar" class:panel-hidden={!showSidebar}>
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

        <div class="library-group">
            <span class="library-title">Starter templates</span>
            <div class="library-actions">
                {#each STARTER_TEMPLATES as template}
                    <button
                        type="button"
                        class="graph-list-item"
                        title={template.description}
                        onclick={() => loadStarterTemplate(template)}
                    >
                        <span class="graph-list-title">{template.label}</span>
                        <span class="graph-list-meta">{template.description}</span>
                    </button>
                {/each}
            </div>
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
                    <button
                        type="button"
                        class="graph-list-item"
                        title="A slider whose value drives a downstream transform's config field, live."
                        onclick={() => addParamNode()}
                    >
                        <span class="graph-list-title">Param</span>
                        <span class="graph-list-meta"
                            >Slider bound to a transform config field</span
                        >
                    </button>
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
                <button
                    type="button"
                    class="icon-btn"
                    class:active={showSidebar}
                    onclick={() => (showSidebar = !showSidebar)}
                    title={showSidebar ? "Hide boards & palette" : "Show boards & palette"}
                    aria-pressed={showSidebar}
                >
                    <PanelLeft size={16} />
                </button>
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
                <button
                    type="button"
                    class="icon-btn"
                    class:active={showInspector}
                    onclick={() => (showInspector = !showInspector)}
                    title={showInspector ? "Hide inspector" : "Show inspector"}
                    aria-pressed={showInspector}
                >
                    <PanelRight size={16} />
                </button>
            </div>
        </div>

        <div class="graph-workspace">
            {#if connectionMessage}
                <div class="connection-note">
                    <span>{connectionMessage}</span>
                    <button
                        type="button"
                        class="connection-note-dismiss"
                        onclick={() => (connectionMessage = null)}
                        aria-label="Dismiss">×</button
                    >
                </div>
            {/if}
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
                            {@const sourcePoint = getPortPoint(
                                sourceNode,
                                edge.source_port,
                                "output",
                            )}
                            {@const targetPoint = getPortPoint(
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
                            {@const dragSourcePoint = getPortPoint(
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
                            {inlineViewerChart}
                            {streamDeviceNames}
                            onPortLayout={handlePortLayout}
                            onResize={handleNodeResize}
                            onToggleInlineGraph={setInlineViewerGraph}
                            onSelect={selectNode}
                            onStartDrag={startNodeDrag}
                            onPortClick={handlePortClick}
                            onPortMouseDown={handlePortMouseDown}
                            onExpand={handleNodeExpand}
                            onParamValueChange={(nodeId, value) => {
                                const paramNode = draftGraph.nodes.find(
                                    (candidate) =>
                                        candidate.id === nodeId &&
                                        candidate.kind === "param",
                                );
                                if (paramNode && paramNode.kind === "param") {
                                    applyParamValue(paramNode, value);
                                }
                            }}
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

            <div class="graph-inspector" class:panel-hidden={!showInspector}>
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
                            {#if selectedNodeCapability}
                                <p class="node-doc">
                                    {selectedNodeCapability.description}
                                </p>
                            {/if}
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

                        {#if selectedSessionNode}
                            {@const protocol = selectedSessionNode.config.protocol}
                            <label>
                                <span>Protocol name</span>
                                <input
                                    value={protocol.label}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            label: (event.currentTarget as HTMLInputElement).value,
                                        })}
                                />
                            </label>
                            <label>
                                <span>Protocol id</span>
                                <input
                                    value={protocol.protocol_id}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            protocol_id: sanitizeIdentifier(
                                                (event.currentTarget as HTMLInputElement).value,
                                            ),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Classes (comma-separated labels)</span>
                                <input
                                    value={protocol.classes.join(", ")}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            classes: parseClassList(
                                                (event.currentTarget as HTMLInputElement).value,
                                            ),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Rest / idle class</span>
                                <input
                                    value={protocol.rest_class}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            rest_class: (event.currentTarget as HTMLInputElement).value,
                                        })}
                                />
                            </label>
                            <label>
                                <span>Repetitions</span>
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={protocol.repetitions}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            repetitions: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Hold (s)</span>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.5"
                                    value={protocol.hold_s}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            hold_s: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Rest (s)</span>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.5"
                                    value={protocol.rest_s}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            rest_s: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Lead-in (s)</span>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.5"
                                    value={protocol.lead_in_s}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            lead_in_s: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Tail rest (s)</span>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.5"
                                    value={protocol.tail_rest_s}
                                    oninput={(event) =>
                                        updateSessionProtocol({
                                            tail_rest_s: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Participant id</span>
                                <input
                                    value={selectedSessionNode.config.participant_id ?? ""}
                                    oninput={(event) =>
                                        updateSessionMeta({
                                            participant_id: (event.currentTarget as HTMLInputElement).value,
                                        })}
                                />
                            </label>
                            <label>
                                <span>Notes</span>
                                <input
                                    value={selectedSessionNode.config.notes ?? ""}
                                    oninput={(event) =>
                                        updateSessionMeta({
                                            notes: (event.currentTarget as HTMLInputElement).value,
                                        })}
                                />
                            </label>
                            {#if selectedSessionSummary}
                                <div class="summary-row">
                                    <span>Schedule</span>
                                    <strong
                                        >{selectedSessionSummary.holdCues} cues · ~{selectedSessionSummary.durationS}s</strong
                                    >
                                </div>
                            {/if}
                            <div class="summary-row">
                                <span
                                    >Recording inputs ({selectedSessionNode
                                        .input_port_ids?.length ?? 0})</span
                                >
                            </div>
                            <div class="inspector-action-row">
                                {#if sessionRecording && sessionRecording.nodeId === selectedSessionNode.id}
                                    <button
                                        type="button"
                                        class="action-btn secondary"
                                        onclick={() =>
                                            finishSessionRecording(false)}
                                    >
                                        Stop recording
                                    </button>
                                {:else}
                                    <button
                                        type="button"
                                        class="action-btn"
                                        disabled={sessionRecording !== null}
                                        onclick={() =>
                                            startSessionRecording(
                                                selectedSessionNode,
                                            )}
                                    >
                                        <CircleDot size={15} />
                                        Record session
                                    </button>
                                {/if}
                            </div>
                            {#if sessionRecording && sessionRecording.nodeId === selectedSessionNode.id}
                                <div class="runtime-card">
                                    <div class="summary-row">
                                        <span>Elapsed</span>
                                        <strong
                                            >{(
                                                sessionRecording.elapsedMs / 1000
                                            ).toFixed(1)}s / {(
                                                sessionRecording.durationMs /
                                                1000
                                            ).toFixed(0)}s</strong
                                        >
                                    </div>
                                    {#if activeSessionCue}
                                        <div class="summary-row">
                                            <span>Current cue</span>
                                            <strong
                                                >{activeSessionCue.prompt} · {activeSessionCue.gesture}</strong
                                            >
                                        </div>
                                    {/if}
                                </div>
                            {/if}
                            {#if sessionRecordMessage}
                                <p class="muted-text">{sessionRecordMessage}</p>
                            {/if}
                        {/if}

                        {#if selectedTrainNode}
                            {@const cfg = selectedTrainNode.config}
                            <label>
                                <span>Model families (comma-separated)</span>
                                <input
                                    value={cfg.families.join(", ")}
                                    oninput={(event) =>
                                        updateTrainConfig({
                                            families: parseClassList(
                                                (event.currentTarget as HTMLInputElement).value,
                                            ),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Train runs (session:run, comma-separated)</span>
                                <input
                                    value={cfg.train_runs.join(", ")}
                                    oninput={(event) =>
                                        updateTrainConfig({
                                            train_runs: parseClassList(
                                                (event.currentTarget as HTMLInputElement).value,
                                            ),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Eval runs (session:run, comma-separated)</span>
                                <input
                                    value={cfg.eval_runs.join(", ")}
                                    oninput={(event) =>
                                        updateTrainConfig({
                                            eval_runs: parseClassList(
                                                (event.currentTarget as HTMLInputElement).value,
                                            ),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Window (ms)</span>
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={cfg.window_ms}
                                    oninput={(event) =>
                                        updateTrainConfig({
                                            window_ms: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Hop (ms)</span>
                                <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={cfg.hop_ms}
                                    oninput={(event) =>
                                        updateTrainConfig({
                                            hop_ms: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <div class="inspector-action-row">
                                <button
                                    type="button"
                                    class="action-btn"
                                    disabled={cfg.families.length === 0 ||
                                        cfg.train_runs.length === 0}
                                    onclick={() =>
                                        submitTrainJob(selectedTrainNode.config)}
                                >
                                    <Cpu size={15} />
                                    Submit training job
                                </button>
                            </div>
                            {#if trainJobStatus}
                                <div class="summary-row">
                                    <span>Job</span>
                                    <strong>{trainJobStatus}</strong>
                                </div>
                            {/if}
                            {#if trainModelPath}
                                <div class="summary-row">
                                    <span>Model</span>
                                    <strong>{trainModelPath}</strong>
                                </div>
                                <p class="muted-text">
                                    Paste this path into a classify (lda_classify)
                                    node's model_path to run predictions.
                                </p>
                            {/if}
                        {/if}

                        {#if selectedParamNode}
                            <label>
                                <span>Value</span>
                                <input
                                    type="range"
                                    min={selectedParamNode.min}
                                    max={selectedParamNode.max}
                                    step={selectedParamNode.step}
                                    value={selectedParamNode.value}
                                    oninput={(event) =>
                                        applyParamValue(
                                            selectedParamNode,
                                            Number((event.currentTarget as HTMLInputElement).value),
                                        )}
                                />
                            </label>
                            <div class="summary-row">
                                <span>Current</span>
                                <strong>{selectedParamNode.value}</strong>
                            </div>
                            <label>
                                <span>Target transform</span>
                                <select
                                    value={selectedParamNode.target_node_id ?? ""}
                                    onchange={(event) =>
                                        updateParamBinding({
                                            target_node_id:
                                                (event.currentTarget as HTMLSelectElement).value || undefined,
                                            target_field: undefined,
                                        })}
                                >
                                    <option value="">(none)</option>
                                    {#each transformNodeOptions as t}
                                        <option value={t.id}>{t.label}</option>
                                    {/each}
                                </select>
                            </label>
                            <label>
                                <span>Target config field</span>
                                <select
                                    value={selectedParamNode.target_field ?? ""}
                                    onchange={(event) =>
                                        updateParamBinding({
                                            target_field:
                                                (event.currentTarget as HTMLSelectElement).value || undefined,
                                        })}
                                >
                                    <option value="">(none)</option>
                                    {#each paramTargetFields as field}
                                        <option value={field.id}>{field.label}</option>
                                    {/each}
                                </select>
                            </label>
                            <label>
                                <span>Min</span>
                                <input
                                    type="number"
                                    value={selectedParamNode.min}
                                    oninput={(event) =>
                                        updateParamBinding({
                                            min: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Max</span>
                                <input
                                    type="number"
                                    value={selectedParamNode.max}
                                    oninput={(event) =>
                                        updateParamBinding({
                                            max: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            <label>
                                <span>Step</span>
                                <input
                                    type="number"
                                    value={selectedParamNode.step}
                                    oninput={(event) =>
                                        updateParamBinding({
                                            step: Number((event.currentTarget as HTMLInputElement).value),
                                        })}
                                />
                            </label>
                            {#if selectedParamNode.target_node_id && selectedParamNode.target_field}
                                <p class="muted-text">
                                    Drives {selectedParamNode.target_field} on the
                                    target transform — live while the graph runs.
                                </p>
                            {/if}
                        {/if}

                        {#if recommendedNextTransforms.length > 0}
                            <div class="inspector-section">
                                <p class="eyebrow">Recommended next</p>
                                <div class="library-actions">
                                    {#each recommendedNextTransforms.slice(0, 8) as capability}
                                        <button
                                            type="button"
                                            class="graph-list-item"
                                            title={capability.description}
                                            onclick={() =>
                                                addRecommendedTransform(capability.kind)}
                                        >
                                            <span class="graph-list-title"
                                                >+ {capability.label}</span
                                            >
                                            <span class="graph-list-meta"
                                                >{capability.kind}</span
                                            >
                                        </button>
                                    {/each}
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
                {@render streamRenderer(
                    expandedViewerStreamId ? String(expandedViewerStreamId) : null,
                    false,
                )}
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
                <Command.Item
                    value="param slider input control"
                    onSelect={() => runPaletteAction(() => addParamNode())}
                >
                    <SlidersHorizontal size={16} />
                    <span>Param</span>
                </Command.Item>
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
        display: block;
        height: 100%;
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
        position: absolute;
        top: 72px;
        left: 14px;
        bottom: 14px;
        width: 280px;
        z-index: 15;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        overflow: auto;
        border-radius: 8px;
        transition: transform 0.18s ease, opacity 0.18s ease;
    }

    /* Floating menus slide off-canvas when hidden so the board fills the page. */
    .graph-sidebar.panel-hidden {
        transform: translateX(calc(-100% - 18px));
        opacity: 0;
        pointer-events: none;
    }

    .graph-inspector.panel-hidden {
        transform: translateX(calc(100% + 18px));
        opacity: 0;
        pointer-events: none;
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

    .icon-btn.active {
        background: rgba(76, 161, 255, 0.24);
        border-color: rgba(76, 161, 255, 0.5);
        color: #cfe2ff;
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
        position: absolute;
        inset: 0;
        min-width: 0;
    }

    .graph-toolbar {
        position: absolute;
        top: 14px;
        left: 14px;
        right: 14px;
        z-index: 20;
        border-radius: 8px;
        padding: 0.6rem 0.8rem;
        gap: 1rem;
        flex-wrap: wrap;
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
        position: absolute;
        inset: 0;
        display: block;
    }

    .graph-canvas {
        position: absolute;
        inset: 0;
        overflow: hidden;
        background:
            radial-gradient(circle at top, rgba(76, 161, 255, 0.12), transparent 45%),
            linear-gradient(180deg, rgba(8, 12, 24, 0.96), rgba(5, 8, 16, 1));
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
        position: absolute;
        top: 72px;
        right: 14px;
        bottom: 14px;
        width: 360px;
        z-index: 15;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        overflow: auto;
        border-radius: 8px;
        transition: transform 0.18s ease, opacity 0.18s ease;
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

    /* Phase 8: inline node doc + typed connection feedback */
    .node-doc {
        margin: 0;
        font-size: 0.82rem;
        line-height: 1.4;
        color: #9dafdf;
    }

    .connection-note {
        position: absolute;
        top: 0.6rem;
        left: 50%;
        transform: translateX(-50%);
        z-index: 20;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.4rem 0.7rem;
        border-radius: 8px;
        background: rgba(60, 45, 12, 0.96);
        border: 1px solid rgba(214, 158, 46, 0.5);
        color: #f4d58d;
        font-size: 0.82rem;
        max-width: 80%;
    }

    .connection-note-dismiss {
        border: none;
        background: transparent;
        color: inherit;
        font-size: 1rem;
        line-height: 1;
        cursor: pointer;
    }
</style>
