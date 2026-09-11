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
        FileDown,
        FlaskConical,
        FolderOpen,
        Pencil,
        Network,
        GitBranch,
        Lightbulb,
        Maximize2,
        Monitor,
        Package,
        PanelLeft,
        PanelRight,
        Plus,
        RefreshCw,
        Save,
        ScanSearch,
        Clock,
        SquareDashedMousePointer,
        Square,
        Play,
        Trash2,
        Ungroup,
        Upload,
        UserPlus,
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
    import DeviceHealthPanel from "./DeviceHealthPanel.svelte";
    import { clockFitForStream } from "../StreamViewer/clockFit";
    import ImuViewer from "../StreamViewer/ImuViewer.svelte";
    import ChannelFrameViewer from "../StreamViewer/ChannelFrameViewer.svelte";
    import FeatureVectorViewer from "../StreamViewer/FeatureVectorViewer.svelte";
    import SchemaDescriptorInspector from "../StreamViewer/SchemaDescriptorInspector.svelte";
    import ClassificationViewer from "../StreamViewer/ClassificationViewer.svelte";
    import MarkerViewer from "../StreamViewer/MarkerViewer.svelte";
    import TimelineStrip from "./TimelineStrip.svelte";
    import {
        createLiveContext,
        computeTimeWindow,
        timeToFraction,
        fractionToTime,
        layoutTicks,
        layoutRegions,
        advancePlayhead,
        type TimeContext,
        type PlaybackSpeed,
    } from "./timeContext";
    import type {
        BufferedMarkerEvent,
        StreamTimeMessage,
    } from "../StreamViewer/types";
    import type { RecordedRunSummary } from "../MlPipeline/types";
    import NodeConfigFields from "../StreamViewer/NodeConfigFields.svelte";
    import {
        chooseViewerRenderer,
        MARKER_SCHEMA_NAME,
    } from "../StreamViewer/viewerRegistry";
    import {
        STARTER_TEMPLATES,
        type StarterTemplate,
    } from "./starterTemplates";
    import {
        scheduleDurationMs,
        activeCueAtElapsedMs,
        nextCueAfterElapsedMs,
        buildDefaultSessionId,
        buildSessionMetadataRecordPayload,
        buildSessionLifecycleMarkerPayload,
        buildCueMarkerPayloads,
        type EmgCueEvent,
        type SessionPublishBundleInput,
        FINGER_COUNTING_PROTOCOL,
    } from "../StreamViewer/experiment";
    import {
        isStepProtocol,
        protocolClasses,
        resolveScheduleWaits,
        scheduleForProtocol,
    } from "../StreamViewer/experimentSteps";
    import {
        accuracy_int_to_calibration_status,
        calibration_status_for_accuracies,
        SENSOR_KEYS,
        sensorIsReporting,
        calibration_status_to_color,
        calibration_status_to_string,
        type SensorAccuracies,
    } from "../ImuExperiment/util";
    import {
        SENSOR_POSITION_NAMES,
        ASSIGNABLE_SENSOR_POSITIONS,
        duplicatePositions,
        isAssignedPosition,
        meetsCalibrationMinimum,
        CALIBRATION_MINIMUM,
    } from "../StreamViewer/sensorPositions";
    import StreamGraphNodeCard from "./StreamGraphNode.svelte";
    import ExperimentRunner from "./ExperimentRunner.svelte";
    import ExperimentPanel from "./ExperimentPanel.svelte";
    import ExperimentDesigner from "./ExperimentDesigner.svelte";
    import DialogHost from "./DialogHost.svelte";
    import { askConfirm, askName, showAlert } from "./dialogs.svelte";
    import { resolveSourceView } from "./sourceOnlyView";
    import { streamDisplayName } from "../StreamViewer/streamNames";
    import {
        answerCarriesGroupState,
        controlLabel,
        parseToggleStates,
        resolveControls,
        writeArgsFor,
        type DeviceControl,
    } from "../StreamViewer/deviceControls";
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
        graphRunStateLabel,
        isProvenancePort,
        BOTH_LABEL,
        sanitizeIdentifier,
        visibleConfigFields,
        PROVENANCE_PORT_MODELS,
        PROVENANCE_PORT_MODEL,
        type GraphStreamOption,
    } from "./streamGraph";
    import { resolveAxisEndUs } from "./marbleStrip";
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
        DeviceHealthMessage,
        TransformCapability,
        TransformCapabilityConfigField,
        ChannelActivity,
        NodeCatalogEntry,
        SessionProtocol,
        StreamGraphExperimentNode,
        StreamGraphTrainNode,
        StreamGraphExportNode,
        ExportNodeConfig,
        ExportDownloadResult,
        TrainNodeConfig,
        TrainedModel,
        LiveStreamData,
        OutputChannelTopic,
        ChannelKind,
        Profile,
        Workspace,
        Experiment,
    } from "../StreamViewer/types";
    import {
        channelKindFromTopics,
        markerTopicOfChannel,
        dataTopicOfChannel,
    } from "../StreamViewer/types";

    interface Props {
        availableStreams: GraphStreamOption[];
        transformCapabilities: TransformCapability[];
        nodeCatalog: NodeCatalogEntry[];
        graphDefinitions: StreamGraphDefinition[];
        graphStatuses: Record<string, StreamGraphStatusSummary>;
        // The backend's wall clock at snapshot time, so a lane's heartbeat is
        // compared against the clock that stamped it (TEC-NATKIT-123).
        backendNowUs?: number;
        latestValidation: Record<string, StreamGraphDiagnostic[]>;
        latestEdgeValidation: Record<string, StreamGraphDiagnostic[]>;
        latestGraphDiagnostics: StreamGraphDiagnostic[];
        connectionState: ConnectionState;
        /** The rig's health, or null when nothing has been heard yet. */
        deviceHealth: DeviceHealthMessage | null;
        listStreamGraphs: () => void;
        requestStreamGraphStatus: (graphId: string) => void;
        saveStreamGraph: (graph: StreamGraphDefinition) => boolean;
        // Phase 4: individual profiles (person -> saved classify graph).
        profiles: Profile[];
        listProfiles: () => void;
        saveProfile: (profile: Profile) => boolean;
        deleteProfile: (participantId: string) => boolean;
        // Experiments (experiment-history-snapshots-plan, Phase 1): the stored
        // objects that own a board + its history. saveExperiment doubles as the
        // bind action (its live_graph_id is the board).
        experiments: Experiment[];
        // Workspaces (TEC-NATKIT-56). The lists above arrive ALREADY SCOPED to the
        // selected workspace — the page owns the lens so scoping lives in one
        // place. These are for the selector and its create/rename/delete.
        workspaces: Workspace[];
        // null is the Unfiled pseudo-workspace, where everything that predates
        // workspaces lives.
        selectedWorkspaceId: string | null;
        // How much is filed elsewhere, so the UI can say so rather than appearing
        // to have lost it.
        hiddenCounts: { experiments: number; graphs: number; profiles: number };
        selectWorkspace: (workspaceId: string | null) => void;
        saveWorkspace: (workspace: Workspace) => boolean;
        deleteWorkspace: (workspaceId: string) => boolean;
        saveExperiment: (experiment: Experiment) => boolean;
        deleteExperiment: (experimentId: string) => boolean;
        // Instances (Phases 2 + 3): recording mints an immutable snapshot welded to
        // the data captured in its window.
        startExperimentInstance: (
            experimentId: string,
            windowStartUs: number,
            participantId: string,
            sensorPositions: { stream_id: string; position: string }[],
            calibrationOverride: string | null,
        ) => boolean;
        finishExperimentInstance: (
            graphId: string,
            windowEndUs: number,
            completed: boolean,
        ) => boolean;
        deleteStreamGraph: (graphId: string, force?: boolean) => boolean;
        // The instance currently recording, if any (minted by the backend).
        recordingInstanceGraphId: string | null;
        // Phase 4 (review): fork an instance into an editable copy, and re-check an
        // instance's artifacts against their recorded checksums.
        forkStreamGraph: (sourceGraphId: string, label?: string) => boolean;
        verifyExperimentInstance: (graphId: string) => boolean;
        instanceVerifications: Record<
            string,
            import("../StreamViewer/types").ExperimentInstanceVerificationMessage
        >;
        // A fork just created that should be opened, and the ack to clear it.
        forkedGraphToOpen: string | null;
        onForkOpened: () => void;
        // Replay (Phase 5): stream an instance's Parquet back onto scratch topics and
        // run the graph over it. Review is paced from the original timestamps;
        // recompute is unpaced.
        startInstanceReplay: (
            graphId: string,
            mode: "review" | "recompute",
            speed: number,
        ) => boolean;
        stopInstanceReplay: (replayId: string) => boolean;
        activeReplay:
            | import("../StreamViewer/types").InstanceReplayMessage
            | null;
        // Phase 7: incremental reactivity — restart a node + downstream after a
        // debounced config edit while the graph is running.
        restartStreamGraphNode: (graphId: string, nodeId: string) => boolean;
        // Device commands (EXECUTION_COMMAND): ask a sensor to do something and
        // show what it says back on its log channel. Used by the calibration node.
        sendDeviceCommand: (
            streamId: string,
            command: string,
            args?: Record<string, unknown>,
        ) => boolean;
        deviceCommandPending: Record<string, boolean>;
        deviceCommandResults: Record<
            string,
            import("../StreamViewer/types").DeviceCommandResultMessage
        >;
        publishSessionBundle: (payload: SessionPublishBundleInput) => boolean;
        // Phase 5: submit a train_validate job via the backend ML proxy, and
        // surface the latest job status + resulting model path for train nodes.
        submitTrainJob: (config: TrainNodeConfig) => void;
        trainJobStatus: string | null;
        trainModelPath: string | null;
        // Durable bundle path from the last completed train job; auto-filled into
        // emg_gesture_classify nodes so live classification needs no manual paste.
        trainBundlePath: string | null;
        // Phase 6: validation accuracy of the last completed train job.
        trainAccuracy: {
            family: string | null;
            mean_accuracy: number;
            min_accuracy: number;
            mean_coverage: number;
        } | null;
        // Phase 4 (provenance edges): the last completed train job as a model
        // record, associated with the submitting train node for the classify
        // model dropdown.
        completedTrainJob: {
            job_id: string;
            bundle_path: string | null;
            model_path: string | null;
            family: string | null;
            accuracy: number | null;
            completed_at_us: number;
        } | null;
        validateStreamGraph: (graph: StreamGraphDefinition) => boolean;
        startStreamGraph: (
            graphId: string,
            startOffset?: number,
            replayId?: string,
        ) => boolean;
        stopStreamGraph: (graphId: string) => boolean;
        // Phase 5: replay support — query a stream's offset bounds / the offset
        // for a scrubbed timestamp, with replies surfaced in streamTimeExtents.
        queryStreamTime: (
            streamId: string,
            timestampUs?: number,
            requestId?: string,
        ) => void;
        streamTimeExtents: Record<string, StreamTimeMessage>;
        // Phase 6: the experiment library (recorded runs) + a refresh trigger.
        recordedRuns: RecordedRunSummary[];
        requestRecordedRuns: () => void;
        inspectStream: (streamId: string) => void;
        // Per-stream live buffers (keyed by stream id) so multiple inspectors can
        // be live at once, plus friendly device names per stream.
        liveStreams: Record<string, LiveStreamData>;
        streamDeviceNames: Record<string, string>;
        // Friendly names a person chose (TEC-NATKIT-103), resolved by the
        // backend. Distinct from streamDeviceNames, which the device reports.
        streamAliases: Record<string, string>;
        setStreamAlias: (streamId: string, alias: string) => boolean;
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
        backendNowUs = 0,
        latestValidation,
        latestEdgeValidation,
        latestGraphDiagnostics,
        connectionState,
        deviceHealth,
        listStreamGraphs,
        requestStreamGraphStatus,
        saveStreamGraph,
        profiles,
        listProfiles,
        saveProfile,
        deleteProfile,
        experiments,
        workspaces,
        selectedWorkspaceId,
        hiddenCounts,
        selectWorkspace,
        saveWorkspace,
        deleteWorkspace,
        saveExperiment,
        deleteExperiment,
        startExperimentInstance,
        finishExperimentInstance,
        deleteStreamGraph,
        recordingInstanceGraphId,
        forkStreamGraph,
        verifyExperimentInstance,
        instanceVerifications,
        forkedGraphToOpen,
        onForkOpened,
        startInstanceReplay,
        stopInstanceReplay,
        activeReplay,
        restartStreamGraphNode,
        sendDeviceCommand,
        deviceCommandPending,
        deviceCommandResults,
        publishSessionBundle,
        submitTrainJob,
        trainJobStatus,
        trainModelPath,
        trainBundlePath,
        trainAccuracy,
        completedTrainJob,
        validateStreamGraph,
        startStreamGraph,
        stopStreamGraph,
        queryStreamTime,
        streamTimeExtents,
        recordedRuns,
        requestRecordedRuns,
        inspectStream,
        liveStreams,
        streamDeviceNames,
        streamAliases,
        setStreamAlias,
        subscribeToStream,
        unsubscribeFromStream,
        formatNumber,
    }: Props = $props();

    let selectedGraphId = $state<string>("");
    let draftGraph = $state<EditorGraphDefinition>(createEmptyGraph());
    let draftGraphLoadedKey = $state("");
    let graphDirty = $state(false);
    // Once the user has picked/created/loaded a graph, the reconciliation effect
    // must never auto-switch the draft to a DIFFERENT graph — otherwise a
    // freshly-saved new graph (e.g. a starter template) gets clobbered in the
    // window between sending the save and its reply landing in graphDefinitions
    // (its id isn't in the list yet, so the old fallback jumped to another graph
    // / a blank board). The effect still refreshes the SAME selected graph.
    let userTouchedSelection = false;
    let selectedNodeId = $state<string | null>(null);
    let selectedNodeIds = $state<Set<string>>(new Set());
    let selectedEdgeId = $state<string | null>(null);
    // Part C: which edge's topic badge dropdown is open (click-to-toggle).
    let openBadgeEdgeId = $state<string | null>(null);
    let compositeTemplates = $state<CompositeTemplate[]>(
        listCompositeTemplates(),
    );
    let compositeFileInput = $state<HTMLInputElement | null>(null);
    let paletteOpen = $state(false);
    // Floating-panel visibility. The canvas fills the page and these menus float
    // over it; each can be hidden to reclaim canvas space.
    let showSidebar = $state(true);
    let showInspector = $state(true);
    // The experiment panel is where the protocol is authored and Record lives now
    // that the experiment owns the board rather than sitting on the canvas.
    let showExperimentPanel = $state(false);
    // The protocol-authoring overlay (ExperimentDesigner); the panel stays the
    // operator surface.
    let showExperimentDesigner = $state(false);
    // Which view the designer opens on. The markers node is the spatial portal
    // into its experiment's protocol, so it opens straight onto the canvas.
    let designerInitialView = $state<"list" | "canvas">("list");
    // The toolbar floats over the canvas and WRAPS: its height changes with how
    // many buttons are showing (selecting a node adds Group, a composite adds two
    // more) and with the viewport width. The side panels are absolutely positioned
    // and used to clear it with a hardcoded 72px, so a wrapped toolbar covered
    // their first row and — being on a higher z-index — swallowed clicks on it.
    // Measure it instead and derive the panels' offset.
    let toolbarHeight = $state(44);

    function runPaletteAction(action: () => void) {
        paletteOpen = false;
        action();
    }

    function handleWindowKeydown(event: KeyboardEvent) {
        // The node detail view (TEC-NATKIT-124) is the topmost layer, so it
        // takes Escape first. ⚠️ Folded into the EXISTING handler rather than a
        // second <svelte:window>: Svelte allows only one per component, and
        // svelte-check does not catch the duplicate — only the vite compile
        // does, as a blank page at runtime.
        if (event.key === "Escape" && detailNodeId) {
            closeNodeDetail();
            return;
        }
        if (event.key === "Escape" && openBadgeEdgeId) {
            openBadgeEdgeId = null;
            return;
        }
        // An open menu was surviving Escape as well as canvas clicks: this handler
        // had no contextMenu branch at all (TEC-NATKIT-71). Checked before the
        // badge branch would swallow it, and returns so Escape does not also fall
        // through to whatever else listens for it.
        if (event.key === "Escape" && contextMenu.open) {
            closeContextMenu();
            return;
        }
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
        const draft = ((): EditorGraphDefinition => {
            const editorGraph = loadEditorGraph(backendGraph.graph_id);
            if (editorGraph) {
                return cloneGraph(editorGraph);
            }
            // Fall back to the backend-persisted composite tree (Phase 7) so a
            // graph saved elsewhere still reloads with its composites intact — no
            // local copy required. Only the flattened primitives remain otherwise.
            if (backendGraph.editor_metadata) {
                return cloneGraph(
                    backendGraph.editor_metadata as EditorGraphDefinition,
                );
            }
            return cloneGraph(backendGraph) as EditorGraphDefinition;
        })();
        // Identity belongs to the record we were asked to open — never to the
        // editor tree we recovered it from. An instance (or fork) is minted by
        // snapshotting a board, and that snapshot's editor_metadata still carries
        // the ORIGINAL board's graph_id and label. Trusting them opened the
        // instance in the inspector while leaving draftGraph pointing at the live
        // board it came from, so every graph_id-keyed action — Start, Stop, Save,
        // status polling — silently addressed the wrong graph. On a fork (which is
        // NOT read-only) a save would have written over its parent.
        draft.graph_id = backendGraph.graph_id;
        if (backendGraph.label) {
            draft.label = backendGraph.label;
        }
        return draft;
    }

    $effect(() => {
        if (graphDefinitions.length === 0) {
            // Seed a blank board only on genuine first mount (nothing persisted
            // and the user hasn't started anything). Never reseed over a draft
            // the user is building or has just saved but whose save reply hasn't
            // repopulated the list yet.
            if (!graphDirty && !userTouchedSelection) {
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

        // Initial adoption: before the user has touched anything, follow the
        // first persisted graph (or re-point off the seeded blank board once
        // real graphs arrive). After the user picks/creates/loads a graph, the
        // selection is theirs — we never switch to a different graph_id.
        const selectionIsPersisted = graphDefinitions.some(
            (graph) => graph.graph_id === selectedGraphId,
        );
        if (!userTouchedSelection && !graphDirty && !selectionIsPersisted) {
            selectedGraphId = graphDefinitions[0].graph_id;
        }

        const matchingGraph = graphDefinitions.find(
            (graph) => graph.graph_id === selectedGraphId,
        );
        // Selected graph isn't in the persisted list yet (a new/renamed graph
        // whose save is still in flight, or an unsaved draft) — keep the current
        // draft; don't fall back to another graph.
        if (!matchingGraph) {
            return;
        }
        const graphKey = `${matchingGraph.graph_id}:${matchingGraph.updated_at_us ?? 0}`;

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

    // --- Experiment binding (experiment-history-snapshots-plan, Phase 1) -----
    // The board record as the BACKEND has it. Provenance — experiment_id,
    // instance_id, immutable, recording — is backend-owned (handleSaveStreamGraph
    // re-pins it from the stored record), so it is read from here rather than from
    // the local draft, which can only ever be a stale copy of it.
    const selectedGraphRecord = $derived(
        graphDefinitions.find((graph) => graph.graph_id === selectedGraphId) ??
            null,
    );

    const boundExperimentId = $derived(selectedGraphRecord?.experiment_id ?? "");

    const boundExperiment = $derived(
        boundExperimentId
            ? (experiments.find(
                  (experiment) => experiment.experiment_id === boundExperimentId,
              ) ?? null)
            : null,
    );

    // Field edits are debounced before they reach the backend. Every save rewrites
    // the whole experiment store (re-serialize + atomic rename) and re-runs the
    // binding sweep, so a per-keystroke save would do that once per character.
    // Edits accumulate locally in the meantime, otherwise a burst of keystrokes
    // would each build its patch from the same stale record and only the last field
    // typed would survive. Everything that READS the experiment reads this view, so
    // the UI reflects the edit immediately regardless of when the save lands.
    let pendingExperimentEdit = $state<Experiment | null>(null);
    let experimentSaveTimer: ReturnType<typeof setTimeout> | null = null;

    // An edit that has been SENT but not yet echoed back by the backend
    // (TEC-NATKIT-19).
    //
    // ⚠️ This exists because clearing the pending edit at SEND time made the
    // designer render the PREVIOUS protocol for the length of the round trip. It
    // was measured at ~11ms on this machine and is as long as the round trip
    // anywhere else — so on a slow or failed save the author watches their edit
    // vanish with nothing to explain it. It also reset anything holding a
    // reference INTO the protocol: the canvas remembers its zoomed repeat group by
    // step id, so opening a group just after "Convert to editable steps" zoomed in
    // and then bounced back out.
    //
    // `storedUpdatedAtUs` is the stored record's timestamp AT SEND TIME, so the
    // echo is recognised by that value advancing. Deliberately not "the backend's
    // timestamp is newer than my clock": those are two different clocks, and
    // comparing them is how this sort of fix breaks on a machine whose clock is a
    // few seconds off.
    interface InFlightExperimentEdit {
        experiment: Experiment;
        storedUpdatedAtUs: number;
        timeout: ReturnType<typeof setTimeout>;
    }
    let inFlightExperimentEdit = $state<InFlightExperimentEdit | null>(null);

    // How long to keep showing an unconfirmed edit before giving up on it.
    // ⚠️ Not optional: without it a save that is never echoed leaves the edit on
    // screen forever and the author believes it was stored. Long enough that a
    // slow round trip is not mistaken for a failure.
    const EXPERIMENT_ECHO_TIMEOUT_MS = 10000;

    function clearInFlightExperimentEdit(): void {
        if (inFlightExperimentEdit) {
            clearTimeout(inFlightExperimentEdit.timeout);
            inFlightExperimentEdit = null;
        }
    }

    // The edit the UI should show: what is being typed, else what has been sent but
    // not confirmed, else what the store holds. Ordered so a newer intention always
    // wins over an older one.
    const boundExperimentView = $derived(
        pendingExperimentEdit &&
            pendingExperimentEdit.experiment_id === boundExperimentId
            ? pendingExperimentEdit
            : inFlightExperimentEdit &&
                inFlightExperimentEdit.experiment.experiment_id === boundExperimentId
              ? inFlightExperimentEdit.experiment
              : boundExperiment,
    );

    // The echo landed: the store's copy of this experiment is newer than it was
    // when we sent, so it is now at least as new as our edit.
    $effect(() => {
        const inFlight = inFlightExperimentEdit;
        if (!inFlight) {
            return;
        }
        const stored = experiments.find(
            (experiment) =>
                experiment.experiment_id === inFlight.experiment.experiment_id,
        );
        if (!stored) {
            // The record went away underneath us — nothing left to confirm.
            clearInFlightExperimentEdit();
            return;
        }
        if ((stored.updated_at_us ?? 0) > inFlight.storedUpdatedAtUs) {
            clearInFlightExperimentEdit();
        }
    });

    function queueExperimentEdit(next: Experiment): void {
        pendingExperimentEdit = next;
        if (experimentSaveTimer) {
            clearTimeout(experimentSaveTimer);
        }
        experimentSaveTimer = setTimeout(flushExperimentEdit, 400);
    }

    // Send any queued edit now. Called before recording (the session bundle is
    // stamped with the protocol/participant, so a snapshot must not record against
    // a protocol the server hasn't been told about yet) and before a rebind, where
    // WS ordering makes flush-then-bind land the fields on the old binding and the
    // new binding last.
    function flushExperimentEdit(): void {
        if (experimentSaveTimer) {
            clearTimeout(experimentSaveTimer);
            experimentSaveTimer = null;
        }
        const edit = pendingExperimentEdit;
        pendingExperimentEdit = null;
        if (!edit) {
            return;
        }
        // Hold it as in-flight rather than dropping it: the store does not know
        // about it until the echo arrives, and falling back to the store in the
        // meantime is the flash this ticket is about.
        const storedUpdatedAtUs =
            experiments.find(
                (experiment) => experiment.experiment_id === edit.experiment_id,
            )?.updated_at_us ?? 0;
        if (!saveExperiment(edit)) {
            // Refused outright (a closed socket). The store is authoritative, so
            // continuing to show the edit would be a lie — and saveExperiment has
            // already set the error banner, so the disappearance is explained.
            clearInFlightExperimentEdit();
            return;
        }
        clearInFlightExperimentEdit();
        inFlightExperimentEdit = {
            experiment: edit,
            storedUpdatedAtUs,
            timeout: setTimeout(() => {
                // No echo. Stop claiming the edit is stored, and SAY SO — silently
                // reverting is exactly the "my edit vanished" this fix removes.
                inFlightExperimentEdit = null;
                showAlert({
                    title: "That change may not have been saved",
                    body:
                        "The backend did not confirm the edit within ten seconds, " +
                        "so the panel is showing the last version it did confirm. " +
                        "Re-apply the change, and check the connection if it keeps " +
                        "happening.",
                });
            }, EXPERIMENT_ECHO_TIMEOUT_MS),
        };
    }

    // Drop a queued edit unsent — used when the record it targets is going away, so
    // a late save can't resurrect a deleted experiment or re-bind an unbound board.
    function discardExperimentEdit(): void {
        if (experimentSaveTimer) {
            clearTimeout(experimentSaveTimer);
            experimentSaveTimer = null;
        }
        pendingExperimentEdit = null;
        // The in-flight one too: this is called when the record it targets is going
        // away, and a late echo must not resurrect it on screen.
        clearInFlightExperimentEdit();
    }

    // An immutable instance is read-only everywhere: the backend rejects a save
    // over it, so the editor must not offer to write one (Phase 7's reactive
    // auto-save would otherwise spray rejections on every keystroke).
    const boardIsImmutable = $derived(selectedGraphRecord?.immutable === true);

    // Cue-schedule preview for the bound protocol.
    const boundExperimentSummary = $derived.by(() => {
        const protocol = boundExperimentView?.protocol;
        if (!protocol) {
            return null;
        }
        const schedule = scheduleForProtocol(protocol);
        return {
            holdCues: schedule.filter((cue) => cue.phase === "hold").length,
            durationS: Math.round(scheduleDurationMs(schedule) / 1000),
        };
    });

    // Every source on the board is a recorded source now that the experiment owns
    // the whole graph — that is what replaced the source→experiment provenance
    // edge. Resolve their device_id strings so the session bundle can name the
    // topics reconstruction should read (instead of scanning the broker to guess).
    const recordedDeviceIds = $derived.by(() => {
        const deviceIds = new Set<string>();
        for (const node of draftGraph.nodes) {
            if (node.kind !== "stream_source" || !node.stream_id) {
                continue;
            }
            const deviceId = streamDeviceNames[String(node.stream_id)];
            if (deviceId) {
                deviceIds.add(deviceId);
            }
        }
        return [...deviceIds];
    });

    // This experiment's history, newest first. Instances live in the graph store
    // (they ARE graphs), so this reads the same list the picker filters them out of.
    const boundExperimentInstances = $derived(
        boundExperimentId
            ? graphDefinitions
                  .filter(
                      (graph) =>
                          graph.experiment_id === boundExperimentId &&
                          !!graph.instance_id,
                  )
                  .sort(
                      (left, right) =>
                          (right.created_at_us ?? 0) - (left.created_at_us ?? 0),
                  )
            : [],
    );

    // The full history, as a TREE. Recordings sit under their experiment; forks nest
    // under whatever they were forked from (a fork of a fork nests two deep), which
    // is what `forked_from` is for. Built for every experiment, not just the bound
    // one, so the sidebar shows the whole history without switching boards first.
    interface InstanceTreeNode {
        graph: StreamGraphDefinition;
        children: InstanceTreeNode[];
    }
    const experimentTree = $derived.by(() => {
        const instances = graphDefinitions.filter((graph) => !!graph.instance_id);
        // ⚠️ Keyed by GRAPH ID, which is globally unique. Keyed by `instance_id`
        // this silently LOST recordings (TEC-NATKIT-80): run numbering restarts
        // per experiment, so "run-0001" is not one instance but one per
        // experiment, and `Map.set` kept only whichever came last. On the dev
        // store that meant 9 instances collapsing to 6 rows, all of them from a
        // single experiment — every other experiment's history was simply absent
        // from the tree, with no error and nothing to notice.
        const byGraphId = new Map<string, InstanceTreeNode>();
        for (const graph of instances) {
            byGraphId.set(graph.graph_id, { graph, children: [] });
        }
        // Fork parents are named by `forked_from`, which holds an INSTANCE id and
        // so carries the same ambiguity — resolved within the parent's own
        // experiment rather than across all of them.
        const forkKey = (experimentId: string | undefined, instanceId: string) =>
            `${experimentId ?? ""}\u0000${instanceId}`;
        const byExperimentInstance = new Map<string, InstanceTreeNode>();
        for (const node of byGraphId.values()) {
            byExperimentInstance.set(
                forkKey(node.graph.experiment_id, node.graph.instance_id as string),
                node,
            );
        }
        const roots = new Map<string, InstanceTreeNode[]>();
        for (const node of byGraphId.values()) {
            const parentId = node.graph.forked_from;
            const parent =
                parentId && parentId !== node.graph.instance_id
                    ? byExperimentInstance.get(
                          forkKey(node.graph.experiment_id, parentId),
                      )
                    : undefined;
            // ⚠️ `parentId !== own instance_id` above: a record naming itself as
            // its parent would be pushed into its own children and never appear as
            // a root, and the render is recursive — so it would hang the page
            // rather than show a wrong tree.
            if (parent) {
                parent.children.push(node);
                continue;
            }
            // A recording, or a fork whose parent has been deleted — either way it
            // hangs off the experiment rather than vanishing from the tree.
            const experimentId = node.graph.experiment_id ?? "";
            const bucket = roots.get(experimentId) ?? [];
            bucket.push(node);
            roots.set(experimentId, bucket);
        }
        const byCreated = (left: InstanceTreeNode, right: InstanceTreeNode) =>
            (right.graph.created_at_us ?? 0) - (left.graph.created_at_us ?? 0);
        const sortDeep = (nodes: InstanceTreeNode[]) => {
            nodes.sort(byCreated);
            for (const node of nodes) {
                sortDeep(node.children);
            }
        };
        for (const bucket of roots.values()) {
            sortDeep(bucket);
        }
        // Every experiment gets an entry, even with no history yet, so the tree is
        // also how you find an experiment.
        return experiments.map((experiment) => ({
            experiment,
            instances: roots.get(experiment.experiment_id) ?? [],
        }));
    });

    // Instances that can be TRAINED on (Phase 6): sealed recordings with verified
    // artifacts. A forked instance qualifies too — it inherits the same files.
    const trainableInstances = $derived(
        graphDefinitions
            .filter(
                (graph) =>
                    !!graph.instance_id &&
                    graph.recording?.status === "complete" &&
                    (graph.recording?.artifacts?.data?.length ?? 0) > 0,
            )
            .sort(
                (left, right) =>
                    (right.created_at_us ?? 0) - (left.created_at_us ?? 0),
            ),
    );

    function toggleTrainInstance(graphId: string, list: "train" | "eval") {
        const key = list === "train" ? "train_instances" : "eval_instances";
        const current = selectedTrainNode?.config[key] ?? [];
        const next = current.includes(graphId)
            ? current.filter((entry) => entry !== graphId)
            : [...current, graphId];
        updateTrainConfig({ [key]: next });
    }

    // The selected instance, when the open board IS one (Phase 4 review).
    const selectedInstance = $derived(
        selectedGraphRecord?.instance_id ? selectedGraphRecord : null,
    );

    const selectedInstanceVerification = $derived(
        selectedInstance ? (instanceVerifications[selectedInstance.graph_id] ?? null) : null,
    );

    // Boards the picker offers. Instances and forks live in the graph store too,
    // so without this filter every recorded snapshot would show up as a board;
    // they are reached through the experiment's history instead.
    const boardDefinitions = $derived(
        graphDefinitions.filter((graph) => !graph.instance_id),
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

    // The node detail view (TEC-NATKIT-124): double-click a node to open it
    // full-screen, n8n style, instead of reading a 1,700-line inspector through
    // a narrow right-hand rail.
    //
    // It holds no state of its own — it renders the SAME inspector snippet the
    // sidebar does, against the SAME selectedNodeId. Opening it selects the
    // node, so the sidebar and the detail view can never disagree about which
    // node is being edited.
    // Type-to-filter for the Add Node palette (TEC-NATKIT-127 item 6).
    // Seventeen transforms in one flat column is a list you scan, not a menu
    // you use. Matches the label AND the kind, because somebody who knows the
    // kind (`bandpass_iir`) should not have to remember its prose label.
    let paletteFilter = $state("");

    function paletteMatches(...fields: (string | undefined | null)[]): boolean {
        const needle = paletteFilter.trim().toLowerCase();
        if (!needle) return true;
        return fields.some((field) =>
            (field ?? "").toLowerCase().includes(needle),
        );
    }

    let detailNodeId = $state<string | null>(null);
    const detailNode = $derived(
        detailNodeId
            ? (draftGraph.nodes.find((node) => node.id === detailNodeId) ?? null)
            : null,
    );

    function openNodeDetail(nodeId: string) {
        selectNode(nodeId);
        detailNodeId = nodeId;
    }

    function closeNodeDetail() {
        detailNodeId = null;
    }

    // The shared right-hand edge for every marble strip on the canvas
    // (TEC-NATKIT-106): the newest event ANY lane in the graph has seen, on the
    // DATA clock. Resolved once here rather than per card, because two rows are
    // only comparable against one axis — per-card axes would right-align every
    // row and make a stalled input indistinguishable from a live one, which is
    // the failure the strips exist to reveal. Using the data clock also means a
    // paused replay holds the strips still instead of draining them.
    const marbleAxisEndUs = $derived.by(() => {
        const lanes: (ChannelActivity | undefined)[] = [];
        for (const status of Object.values(
            selectedGraphStatus?.node_statuses ?? {},
        )) {
            lanes.push(status?.data_activity, status?.marker_activity);
        }
        return resolveAxisEndUs(lanes);
    });

    // Node kinds whose config comes from the runtime NODE CATALOG rather than
    // from transformCapabilities. A transform's fields arrive with its
    // capability; these kinds are not transform capabilities, so without this
    // they would have no config UI at all — which is exactly why combine had
    // none before TEC-NATKIT-103 and threshold/gate would have none now.
    const CATALOG_CONFIG_KINDS = [
        "combine",
        "threshold",
        "gate",
        "gap_detect",
        "marker_merge",
        "marker_filter",
        "marker_debounce",
        "marker_take_until",
    ];

    // Kinds that publish a topic and configure entirely from the catalog, so
    // one inspector block serves them all: an output identifier plus their
    // fields. Combine keeps its own block because it also has variadic
    // input-port controls.
    const TOPIC_PUBLISHING_KINDS = [
        "threshold",
        "gate",
        "gap_detect",
        "marker_merge",
        "marker_filter",
        "marker_debounce",
        "marker_take_until",
    ];

    // The two lane crossings share an inspector: both publish a topic (so both
    // need an identifier) and both configure entirely from the catalog.
    const selectedLaneCrossingNode = $derived(
        selectedNode && TOPIC_PUBLISHING_KINDS.includes(selectedNode.kind)
            ? (selectedNode as EditorGraphNode & {
                  output_identifier?: string;
                  config?: Record<string, number | string | boolean | undefined>;
              })
            : null,
    );

    // Each says what it DOES, because both are silently wrong when misconfigured
    // rather than erroring: a threshold whose level sits in the noise floor
    // fires constantly, and a gate whose labels never arrive passes nothing.
    const laneCrossingHint = $derived.by(() => {
        if (selectedNode?.kind === "threshold") {
            return "Emits a marker when the channel crosses the level and stays past it for the dwell. The marker is stamped at the interpolated crossing time, not the frame's. Refractory suppresses repeat firing — raise it if a hovering signal floods the output.";
        }
        if (selectedNode?.kind === "gate") {
            return "Passes data only between the opening and closing markers. Labels match a marker's name OR its event, so a threshold in 'either' mode can open on 'rising' and close on 'falling'. Splitting at the sample is exact; the other modes trade accuracy at the window edges for uniform frame sizes.";
        }
        if (selectedNode?.kind === "gap_detect") {
            return "Emits a marker when consecutive frames arrive further apart than they should, decided from the frames' own timestamps so it replays identically. Stamped where the data STOPPED, and it says whether frames were lost (seq_no jumped) or the producer paused. ⚠️ It fires when data RESUMES — a gap is the distance between two frames — so a dropout still in progress shows as a stalled node and a quiet strip, not as a marker.";
        }
        if (selectedNode?.kind === "marker_merge") {
            return "Merges its marker inputs into one stream, ordered by each marker's own emitted time rather than by arrival. Output waits for the slowest input, so a silent input holds the merge.";
        }
        if (selectedNode?.kind === "marker_filter") {
            return "Keeps only the markers whose chosen field matches. An empty value list passes everything, deliberately — a filter that blocked until configured would look exactly like a dead upstream.";
        }
        if (selectedNode?.kind === "marker_debounce") {
            return "Suppresses markers arriving within the window of the last one PASSED, so a dense burst cannot extend the suppression indefinitely. Reads the markers' own timestamps, so a replay debounces identically.";
        }
        if (selectedNode?.kind === "marker_take_until") {
            return "Passes the first input's markers until one arrives on 'until', then stops for good. 'Until' is decided by timestamp, not arrival, so the cut lands in the same place on a replay as it did live.";
        }
        return "";
    });

    const selectedCatalogConfigNode = $derived(
        selectedNode && CATALOG_CONFIG_KINDS.includes(selectedNode.kind)
            ? selectedNode
            : null,
    );

    // Filtered by each field's `visible_when`, so a value the selected mode
    // would ignore is never offered (combine's tolerance under anything but
    // zip, its output rate under anything but sample).
    const catalogConfigFields = $derived(
        selectedCatalogConfigNode
            ? visibleConfigFields(
                  nodeCatalog.find(
                      (entry) => entry.node_type === selectedCatalogConfigNode.kind,
                  )?.config_fields ?? [],
                  (selectedCatalogConfigNode as { config?: Record<string, unknown> })
                      .config ?? {},
              )
            : [],
    );

    // Picking the wrong join policy is silently wrong rather than an error, so
    // the inspector says what the selected one DOES rather than leaving the
    // author to infer it from the name.
    const combineJoinPolicyHint = $derived.by(() => {
        const policy = selectedCombineNode?.config?.join_policy ?? "zip";
        switch (policy) {
            case "combine_latest":
                return "Emits whenever any input produces, reusing every other input's most recent frame. For mixed-rate fusion, where waiting for the slow input would throw away most of the fast one.";
            case "with_latest_from":
                return "Only the FIRST input triggers output; the others are sampled at its cadence and contribute their most recent frame. A frame on another input emits nothing.";
            case "sample":
                return "A fixed rate on the data clock drives output, and every input contributes its latest frame. For logging sources with no common cadence.";
            default:
                return "Lockstep: one frame per input per output, waiting for laggards, pairing frames whose timestamps fall within the tolerance. Right when every input derives from a common window.";
        }
    });

    // A legacy `experiment` node on an unconverted board. It no longer authors
    // anything — the inspector offers to convert it instead.
    const selectedLegacyExperimentNode = $derived(
        selectedNode?.kind === "experiment" ? selectedNode : null,
    );

    const selectedMarkersNode = $derived(
        selectedNode?.kind === "markers" || selectedNode?.kind === "experiment"
            ? selectedNode
            : null,
    );

    const selectedTrainNode = $derived(
        selectedNode?.kind === "train" ? selectedNode : null,
    );

    const selectedExportNode = $derived(
        selectedNode?.kind === "export" ? selectedNode : null,
    );

    // The export node is topic-aware: each inbound data edge is classified by
    // what its source emits. A data input supplies the exported rows; a
    // `markers` input supplies the session window + cue labels.
    // Both are read off the RUNTIME status (output_topics), which is where the
    // resolved stream id + schema live.
    const exportInputs = $derived.by(() => {
        const data: {
            nodeId: string;
            label: string;
            topic: OutputChannelTopic | undefined;
        }[] = [];
        const experiments: {
            nodeId: string;
            label: string;
            sessionId: string;
            markerStreamId: string | undefined;
        }[] = [];
        if (!selectedExportNode) {
            return { data, experiments };
        }
        for (const edge of draftGraph.edges) {
            if (
                edge.target_node_id !== selectedExportNode.id ||
                edge.edge_kind === "provenance"
            ) {
                continue;
            }
            const src = draftGraph.nodes.find((n) => n.id === edge.source_node_id);
            if (!src) {
                continue;
            }
            const status = selectedGraphStatus?.node_statuses?.[src.id];
            if (src.kind === "markers" || src.kind === "experiment") {
                // The session id is the bound experiment's id (a legacy node's own
                // config is the fallback, so an unconverted board still exports).
                const sessionId = sanitizeIdentifier(
                    boundExperimentId ||
                        (src.kind === "experiment"
                            ? (src.config.experiment_id ?? "")
                            : ""),
                );
                if (sessionId) {
                    experiments.push({
                        nodeId: src.id,
                        label: src.label,
                        sessionId,
                        markerStreamId:
                            markerTopicOfChannel(status?.output_topics)?.id ??
                            status?.output_stream_id,
                    });
                }
                continue;
            }
            const topic = dataTopicOfChannel(status?.output_topics);
            data.push({ nodeId: src.id, label: src.label, topic });
        }
        return { data, experiments };
    });

    // The channel the export endpoint reads rows from.
    const exportChannelStreamId = $derived(
        exportInputs.data.find((entry) => entry.topic)?.topic?.id,
    );

    // Markers come from the data channel itself when a combine bundled them
    // (Data/<id> + Marker/<id> share an id). When a markers node is wired
    // straight into the export node instead, its marker channel is separate and
    // has to be named explicitly.
    const exportMarkerStreamId = $derived.by(() => {
        const bundled = exportInputs.data.find(
            (entry) => entry.topic,
        )?.nodeId;
        if (bundled) {
            const status = selectedGraphStatus?.node_statuses?.[bundled];
            if (markerTopicOfChannel(status?.output_topics)) {
                return undefined;  // already bundled on the data channel
            }
        }
        return exportInputs.experiments.find((e) => e.markerStreamId)
            ?.markerStreamId;
    });

    // What the Export button will actually submit, or why it can't.
    const exportReadiness = $derived.by(() => {
        if (!selectedExportNode) {
            return { ready: false, reason: "" };
        }
        const { data, experiments } = exportInputs;
        if (data.length === 0) {
            return {
                ready: false,
                reason: "Wire a data stream into this export node.",
            };
        }
        if (experiments.length === 0) {
            return {
                ready: false,
                reason:
                    "Wire a markers node in — it defines the session window and the labels.",
            };
        }
        const resolved = data.find((entry) => entry.topic);
        if (!resolved) {
            return {
                ready: false,
                reason:
                    "Start the graph so the upstream stream resolves a topic, then export.",
            };
        }
        return { ready: true, reason: "" };
    });

    // The experiment whose runs the train picker scopes to. This used to be
    // resolved from an experiment→train provenance edge; the experiment now owns
    // the whole board, so the board's binding says it without any wiring — which
    // is why that edge was retired.
    const trainLineageExperimentIds = $derived(
        boundExperimentId ? [sanitizeIdentifier(boundExperimentId)] : [],
    );

    // True when a recorded run belongs to the board's experiment (its session_id
    // matches that experiment's id).
    function isRunInScope(run: RecordedRunSummary): boolean {
        if (trainLineageExperimentIds.length === 0) {
            return false;
        }
        return trainLineageExperimentIds.includes(
            sanitizeIdentifier(run.session_id),
        );
    }

    // Recorded runs for the picker. When experiment(s) are wired into the train
    // node, their runs are surfaced FIRST (and badged), but every other recorded
    // run stays visible below so you can still train across sessions/experiments.
    // With no experiment wired, this is just every recorded run in order.
    const trainScopedRuns = $derived.by(() => {
        if (trainLineageExperimentIds.length === 0) {
            return recordedRuns;
        }
        const inScope: RecordedRunSummary[] = [];
        const others: RecordedRunSummary[] = [];
        for (const run of recordedRuns) {
            (isRunInScope(run) ? inScope : others).push(run);
        }
        return [...inScope, ...others];
    });

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

    // Phase 4: models offered to the selected classify node by a train→classify
    // provenance edge. When the node has an inbound provenance edge into its
    // prov_model port from a train node, list that trainer's models (newest
    // first) so the operator picks one instead of pasting a path.
    const classifyModelOptions = $derived.by(() => {
        if (!selectedTransformNode) {
            return [] as TrainedModel[];
        }
        const models: TrainedModel[] = [];
        for (const edge of draftGraph.edges) {
            if (
                edge.edge_kind !== "provenance" ||
                edge.target_node_id !== selectedTransformNode.id ||
                edge.target_port !== PROVENANCE_PORT_MODEL
            ) {
                continue;
            }
            const src = draftGraph.nodes.find(
                (n) => n.id === edge.source_node_id,
            );
            if (src?.kind === "train") {
                models.push(...(src.config.models ?? []));
            }
        }
        // Newest first; a model with a usable path is required to select.
        return [...models]
            .filter((m) => m.bundle_path || m.model_path)
            .sort((a, b) => b.completed_at_us - a.completed_at_us);
    });

    // Phase 5: the model currently loaded by the selected classify node, matched
    // back to a wired trainer's model by path — so the inspector shows which
    // model (label + accuracy) the classifier is serving.
    const selectedClassifyModel = $derived.by(() => {
        const path = selectedTransformNode?.config?.model_path;
        if (!path || classifyModelOptions.length === 0) {
            return null;
        }
        return (
            classifyModelOptions.find(
                (m) => m.bundle_path === path || m.model_path === path,
            ) ?? null
        );
    });

    // The path a classify node loads for a given model: emg_gesture_classify
    // loads the self-describing bundle; a legacy lda_classify loads the raw model
    // path. Used both as the dropdown option value (so the current selection
    // reflects) and when applying a pick.
    function classifyModelPath(model: TrainedModel): string | null {
        if (selectedTransformNode?.transform_kind === "lda_classify") {
            return model.model_path ?? model.bundle_path;
        }
        return model.bundle_path ?? model.model_path;
    }

    // Apply a selected model to the classify node: writes config.model_path
    // (explicit + re-selectable) and restarts if live.
    function selectClassifyModel(path: string) {
        if (!selectedTransformNode || !path) {
            return;
        }
        const nodeId = selectedTransformNode.id;
        updateSelectedNode((node) =>
            node.kind === "transform"
                ? { ...node, config: { ...node.config, model_path: path } }
                : node,
        );
        scheduleReactiveRestart(nodeId);
    }

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
    // Outcome of the last parquet download from an export node's inspector.
    let exportDownload = $state<ExportDownloadResult | null>(null);

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
    // Kinds whose silence is NORMAL. A gap detector emits only when data drops
    // out, a filter only when something matches — so "no output for 3s" is not a
    // fault for these, it is the healthy case. Without this exception, adding a
    // gap detector to a board would permanently park a warning in Diagnostics
    // (TEC-NATKIT-116 is the same problem in the status layer).
    const SILENCE_IS_NORMAL_KINDS = [
        "gap_detect",
        "marker_filter",
        "marker_take_until",
        "marker_debounce",
    ];

    // ⚠️ A LABEL THAT CONTRADICTS THE CONFIG. A combine called "Combine (zip)"
    // while configured `combine latest` tells the canvas one story and the
    // runtime another — and the label is what everybody reads. Surfaced rather
    // than auto-corrected, because renaming somebody's node behind their back
    // is worse than telling them.
    const labelMismatches = $derived.by(() => {
        const out: { label: string; message: string }[] = [];
        for (const node of draftGraph.nodes) {
            if (node.kind !== "combine") continue;
            const policy = String(
                (node.config as Record<string, unknown> | undefined)
                    ?.join_policy ?? "zip",
            );
            const label = (node.label ?? "").toLowerCase();
            const policyWords: Record<string, string> = {
                zip: "zip",
                combine_latest: "combine latest",
                with_latest_from: "with latest from",
                sample: "sample",
            };
            // Only complain when the label names a DIFFERENT policy, not when
            // it names none — most labels say what the node is for, not how it
            // joins, and nagging about those would make this useless.
            const named = Object.entries(policyWords).find(
                ([key, words]) =>
                    label.includes(words) || label.includes(key.replace(/_/g, "")),
            );
            if (named && named[0] !== policy) {
                out.push({
                    label: node.label || node.id,
                    message: `Labelled "${named[1]}" but configured "${policyWords[policy] ?? policy}".`,
                });
            }
        }
        return out;
    });

    const runtimeIssues = $derived.by(() => {
        const nodeById = new Map(draftGraph.nodes.map((node) => [node.id, node]));
        return Object.entries(selectedGraphStatus?.node_statuses ?? {})
            .filter(([nodeId, status]) => {
                if (status.state === "error" || status.state === "blocked") {
                    return true;
                }
                // ⚠️ STALLED BELONGS HERE. Diagnostics said "No validation
                // issues yet" while a node on the same board read STALLED,
                // because this filter only looked for error/blocked — so the
                // one panel meant to answer "is anything wrong" was the one
                // place that never mentioned it.
                if (status.state !== "stalled") return false;
                const kind = nodeById.get(nodeId)?.kind ?? "";
                return !SILENCE_IS_NORMAL_KINDS.includes(kind);
            })
            .map(([nodeId, status]) => {
                const node = nodeById.get(nodeId);
                const label = node?.label || nodeId;
                if (status.state === "stalled") {
                    return {
                        label,
                        // Say WHY, not just the state. "Stalled" on its own
                        // sends people to the logs; the threshold that decided
                        // it is the thing they need.
                        message:
                            "No output for over 3s — the upstream input may have stopped.",
                    };
                }
                return {
                    label,
                    message: status.message ?? `Node is ${status.state}.`,
                };
            });
    });

    function markDraftChanged(nextGraph: EditorGraphDefinition) {
        // Read-only backstop for a sealed instance. Every edit funnels through here
        // (palette adds, drags, config changes, composite group/ungroup, param
        // writes), so gating this one function covers all of them — rather than
        // hoping each remembered to check. The plan lists immutability's back doors
        // precisely because there are many; the backend rejection is the outer
        // backstop, and this keeps the editor from ever reaching a state it cannot
        // persist.
        if (boardIsImmutable) {
            connectionMessage =
                "This is an immutable recording — fork it to edit (History → Fork to edit).";
            return;
        }
        nextGraph.updated_at_us = Date.now() * 1000;
        nextGraph.ui = nextGraph.ui ?? {};
        nextGraph.ui.selected_node_id = selectedNodeId;
        draftGraph = nextGraph;
        graphDirty = true;
        userTouchedSelection = true;
    }

    // Display-only state — the viewport, and whether a viewer draws its inline
    // graph — happens to be stored IN the graph document, so it used to funnel
    // through markDraftChanged and get refused on a sealed recording. But
    // reviewing a recording is exactly when you pan around it and switch the
    // graphs on, and neither changes the pipeline. So apply these to the local
    // draft, and on an immutable board skip the dirty/persist bookkeeping: there
    // is nothing to save, and markDraftChanged would only emit a refusal.
    function markViewStateChanged(nextGraph: EditorGraphDefinition) {
        if (boardIsImmutable) {
            nextGraph.ui = nextGraph.ui ?? {};
            nextGraph.ui.selected_node_id = selectedNodeId;
            draftGraph = nextGraph;
            return;
        }
        markDraftChanged(nextGraph);
    }

    // Every path that throws away an unsaved board asks the same question, so it
    // is asked in one place.
    function confirmDiscardEdits(nextAction: string): Promise<boolean> {
        return askConfirm({
            title: "Discard unsaved edits?",
            body: `This board has changes that have not been saved. ${nextAction}`,
            confirmLabel: "Discard and continue",
            danger: true,
        });
    }

    async function selectGraph(graphId: string) {
        if (graphDirty) {
            if (!(await confirmDiscardEdits("Opening another board will lose them."))) {
                return;
            }
        }
        const matchingGraph =
            graphDefinitions.find((graph) => graph.graph_id === graphId) ?? null;
        if (!matchingGraph) {
            return;
        }
        selectedGraphId = graphId;
        userTouchedSelection = true;
        draftGraph = resolveDraftForGraph(matchingGraph);
        draftGraphLoadedKey = `${matchingGraph.graph_id}:${matchingGraph.updated_at_us ?? 0}`;
        graphDirty = false;
        selectedNodeId = draftGraph.ui?.selected_node_id ?? null;
        selectedNodeIds = selectedNodeId ? new Set([selectedNodeId]) : new Set();
        selectedEdgeId = null;
        pendingConnection = null;
        requestStreamGraphStatus(graphId);
    }

    async function createGraph() {
        if (graphDirty) {
            if (!(await confirmDiscardEdits("Creating a new board will lose them."))) {
                return;
            }
        }
        draftGraph = createEmptyGraph();
        selectedGraphId = draftGraph.graph_id;
        draftGraphLoadedKey = selectedGraphId;
        graphDirty = true;
        userTouchedSelection = true;
        selectedNodeId = null;
        selectedNodeIds = new Set();
        selectedEdgeId = null;
        pendingConnection = null;
    }

    // When a fork comes back, open it: the whole point of forking is to start
    // editing the copy, and leaving the user on the read-only original would make
    // them hunt for it in the tree.
    $effect(() => {
        const target = forkedGraphToOpen;
        if (!target) {
            return;
        }
        if (graphDefinitions.some((graph) => graph.graph_id === target)) {
            onForkOpened();
            selectGraph(target);
        }
    });

    // Phase 8: load a starter preset as a new board, binding its source to the
    // first available stream (the user can rebind in the inspector).
    async function loadStarterTemplate(template: StarterTemplate) {
        if (graphDirty) {
            if (
                !(await confirmDiscardEdits(
                    "Loading a starter template will lose them.",
                ))
            ) {
                return;
            }
        }
        const firstStreamId = availableStreams[0]?.streamId ?? null;
        draftGraph = template.build(firstStreamId);
        selectedGraphId = draftGraph.graph_id;
        draftGraphLoadedKey = selectedGraphId;
        graphDirty = true;
        userTouchedSelection = true;
        selectedNodeId = null;
        selectedNodeIds = new Set();
        selectedEdgeId = null;
        pendingConnection = null;
        // A template that is a whole study also brings its WORKSPACE (#407). Created
        // FIRST and switched to, so the experiment and board below are filed there
        // rather than into Unfiled — where the scoped lists would hide them the
        // instant the user switched workspace, which looks like the template having
        // silently failed.
        //
        // An existing workspace with the same id is reused rather than clobbered:
        // loading the template twice should put you back in the study you already
        // have, not mint "ADL study 2".
        let templateWorkspaceId = selectedWorkspaceId;
        if (template.workspace) {
            const workspaceId =
                sanitizeIdentifier(template.workspace.label) ||
                `workspace-${Date.now()}`;
            const existing = workspaces.find(
                (workspace) => workspace.workspace_id === workspaceId,
            );
            if (!existing) {
                saveWorkspace({
                    workspace_id: workspaceId,
                    label: template.workspace.label,
                    notes: "",
                    created_at_us: 0,
                    updated_at_us: 0,
                });
            }
            templateWorkspaceId = workspaceId;
            selectWorkspace(workspaceId);
        }
        // A recording template needs its EXPERIMENT too, not just the board: the
        // protocol lives in the experiment record and the board's markers node
        // resolves its topic from the binding. persistExperiment saves the board
        // first, so the backend has a graph to bind by the time it gets here.
        if (template.experiment) {
            const nowUs = Date.now() * 1000;
            const experimentId =
                sanitizeIdentifier(`${template.id}-${Date.now()}`) ||
                `experiment-${Date.now()}`;
            persistExperiment({
                experiment_id: experimentId,
                label: template.experiment.label,
                // The workspace just created, NOT `selectedWorkspaceId` — that prop
                // has not round-tripped through the page yet at this point.
                workspace_id: templateWorkspaceId ?? "",
                protocol: { ...template.experiment.protocol },
                notes: "",
                live_graph_id: selectedGraphId,
                created_at_us: nowUs,
                updated_at_us: nowUs,
            });
            showExperimentPanel = true;
        }
    }

    // Phase 4: profiles. Save the CURRENT (saved) graph as a person's profile,
    // capturing the bundle path, protocol, device binding, and validation
    // accuracy. The bundle is already baked into the graph's classify node, so
    // loading a profile just reloads that graph — resume in one click.
    async function saveCurrentAsProfile() {
        if (!selectedGraphId) {
            await showAlert({
                title: "Save the board first",
                body: "A profile points at a saved board, so this board needs to be saved before it can become one.",
            });
            return;
        }
        if (graphDirty) {
            await showAlert({
                title: "Unsaved edits",
                body: "Save this board before creating a profile, or the profile would point at the version on the server rather than what you see.",
            });
            return;
        }
        const displayName = await askName({
            title: "Save as profile",
            body: "A profile remembers this board plus its trained model, so a participant can be resumed in one click.",
            label: "Profile name",
            placeholder: "e.g. Alice",
            noun: "profile",
            existing: profiles.map((profile) => ({
                name: profile.display_name,
                hint: profile.participant_id,
            })),
            confirmLabel: "Save profile",
        });
        if (!displayName) {
            return;
        }
        const participantId =
            sanitizeIdentifier(displayName) || `profile-${Date.now()}`;

        // Pull details from the current graph + the board's experiment (which is
        // where the protocol lives now).
        let modelPath = "";
        const protocolId = boundExperimentView?.protocol?.protocol_id ?? "";
        let deviceId = "";
        for (const node of draftGraph.nodes) {
            if (
                node.kind === "transform" &&
                node.transform_kind === "emg_gesture_classify"
            ) {
                const path = node.config?.model_path;
                if (typeof path === "string") {
                    modelPath = path;
                }
            } else if (node.kind === "stream_source" && !deviceId) {
                deviceId = node.stream_id ?? "";
            }
        }

        const nowUs = Date.now() * 1000;
        const existing = profiles.find(
            (profile) => profile.participant_id === participantId,
        );
        saveProfile({
            participant_id: participantId,
            display_name: displayName,
            model_path: modelPath,
            graph_id: selectedGraphId,
            protocol_id: protocolId,
            device_id: deviceId,
            session_ids: existing?.session_ids ?? [],
            best_accuracy: trainAccuracy?.mean_accuracy ?? existing?.best_accuracy ?? 0,
            created_at_us: existing?.created_at_us ?? nowUs,
            updated_at_us: nowUs,
        });
    }

    async function loadProfile(profile: Profile) {
        if (!profile.graph_id) {
            await showAlert({
                title: "This profile has no board",
                body: `"${profile.display_name}" was saved without a board, so there is nothing to open.`,
            });
            return;
        }
        const hasGraph = graphDefinitions.some(
            (graph) => graph.graph_id === profile.graph_id,
        );
        if (!hasGraph) {
            listStreamGraphs();
            await showAlert({
                title: "Refreshing saved boards",
                body: "This profile's board is not in the list yet. Pick the profile again once the list finishes loading.",
            });
            return;
        }
        void selectGraph(profile.graph_id);
    }

    async function removeProfile(profile: Profile) {
        const confirmed = await askConfirm({
            title: `Delete profile "${profile.display_name}"?`,
            body: "The board and the trained model it points at are kept — only the profile entry is removed.",
            confirmLabel: "Delete profile",
            danger: true,
        });
        if (confirmed) {
            deleteProfile(profile.participant_id);
        }
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
        // Never reopen pre-filtered: a palette that opens showing three of
        // seventeen nodes, because of something typed a minute ago, reads as
        // a broken palette rather than a remembered search.
        paletteFilter = "";
        contextMenu = {
            ...contextMenu,
            open: false,
        };
    }

    function handleWindowPointerDown(event: MouseEvent) {
        const target = event.target as HTMLElement | null;
        // Close an open edge-topic badge dropdown on any pointer-down outside it
        // (the badge + menu stop propagation, so those clicks don't reach here).
        if (openBadgeEdgeId && !target?.closest(".edge-badge-wrap")) {
            openBadgeEdgeId = null;
        }
        if (!contextMenu.open) {
            return;
        }
        // Clicks on the menu itself are its own business.
        if (target?.closest(".context-menu")) {
            return;
        }
        // ⚠️ On the canvas, discriminate by BUTTON rather than exempting the canvas
        // wholesale (TEC-NATKIT-71).
        //
        // The canvas used to be exempt entirely, so the only way to dismiss the menu
        // was to click off the canvas — the toolbar or a side panel — which is
        // backwards from how every other context menu behaves.
        //
        // It cannot simply be deleted, though: a right-click fires mousedown
        // (button 2) on the canvas BEFORE the contextmenu event that opens the menu,
        // so treating that press as "click away" would close a menu that is about to
        // open. Left button dismisses; anything else (the opening right-click, a
        // middle-click pan) is left alone.
        if (target?.closest(".graph-canvas") && event.button !== 0) {
            return;
        }
        closeContextMenu();
    }

    /**
     * Add a Stream node.
     *
     * ⚠️ THE STREAM IS OPTIONAL, and that is the point. The palette used to offer
     * one entry PER LIVE STREAM, so the menu changed shape with the rig and a
     * board could not be laid out before the hardware was on. There is one
     * generic "Stream" node now; which stream it carries is chosen from the
     * inspector dropdown, which has always existed.
     *
     * An unbound source is already a first-class state — `stream_id` is optional
     * and OMITTED rather than "" when absent (TEC-NATKIT-66) — so this needed no
     * new concept, only for this function to stop insisting.
     */
    function addSourceNode(
        streamId: string | null = null,
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const stream = streamId
            ? (availableStreams.find((item) => item.streamId === streamId) ?? null)
            : null;
        // ⚠️ Only refuse a stream id that was ASKED FOR and does not exist. A null
        // id is a deliberate "pick it later", not a lookup failure.
        if (streamId && !stream) {
            return;
        }
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = streamId
            ? `source/${sanitizeIdentifier(streamId)}-${Date.now()}`
            : `source/unbound-${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "stream_source",
            label: streamId ? `Stream ${streamId}` : "Stream",
            position: { ...position },
            // ⚠️ OMITTED, not "", when unbound. The backend parses stream_id only
            // if the key is PRESENT and then demands a non-negative integer, so
            // "" makes the whole board unsavable (TEC-NATKIT-66). Same for the
            // schema, which is not known until a stream is chosen.
            ...(streamId ? { stream_id: streamId } : {}),
            ...(stream ? { schema_name: stream.schemaName } : {}),
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
        // A classifier transform (one that loads a model bundle — detected by a
        // model_path config field) can receive a train->classify provenance
        // edge, so it exposes a prov_model input stub alongside its data input.
        const takesModel = capability.config_fields.some(
            (field) => field.id === "model_path",
        );
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
            input_port_ids: takesModel
                ? ["input", PROVENANCE_PORT_MODEL]
                : ["input"],
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
        displayMode?: "imu_calibration",
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `viewer/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "viewer",
            label: displayMode === "imu_calibration" ? "IMU Calibration" : "Viewer",
            position: { ...position },
            input_port_ids: ["input"],
            // A calibration readout is the node's whole point, so it is on by
            // default rather than hidden behind the inline-graph toggle.
            inline_graph: displayMode === "imu_calibration",
            ...(displayMode ? { display_mode: displayMode } : {}),
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
            // ⚠️ ONE output, carrying BOTH types. A combine's channel is the
            // per-type union of its inputs (see channelTopicsForNode), so when
            // markers are wired in they are already in this channel — the port
            // relabels itself "data and markers" and the link renders as a blue
            // and a violet line running together. A previous pass grew a second
            // `markers` port instead, which split one channel into two ports
            // that nothing downstream treated as separate.
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
    // A frontend-only palette entry (the same trick composites use). It creates a
    // viewer whose display_mode is imu_calibration -- no new backend node kind, so
    // nothing about graph validation or startup changes.
    const IMU_CALIBRATION_ENTRY: NodeCatalogEntry = {
        kind: "viewer",
        node_type: "imu_calibration",
        label: "IMU Calibration",
        description:
            "Shows whether the upstream IMU is calibrated while worn: " +
            "accelerometer, gyroscope and rotation accuracy, worst-case overall.",
    } as NodeCatalogEntry;

    const utilityCatalog = $derived([
        ...nodeCatalog.filter(
            (entry) =>
                entry.kind !== "stream_source" && entry.kind !== "transform",
        ),
        IMU_CALIBRATION_ENTRY,
    ]);

    // Dispatch a catalog entry to the matching node-creation path. Structural
    // kinds keep their bespoke creation (ports, stream binding); this is the
    // one place that maps catalog kind → constructor.
    function addCatalogNode(
        entry: NodeCatalogEntry,
        position?: StreamGraphPosition,
    ) {
        if (entry.node_type === "imu_calibration") {
            addViewerNode(position, "imu_calibration");
        } else if (entry.kind === "viewer") {
            addViewerNode(position);
        } else if (entry.kind === "sink") {
            addSinkNode(position);
        } else if (entry.kind === "combine") {
            addCombineNode(position);
        } else if (entry.kind === "transform") {
            addTransformNode(entry.node_type, position);
        } else if (entry.kind === "markers") {
            addMarkersNode(position);
        } else if (entry.kind === "train") {
            addTrainNode(position);
        } else if (entry.kind === "export") {
            addExportNode(position);
        }
    }

    function buildDefaultExportConfig(): ExportNodeConfig {
        return {
            format: "parquet",
            label_field: "label",
            run_index: null,
        };
    }

    // Terminal + variadic: two data inputs by default so a data stream and an
    // experiment's markers can both be wired in without adding a port first.
    function addExportNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `export/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "export",
            label: "Export",
            position: { ...position },
            // ⚠️ NAMED, not in1/in2. This node needs two SPECIFIC and different
            // things — a data stream for the rows, an experiment's markers for
            // the session window and the label joined onto each row — and the
            // backend already distinguishes them (ParquetExport takes an explicit
            // markerStreamId). Ports called in1/in2 said none of that, and wiring
            // them the wrong way round yields a Parquet file with an empty label
            // column, which reads as a successful export.
            input_port_ids: ["data", "markers"],
            output_port_ids: [],
            config: buildDefaultExportConfig(),
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
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
            // Runs are picked in the inspector (scoped to the board's experiment);
            // the models flow out of prov_models into a classify node.
            input_port_ids: [],
            output_port_ids: [PROVENANCE_PORT_MODELS],
            config: buildDefaultTrainConfig(),
        });
        selectedNodeId = nodeId;
        selectedNodeIds = new Set([nodeId]);
        selectedEdgeId = null;
        closeContextMenu();
        markDraftChanged(nextGraph);
    }

    // Source-like and config-less: no inputs, and its single `markers` output
    // carries the BOUND experiment's cue/session marker stream downstream. There
    // is nothing to author on it — it follows whichever experiment owns the board.
    function addMarkersNode(
        position: StreamGraphPosition = contextMenu.open
            ? contextMenu.graphPosition
            : getDefaultInsertionPosition(),
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const nodeId = `markers/${Date.now()}`;
        nextGraph.nodes.push({
            id: nodeId,
            kind: "markers",
            label: "Markers",
            position: { ...position },
            input_port_ids: [],
            output_port_ids: ["markers"],
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
        if (kind === "markers" || kind === "experiment") return CircleDot;
        if (kind === "train") return Cpu;
        if (kind === "export") return FileDown;
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
        if (boardIsImmutable) {
            // Refuse the drag outright rather than letting the node follow the
            // cursor and snap back when markDraftChanged declines it.
            return;
        }
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
            markViewStateChanged(nextGraph);
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
        markViewStateChanged(nextGraph);
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

        // Provenance (lineage/control) edge? An edge is provenance when either
        // endpoint is a provenance-typed port. A node's data output may originate
        // one (the source-tap end, e.g. source→experiment or experiment→train); a
        // provenance OUTPUT (train's models) must land on a provenance input.
        // These edges are dropped from the executed graph — they resolve node
        // config, not data flow — so they skip the data-edge compatibility rules
        // below and never dedupe by target port (a train may bind several).
        const targetIsProvenance = isProvenancePort(portId);
        const sourceIsProvenance = isProvenancePort(connection.portId);
        if (targetIsProvenance || sourceIsProvenance) {
            if (sourceIsProvenance && !targetIsProvenance) {
                connectionMessage =
                    "⚠ A model output connects only to a model input.";
                pendingConnection = null;
                return;
            }
            const nextGraph = cloneGraph(draftGraph);
            nextGraph.edges.push({
                id: `edge-${Date.now()}`,
                source_node_id: connection.nodeId,
                source_port: connection.portId,
                target_node_id: nodeId,
                target_port: portId,
                edge_kind: "provenance",
            });
            connectionMessage = null;
            pendingConnection = null;
            markDraftChanged(nextGraph);
            return;
        }

        // A marker stream (an experiment's `markers` output) is discrete events,
        // not a numeric frame — a transform can't process it. Combine, however,
        // is now a topic-aware merger (Part B): markers feed its marker lane and
        // bundle with data into a "stream" channel, so only transform is blocked.
        const connectSource = draftGraph.nodes.find(
            (n) => n.id === connection.nodeId,
        );
        const connectTarget = draftGraph.nodes.find((n) => n.id === nodeId);
        if (
            (connectSource?.kind === "markers" ||
                connectSource?.kind === "experiment") &&
            connectTarget?.kind === "transform"
        ) {
            connectionMessage = `⚠ Markers can't feed a ${connectTarget.kind}. Combine them with a data stream, wire the markers into a viewer, or use the timeline.`;
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

    // --- Experiment actions --------------------------------------------------
    // save_experiment is the only writer of the experiment<->board pair, so every
    // one of these is a save. The board must already exist in the graph store for
    // the backend to stamp it, so a dirty/new board is saved FIRST — WS messages
    // are processed in order, which is what makes that safe rather than racy.
    function persistExperiment(experiment: Experiment): void {
        if (graphDirty || !selectedGraphRecord) {
            saveDraftGraph();
        }
        saveExperiment(experiment);
    }

    function bindExperiment(experimentId: string): void {
        flushExperimentEdit();
        if (!experimentId) {
            // Unbind: clear live_graph_id on whichever experiment holds this board.
            const current = boundExperiment;
            if (current) {
                persistExperiment({ ...current, live_graph_id: "" });
            }
            return;
        }
        const target = experiments.find(
            (experiment) => experiment.experiment_id === experimentId,
        );
        if (!target) {
            return;
        }
        persistExperiment({ ...target, live_graph_id: selectedGraphId });
    }

    async function createExperiment(): Promise<void> {
        flushExperimentEdit();
        if (!selectedGraphId) {
            await showAlert({
                title: "Pick a board first",
                body: "An experiment owns a board and its recorded history, so it needs one to bind to. Create or select a board, then try again.",
            });
            return;
        }
        const label = await askName({
            title: "New experiment",
            body: "The experiment owns this board and every recording made from it.",
            label: "Experiment name",
            placeholder: "e.g. Finger counting",
            noun: "experiment",
            // Shown and filtered as you type, so a name that collides with one
            // you already have is obvious before it is created.
            existing: experiments.map((experiment) => ({
                name: experiment.label || experiment.experiment_id,
                hint:
                    experiment.live_graph_id === selectedGraphId
                        ? "on this board"
                        : (experiment.live_graph_id || "no board"),
            })),
            confirmLabel: "Create experiment",
        });
        if (!label) {
            return;
        }
        const experimentId =
            sanitizeIdentifier(`${label}-${Date.now()}`) ||
            `experiment-${Date.now()}`;
        const nowUs = Date.now() * 1000;
        persistExperiment({
            experiment_id: experimentId,
            label,
            // Filed into the workspace in view (TEC-NATKIT-56), or it would be
            // created into Unfiled and vanish from the list being looked at.
            workspace_id: selectedWorkspaceId ?? "",
            protocol: { ...FINGER_COUNTING_PROTOCOL },
            notes: "",
            live_graph_id: selectedGraphId,
            created_at_us: nowUs,
            updated_at_us: nowUs,
        });
        showExperimentPanel = true;
        // A brand-new experiment's next step is authoring its protocol, so open
        // the designer straight away (it renders once the bind lands).
        showExperimentDesigner = true;
    }

    function patchBoundExperiment(patch: Partial<Experiment>): void {
        const current = boundExperimentView;
        if (!current) {
            return;
        }
        queueExperimentEdit({ ...current, ...patch });
    }

    function patchBoundProtocol(patch: Partial<SessionProtocol>): void {
        const current = boundExperimentView;
        if (!current?.protocol) {
            return;
        }
        queueExperimentEdit({
            ...current,
            protocol: { ...current.protocol, ...patch },
        });
    }

    function formatDuration(seconds: number): string {
        if (seconds < 60) {
            return `${seconds}s`;
        }
        if (seconds < 3600) {
            return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        }
        if (seconds < 86400) {
            return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
        }
        return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
    }

    function formatWindow(startUs?: number, endUs?: number | null): string {
        if (!startUs) {
            return "—";
        }
        const start = new Date(startUs / 1000);
        const durationS = endUs ? Math.round((endUs - startUs) / 1_000_000) : null;
        return `${start.toLocaleString()}${
            durationS !== null ? ` · ${formatDuration(durationS)}` : ""
        }`;
    }

    // Replay controls for the open instance.
    let replayMode = $state<"review" | "recompute">("review");
    let replaySpeed = $state(1);

    const replayForSelectedInstance = $derived(
        selectedInstance && activeReplay?.graph_id === selectedInstance.graph_id
            ? activeReplay
            : null,
    );

    // Mirrors what the Instance panel requires to offer Replay: there has to be a
    // materialised data artifact to stream back. Used by the toolbar, which shows
    // Replay in place of Start on a sealed recording.
    const canReplaySelectedInstance = $derived(
        (selectedInstance?.recording?.artifacts?.data?.length ?? 0) > 0,
    );

    function replaySelectedInstance() {
        const instance = selectedInstance;
        if (!instance) {
            return;
        }
        // The page starts the graph against the replay once the backend confirms the
        // scratch topic exists — doing it here would race the topic's creation.
        startInstanceReplay(instance.graph_id, replayMode, replaySpeed);
    }

    function stopSelectedReplay() {
        const replay = replayForSelectedInstance;
        if (!replay) {
            return;
        }
        stopInstanceReplay(replay.replay_id);
        // Stop the pipeline too: leaving workers bound to a topic that is about to be
        // deleted would strand them on a stream that no longer exists.
        stopStreamGraph(replay.graph_id);
    }

    function forkSelectedInstance() {
        const instance = selectedInstance;
        if (!instance) {
            return;
        }
        forkStreamGraph(instance.graph_id);
    }

    // Download a MATERIALIZED artifact. Deliberately not the Kafka-draining export
    // endpoint: an instance exists precisely because its data has left the broker.
    function artifactDownloadUrl(graphId: string, path: string): string {
        const params = new URLSearchParams({ graph_id: graphId, path });
        return `/api/instances/artifact?${params}`;
    }

    // Deleting an instance destroys recorded data, so a SEALED one needs a second,
    // explicit confirmation and the backend's force flag — a mis-click must not be
    // able to erase history.
    async function deleteInstance(
        graphId: string,
        immutable: boolean,
    ): Promise<void> {
        const instance = graphDefinitions.find(
            (graph) => graph.graph_id === graphId,
        );
        const label = instance?.instance_id ?? graphId;
        const confirmed = await askConfirm({
            title: immutable
                ? `Permanently delete recording "${label}"?`
                : `Delete instance "${label}"?`,
            body: immutable
                ? "This is sealed recorded history. Deleting it cannot be undone."
                : "This instance is editable, so nothing recorded is lost.",
            points: immutable
                ? [
                      "Its Parquet data files are deleted from disk.",
                      "Its marker timeline is deleted.",
                      "Any model trained from it will lose its lineage.",
                  ]
                : undefined,
            confirmLabel: immutable ? "Delete permanently" : "Delete instance",
            danger: true,
        });
        if (!confirmed) {
            return;
        }
        deleteStreamGraph(graphId, immutable);
    }

    async function deleteBoundExperiment(): Promise<void> {
        const current = boundExperiment;
        if (!current) {
            return;
        }
        discardExperimentEdit();
        const confirmed = await askConfirm({
            title: `Delete experiment "${current.label || current.experiment_id}"?`,
            body: "Its protocol and participant details are removed. The board it owns, and any data already recorded, are kept.",
            confirmLabel: "Delete experiment",
            danger: true,
        });
        if (confirmed) {
            deleteExperiment(current.experiment_id);
        }
    }

    // Migration (Phase 1): lift a legacy `experiment` node's protocol into a
    // stored experiment bound to this board, and swap the node for a `markers`
    // source IN PLACE — same node id, so every edge it fed survives untouched.
    async function convertExperimentNode(
        node: StreamGraphExperimentNode,
    ): Promise<void> {
        if (!selectedGraphId) {
            await showAlert({
                title: "Save the board first",
                body: "Converting binds a stored experiment to this board, which needs the board to exist on the server. Save it, then convert.",
            });
            return;
        }
        const config = node.config;
        const experimentId =
            sanitizeIdentifier(config.experiment_id ?? "") ||
            sanitizeIdentifier(`${node.label}-${Date.now()}`) ||
            `experiment-${Date.now()}`;
        const nowUs = Date.now() * 1000;
        const existing = experiments.find(
            (experiment) => experiment.experiment_id === experimentId,
        );

        const nextGraph = cloneGraph(draftGraph);
        for (let index = 0; index < nextGraph.nodes.length; index += 1) {
            if (nextGraph.nodes[index].id !== node.id) {
                continue;
            }
            const previous = nextGraph.nodes[index];
            nextGraph.nodes[index] = {
                id: previous.id,
                kind: "markers",
                label: "Markers",
                position: { ...previous.position },
                input_port_ids: [],
                output_port_ids: ["markers"],
                ...(previous.width !== undefined ? { width: previous.width } : {}),
                ...(previous.height !== undefined
                    ? { height: previous.height }
                    : {}),
            };
        }
        markDraftChanged(nextGraph);
        // Order matters: the graph save carries the new markers node, then the
        // experiment save binds the board and lands the protocol.
        saveDraftGraph();
        saveExperiment({
            experiment_id: experimentId,
            label: config.protocol?.label || node.label || experimentId,
            workspace_id: selectedWorkspaceId ?? "",
            protocol: config.protocol ?? { ...FINGER_COUNTING_PROTOCOL },
            // Legacy experiment-NODE migration: the node's config predates both
            // the participant-per-run move and workspaces, so this preserves an
            // old participant into the deprecated field (which the TEC-NATKIT-54
            // back-fill reads) rather than dropping it.
            participant_id: config.participant_id ?? "",
            notes: config.notes ?? "",
            live_graph_id: selectedGraphId,
            created_at_us: existing?.created_at_us ?? nowUs,
            updated_at_us: nowUs,
        });
        showExperimentPanel = true;
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

    function updateExportConfig(patch: Partial<ExportNodeConfig>) {
        updateSelectedNode((node) => {
            if (node.kind !== "export") {
                return node;
            }
            return { ...node, config: { ...node.config, ...patch } };
        });
    }

    // Download the parquet straight from the backend. The whole export runs in
    // C++ (drain the channel, join the cue labels, write the file) and comes
    // back as an attachment — no control-plane hop, no server-side artifact.
    async function downloadExportForNode(node: StreamGraphExportNode) {
        const streamId = exportChannelStreamId;
        if (!streamId) {
            return;
        }
        const params = new URLSearchParams({ stream_id: streamId });
        if (exportMarkerStreamId) {
            params.set("marker_stream_id", exportMarkerStreamId);
        }
        if (node.config.label_field) {
            params.set("label_field", node.config.label_field);
        }
        if (node.config.run_index) {
            params.set("run_index", String(node.config.run_index));
        }

        exportDownload = { status: "downloading", message: "Exporting…" };
        try {
            const response = await fetch(`/api/export/parquet?${params}`, {
                credentials: "same-origin",
            });
            if (!response.ok) {
                // The backend answers failures as JSON with an actionable message
                // (empty window, wrong schema, retention gap) — surface it as-is.
                let message = `Export failed (HTTP ${response.status})`;
                try {
                    const body = await response.json();
                    if (body?.message) {
                        message = body.message;
                    }
                } catch {
                    /* non-JSON body: keep the status message */
                }
                exportDownload = { status: "failed", message };
                return;
            }

            const header = (name: string) => response.headers.get(name);
            const disposition = header("Content-Disposition") ?? "";
            const match = /filename="([^"]+)"/.exec(disposition);
            const fileName = match?.[1] ?? `stream-${streamId}.parquet`;

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = fileName;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);

            const toCount = (value: string | null) =>
                value === null ? null : Number(value);
            exportDownload = {
                status: "downloaded",
                message: `Downloaded ${fileName}`,
                fileName,
                sessionId: header("X-Natkit-Session-Id") ?? undefined,
                frameCount: toCount(header("X-Natkit-Frame-Count")),
                labelledFrameCount: toCount(header("X-Natkit-Labelled-Frame-Count")),
                markerCount: toCount(header("X-Natkit-Marker-Count")),
                truncated: header("X-Natkit-Truncated") === "true",
            };
        } catch (error) {
            exportDownload = {
                status: "failed",
                message: `Export request failed: ${
                    error instanceof Error ? error.message : String(error)
                }`,
            };
        }
    }

    // The run selector the train pipeline expects: "<session-id>:<run-index>".
    function runSelector(run: RecordedRunSummary): string {
        return `${run.session_id}:${run.run_index}`;
    }

    // Toggle a discovered run in/out of the selected train node's train_runs or
    // eval_runs — click a run in the picker instead of typing "session:run".
    function toggleRunSelection(run: RecordedRunSummary, list: "train" | "eval") {
        if (!selectedTrainNode) {
            return;
        }
        const selector = runSelector(run);
        const key = list === "train" ? "train_runs" : "eval_runs";
        const current = selectedTrainNode.config[key];
        const next = current.includes(selector)
            ? current.filter((entry) => entry !== selector)
            : [...current, selector];
        updateTrainConfig({ [key]: next });
    }

    // --- Session recording (Phase 4, slice C) -------------------------------
    // Recording is client-side: run the protocol cue timeline and publish the
    // session bundle (metadata + lifecycle + cue markers) via the backend under
    // one session_id spanning every recorded upstream stream. The raw sensor
    // data is already in Kafka (the source/transform streams); the session emits
    // the marker timeline that labels and delimits the runs.
    interface SessionRecordingState {
        experimentId: string;
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
        // A wait step holds the session for an unknown time. The schedule clock is
        // frozen while it holds, so `elapsedMs` stays a protocol time (offsets keep
        // lining up) and this records the wall time spent paused.
        pausedMs: number;
        // Per wait cue_id, how long it actually held. Markers are stamped from
        // offsets at the end, so resolveScheduleWaits() needs these to place
        // everything after a wait at the time it really happened.
        waitHeldMs: Record<number, number>;
        // The wait currently holding, and when it started holding.
        waitingCueId: number | null;
        waitingSinceMs: number | null;
    }
    let sessionRecording = $state<SessionRecordingState | null>(null);
    let sessionRecordTimer: ReturnType<typeof setInterval> | null = null;
    let sessionRecordMessage = $state<string | null>(null);

    // The first wait step the run has reached and nobody has released yet.
    function findPendingWait(
        rec: SessionRecordingState,
        elapsedMs: number,
    ): EmgCueEvent | null {
        return (
            rec.schedule.find(
                (cue) =>
                    cue.wait_for_input === true &&
                    rec.waitHeldMs[cue.cue_id] === undefined &&
                    cue.start_offset_ms <= elapsedMs,
            ) ?? null
        );
    }

    const activeSessionCue = $derived.by(() => {
        if (!sessionRecording) return null;
        // While a wait holds, IT is what the participant is looking at. An
        // interval lookup would return the step before it (or nothing), because a
        // wait has no length until released.
        const pending = findPendingWait(
            sessionRecording,
            sessionRecording.elapsedMs,
        );
        if (pending) return pending;
        return activeCueAtElapsedMs(
            sessionRecording.schedule,
            sessionRecording.elapsedMs,
        );
    });

    // --- Workspaces (TEC-NATKIT-56) ------------------------------------------
    //
    // The selector scopes the boards, experiments and roster the editor sees. The
    // page owns the filtering; this is the surface for choosing and managing.

    // ⚠️ `<select value={...}>` does NOT reliably select an option that is added in
    // the SAME update. Creating a workspace does exactly that — the saved push adds
    // the option while selectWorkspace sets the value — and the control rendered
    // BLANK, with no workspace apparently selected, while the scoping underneath
    // had already switched. Caught by screenshotting it; the type check and the
    // unit tests were both green.
    //
    // Mirroring the prop into local state and using bind:value fixes the ordering:
    // the effect runs after the DOM update that added the option.
    // Starts empty and is synced entirely by the effect, which also runs on mount —
    // seeding it from the prop directly would only capture the initial value, which
    // is what Svelte warns about.
    let workspaceSelectValue = $state("");
    $effect(() => {
        workspaceSelectValue = selectedWorkspaceId ?? "";
    });

    const selectedWorkspace = $derived(
        workspaces.find(
            (workspace) => workspace.workspace_id === selectedWorkspaceId,
        ) ?? null,
    );

    // Everything filed under some OTHER workspace. Shown rather than left
    // implicit: a board list that just got shorter looks like data loss.
    const hiddenTotal = $derived(
        hiddenCounts.experiments + hiddenCounts.graphs + hiddenCounts.profiles,
    );

    // Cohort export (TEC-NATKIT-65): every completed run in this workspace as one
    // tar, straight from the backend's materialized artifacts.
    let cohortDownload = $state<{ status: "idle" | "downloading" | "done" | "failed"; message: string }>({
        status: "idle",
        message: "",
    });

    async function downloadCohort() {
        // The empty id is Unfiled, which is a legitimate thing to export -- so this
        // is a valid request rather than a missing parameter.
        const params = new URLSearchParams({
            workspace_id: selectedWorkspaceId ?? "",
        });
        cohortDownload = { status: "downloading", message: "Collecting runs…" };
        try {
            const response = await fetch(`/api/export/cohort?${params}`, {
                credentials: "same-origin",
            });
            if (!response.ok) {
                cohortDownload = {
                    status: "failed",
                    message:
                        (await response.text()) ||
                        `Cohort export failed (HTTP ${response.status})`,
                };
                return;
            }
            const disposition = response.headers.get("Content-Disposition") ?? "";
            const fileName =
                /filename="([^"]+)"/.exec(disposition)?.[1] ??
                `cohort-${selectedWorkspaceId ?? "unfiled"}.tar`;
            const instances = response.headers.get("X-Natkit-Instance-Count") ?? "?";
            const files = response.headers.get("X-Natkit-File-Count") ?? "?";
            const skipped = response.headers.get("X-Natkit-Skip-Count") ?? "0";
            const mismatches =
                response.headers.get("X-Natkit-Checksum-Mismatch-Count") ?? "0";

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = fileName;
            anchor.click();
            URL.revokeObjectURL(url);

            // ⚠️ The SKIP count is reported here, not only inside the archive. A
            // cohort export that quietly omitted three participants would read as
            // complete, and nobody opens a manifest they have no reason to suspect.
            const parts = [`${instances} run(s), ${files} file(s)`];
            if (Number(skipped) > 0) {
                parts.push(`${skipped} skipped — see MANIFEST.csv`);
            }
            if (Number(mismatches) > 0) {
                parts.push(`⚠️ ${mismatches} checksum mismatch(es)`);
            }
            cohortDownload = { status: "done", message: parts.join(" · ") };
        } catch (error) {
            cohortDownload = {
                status: "failed",
                message: error instanceof Error ? error.message : String(error),
            };
        }
    }

    async function createWorkspace() {
        const label = await askName({
            title: "New workspace",
            body: "A workspace groups a study's boards, experiments and participants, so picking an experiment is not picking from every experiment ever made.",
            label: "Workspace name",
            placeholder: "e.g. Stroke cohort A",
            noun: "workspace",
            existing: workspaces.map((workspace) => ({
                name: workspace.label,
                hint: workspace.workspace_id,
            })),
            confirmLabel: "Create workspace",
        });
        if (!label) return;
        const workspaceId =
            sanitizeIdentifier(label) || `workspace-${Date.now()}`;
        if (
            workspaces.some(
                (workspace) => workspace.workspace_id === workspaceId,
            )
        ) {
            await showAlert({
                title: "Already exists",
                body: `A workspace with the id ${workspaceId} already exists. Pick a different name.`,
            });
            return;
        }
        if (
            saveWorkspace({
                workspace_id: workspaceId,
                label,
                notes: "",
                created_at_us: 0,
                updated_at_us: 0,
            })
        ) {
            // Switch to it: creating a workspace and then still looking at the
            // previous one is never what was meant.
            selectWorkspace(workspaceId);
        }
    }

    async function renameWorkspace() {
        if (!selectedWorkspace) return;
        const label = await askName({
            title: "Rename workspace",
            body: "Only the name changes — its boards, experiments and participants stay exactly where they are.",
            label: "Workspace name",
            initial: selectedWorkspace.label,
            noun: "workspace",
            existing: workspaces
                .filter(
                    (workspace) =>
                        workspace.workspace_id !==
                        selectedWorkspace.workspace_id,
                )
                .map((workspace) => ({
                    name: workspace.label,
                    hint: workspace.workspace_id,
                })),
            confirmLabel: "Rename",
        });
        if (!label || label === selectedWorkspace.label) return;
        // The id is deliberately NOT re-derived from the new name: it is what
        // every member's workspace_id points at, so renaming must not re-file
        // anything.
        saveWorkspace({ ...selectedWorkspace, label });
    }

    async function removeWorkspace() {
        if (!selectedWorkspace) return;
        // These props arrive already scoped to the selected workspace, so their
        // lengths ARE what is filed in the one about to be deleted.
        const counts = [
            experiments.length > 0 ? `${experiments.length} experiment(s)` : null,
            graphDefinitions.length > 0
                ? `${graphDefinitions.length} board(s)`
                : null,
            profiles.length > 0 ? `${profiles.length} participant(s)` : null,
        ].filter(Boolean);
        const confirmed = await askConfirm({
            title: `Delete workspace "${selectedWorkspace.label}"?`,
            // ⚠️ The copy has to say the contents survive. "Delete workspace"
            // reads like it takes everything with it, and an operator who
            // believes that will not press it -- or worse, will press it
            // believing they are cleaning up a cohort's data.
            body:
                counts.length > 0
                    ? `Its ${counts.join(", ")} are NOT deleted — they move to Unfiled, where you can re-file them. Recorded data and history are untouched.`
                    : "It is empty, so nothing moves.",
            confirmLabel: "Delete workspace",
            danger: true,
        });
        if (!confirmed) return;
        deleteWorkspace(selectedWorkspace.workspace_id);
    }

    // --- Sensor body positions (TEC-NATKIT-62) --------------------------------
    //
    // The stream↔limb pairing for THIS board. Derived from the sources rather than
    // stored separately, so there is one owner of the fact and nothing to keep in
    // sync.
    const sourcePositions = $derived(
        draftGraph.nodes
            .filter((node) => node.kind === "stream_source")
            .map((node) => ({
                node_id: node.id,
                stream_id: (node as { stream_id?: string }).stream_id ?? "",
                label: node.label,
                position:
                    (node as { sensor_position?: string }).sensor_position ?? "",
            })),
    );

    // ⚠️ Two streams claiming the same limb is the error worth refusing. A swapped
    // left/right forearm is invisible in the data and cannot be corrected
    // afterwards without knowing it happened; a duplicate is the one form of it a
    // machine can actually see.
    const positionDuplicates = $derived(
        duplicatePositions(sourcePositions.map((entry) => entry.position)),
    );

    const unpositionedSources = $derived(
        sourcePositions.filter((entry) => !isAssignedPosition(entry.position)),
    );

    // What TEC-NATKIT-63's Record gate consumes: null when the mapping is fit to
    // record against, otherwise the reason, worded for the operator.
    const positionMappingProblem = $derived.by(() => {
        if (sourcePositions.length === 0) return null; // no sources: a different problem
        if (positionDuplicates.length > 0) {
            return `Two sensors are both set to ${positionDuplicates.join(", ")}. Give each source its own body position.`;
        }
        if (unpositionedSources.length > 0) {
            const names = unpositionedSources
                .map((entry) => entry.label || entry.stream_id || entry.node_id)
                .join(", ");
            return `No body position set for ${names}. An exported file cannot say which limb the signal came from.`;
        }
        return null;
    });

    // Ask who this run is of. Returns the participant id, or null if the operator
    // backed out (which must abort the recording — see the call site).
    //
    // The roster is `profiles`, which the page has ALREADY scoped to the selected
    // workspace — so a cohort's list is that cohort's participants, not every
    // person the rig has ever seen. In Unfiled it is the unfiled ones.
    async function askParticipantForRun(): Promise<string | null> {
        const chosen = await askName({
            title: "Who is this run of?",
            body: "The participant belongs to the run, not to the experiment — one procedure can record a whole cohort. Pick someone already on the roster, or type a new id for a first session.",
            label: "Participant",
            placeholder: "e.g. P-042",
            noun: "participant",
            existingMeansReuse: true,
            existing: profiles.map((profile) => ({
                name: profile.participant_id,
                hint: profile.display_name,
            })),
            confirmLabel: "Start recording",
        });
        if (chosen === null) {
            return null;
        }
        // Sanitized because it becomes part of session metadata and marker
        // attributes, which are identifier-shaped. An id that sanitizes to nothing
        // is treated as no answer rather than silently recorded as "".
        const participantId = sanitizeIdentifier(chosen);
        if (!participantId) {
            return null;
        }
        // A name typed rather than picked joins this workspace's roster, or the
        // next Record would not offer them and the operator would have to retype
        // the id exactly — which is how one participant becomes two.
        if (
            !profiles.some(
                (profile) => profile.participant_id === participantId,
            )
        ) {
            const nowUs = Date.now() * 1000;
            saveProfile({
                participant_id: participantId,
                display_name: chosen.trim() || participantId,
                workspace_id: selectedWorkspaceId ?? "",
                model_path: "",
                graph_id: "",
                protocol_id: "",
                device_id: "",
                session_ids: [],
                best_accuracy: 0,
                created_at_us: nowUs,
                updated_at_us: nowUs,
            });
        }
        return participantId;
    }

    async function startSessionRecording(experiment: Experiment) {
        if (sessionRecording) {
            return;
        }
        flushExperimentEdit();
        const protocol = experiment.protocol;
        if (!protocol) {
            sessionRecordMessage =
                "This experiment has no protocol — add classes and timing first.";
            return;
        }
        const schedule = scheduleForProtocol(protocol);
        if (schedule.length === 0) {
            sessionRecordMessage =
                "Protocol has no cues — add classes and timing first.";
            return;
        }
        // THE GATE (TEC-NATKIT-63). Before the participant is even asked: there is no
        // point collecting a name for a run that cannot legitimately start.
        if (hardBlockReason) {
            // Hard: an operator error, fixable now, and a run recorded with it is
            // worthless. Stated rather than silently disabling Record — a greyed
            // button with no reason is what sends someone hunting through nodes.
            sessionRecordMessage = hardBlockReason;
            await showAlert({
                title: "Cannot record yet",
                body: hardBlockReason,
            });
            return;
        }
        let calibrationOverride: string | null = null;
        if (calibrationWarning) {
            // Soft: a judgement. A pilot, a bench test, or a rig whose accuracy feed
            // is not configured are all legitimate reasons to go ahead.
            const proceed = await askConfirm({
                title: "Record below the calibration minimum?",
                body: calibrationWarning,
                points: [
                    "The run will be recorded and marked as taken below the minimum, so it can be found again later.",
                ],
                confirmLabel: "Record anyway",
                danger: true,
            });
            if (!proceed) {
                sessionRecordMessage = calibrationWarning;
                return;
            }
            // ⚠️ Recorded IN THE RUN, not merely permitted. A session taken below
            // threshold on purpose is fine; one that cannot be identified afterwards
            // is not — and by then the accuracies that justified the decision are
            // long gone.
            calibrationOverride = calibrationWarning;
        }

        // WHO is asked here, per run, before anything is published or timestamped
        // (TEC-NATKIT-55). It used to be a field on the experiment, which could
        // only ever name the most recent person — so one procedure recording a
        // cohort attributed every run to whoever was typed in last, and editing
        // that field retroactively reassigned the runs already recorded.
        //
        // The roster is the profile store, and a name not in it is accepted: the
        // first session of a new participant has nothing to pick from.
        const participantId = await askParticipantForRun();
        if (participantId === null) {
            // Cancelled. Deliberately NOT a recording with an empty participant:
            // backing out of this dialog has to mean no run, or the dialog is
            // just a speed bump on the way to unattributed data.
            sessionRecordMessage = "Recording cancelled — no participant chosen.";
            return;
        }
        // Deterministic session↔stream binding: stamp the resolved device_id
        // string(s) of every source on the board, so reconstruction reads the
        // right topics directly instead of scanning the broker to guess "the one
        // device active in the session window" — the scan that hung and that
        // breaks with more than one device. Every source is a recorded source now
        // that the experiment owns the graph. Empty (no source, or its device_id
        // not yet seen live) falls back to that window scan as before.
        const streamIds = recordedDeviceIds;
        // Record under the experiment's id so the published markers land on the
        // same Marker/<experiment_id> topic a markers node resolves to.
        const sessionId = sanitizeIdentifier(
            experiment.experiment_id ||
                buildDefaultSessionId(protocol.protocol_id || "experiment"),
        );
        // AFTER the participant dialog: a dialog the operator sat in front of for
        // twenty seconds would otherwise put the session's start twenty seconds
        // before its first cue.
        const startedAtEpochMs = Date.now();
        const startedAtUs = startedAtEpochMs * 1000;
        const notes = experiment.notes ?? "";
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
            experimentId: experiment.experiment_id,
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
            pausedMs: 0,
            waitHeldMs: {},
            waitingCueId: null,
            waitingSinceMs: null,
        };
        // Mint the instance: the backend snapshots the board and opens the window
        // at the SAME timestamp the markers are stamped with, so the snapshot's
        // window and its marker timeline describe one run.
        startExperimentInstance(
            experiment.experiment_id,
            startedAtUs,
            participantId,
            // Only the sources that actually state a position: an "N/A" recorded as
            // if it were a placement would be worse than its absence.
            sourcePositions
                .filter((entry) => isAssignedPosition(entry.position))
                .map((entry) => ({
                    stream_id: entry.stream_id,
                    position: entry.position,
                })),
            calibrationOverride,
        );
        sessionRecordMessage = `Recording markers as ${sessionId}…`;
        sessionRecordTimer = setInterval(tickSessionRecording, 100);
    }

    function tickSessionRecording() {
        const rec = sessionRecording;
        if (!rec) {
            return;
        }
        const wallMs = Date.now() - rec.startedAtEpochMs;
        const elapsedMs = wallMs - rec.pausedMs;

        // A wait step blocks until released. Freeze the protocol clock at the
        // wait's own start offset and let `pausedMs` absorb the wall time instead:
        // that keeps every later offset lining up with the schedule as compiled,
        // so cue lookups stay correct without rewriting the timeline mid-run.
        //
        // Found by scanning rather than via activeCueAtElapsedMs: a wait is a
        // ZERO-LENGTH window (start == end until it is released), which an
        // interval lookup can never report as active. Offsets are monotonic and
        // waits release in order, so the first unreleased wait we have reached is
        // the one holding.
        const cue = findPendingWait(rec, elapsedMs);
        if (cue) {
            sessionRecording = {
                ...rec,
                elapsedMs: cue.start_offset_ms,
                pausedMs: wallMs - cue.start_offset_ms,
                waitingCueId: cue.cue_id,
                waitingSinceMs:
                    rec.waitingCueId === cue.cue_id ? rec.waitingSinceMs : wallMs,
            };
            return;
        }

        sessionRecording = {
            ...rec,
            elapsedMs,
            waitingCueId: null,
            waitingSinceMs: null,
        };
        if (elapsedMs >= rec.durationMs) {
            finishSessionRecording(true);
        }
    }

    // Play a step's sound once, at its onset.
    //
    // This lives with the SESSION rather than in the runner component: the runner
    // is only mounted when someone has opened a run surface, so putting it there
    // meant a protocol's audio silently did not play if the operator was driving
    // the session from the experiment panel. A stimulus is part of the run, not of
    // one particular view of it.
    let lastSoundedCueId: number | null = null;
    $effect(() => {
        if (!sessionRecording) {
            lastSoundedCueId = null;
            return;
        }
        const cue = activeSessionCue;
        if (!cue || cue.cue_id === lastSoundedCueId) {
            return;
        }
        lastSoundedCueId = cue.cue_id;
        if (!cue.audio_url) {
            return;
        }
        // Autoplay is permitted because starting a session is a user gesture. A
        // failure must never interrupt the run, so it is reported, not thrown.
        const sound = new Audio(cue.audio_url);
        sound.play().catch((error) => {
            console.warn(`Cue audio failed (${cue.audio_url}):`, error);
        });
    });

    // Release the wait the session is holding on.
    function continueSessionWait() {
        const rec = sessionRecording;
        if (!rec || rec.waitingCueId === null) {
            return;
        }
        const wallMs = Date.now() - rec.startedAtEpochMs;
        const heldMs = Math.max(0, wallMs - (rec.waitingSinceMs ?? wallMs));
        sessionRecording = {
            ...rec,
            waitHeldMs: { ...rec.waitHeldMs, [rec.waitingCueId]: heldMs },
            waitingCueId: null,
            waitingSinceMs: null,
        };
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
        // Offsets are relative to the session start, but a wait step displaced
        // everything after it by however long it actually held. Resolve that
        // before stamping markers, or the recorded timeline disagrees with the
        // data it is meant to describe.
        const resolvedSchedule = resolveScheduleWaits(
            rec.schedule,
            rec.waitHeldMs,
        );
        const cueMarkers = buildCueMarkerPayloads({
            sessionId: rec.sessionId,
            cues: resolvedSchedule,
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
            ? `Recorded ${rec.sessionId} markers; materializing…`
            : `Stopped ${rec.sessionId} early; materializing the partial run…`;
        sessionRecording = null;

        // Close the instance window and materialize. Delayed a beat so the markers
        // published just above have landed in Kafka before the exporter drains the
        // topic — the same reason the recorded-runs refresh below waits.
        const instanceGraphId = recordingInstanceGraphId;
        if (instanceGraphId) {
            setTimeout(
                () =>
                    finishExperimentInstance(instanceGraphId, endedAtUs, completed),
                1200,
            );
        } else {
            sessionRecordMessage =
                (sessionRecordMessage ?? "") +
                " (no instance was minted, so nothing was materialized — the markers " +
                "are still on the broker.)";
        }

        // Auto-refresh the Experiments library so the just-recorded run shows up
        // for the Train node without a manual refresh. Delay a beat so the
        // markers have landed in Kafka and the marker topic exists before
        // discover_runs scans (it lists broker topics + reads their history).
        setTimeout(() => requestRecordedRuns(), 1500);
    }

    // Phase 7 incremental reactivity: when a transform config changes while the
    // graph is RUNNING, debounce then save the new config and restart only that
    // node's downstream subgraph — no manual stop/start. Debounced so a slider
    // drag doesn't thrash the hot path.
    let reactiveRestartTimer: ReturnType<typeof setTimeout> | null = null;
    function scheduleReactiveRestart(nodeId: string | null) {
        // Fire while the graph is active — both "running" and "stalled" count. A
        // graph whose classify node is idle-waiting-for-a-model reports "stalled",
        // and that's exactly when a train job auto-fills the model path and we
        // need to restart the node to pick it up.
        const runState = selectedGraphStatus?.run_state;
        if (!nodeId || (runState !== "running" && runState !== "stalled")) {
            return;
        }
        // Phase 7's auto-save would otherwise fire on every keystroke against a
        // sealed instance and spray rejections.
        if (boardIsImmutable) {
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

    // Manually restart the selected node (+ its downstream) without stopping the
    // whole graph — e.g. to apply a just-filled model path to a stalled classify
    // node. Saves any pending edits first so the restarted node uses them.
    function restartSelectedNode() {
        const nodeId = selectedNodeId;
        const graphId = draftGraph.graph_id;
        if (!nodeId || !graphId) {
            return;
        }
        if (graphDirty) {
            saveDraftGraph();
        }
        restartStreamGraphNode(graphId, nodeId);
    }

    const selectedGraphActive = $derived(
        selectedGraphStatus?.run_state === "running" ||
            selectedGraphStatus?.run_state === "stalled",
    );

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

    // Config for a catalog-configured node. Restarting is required for the same
    // reason a transform's config change is: the worker's state — a joiner's
    // queues and tick phase, a detector's pending candidate, a gate's open
    // window and buffered frames — belongs to the old settings and cannot be
    // re-policied in place.
    function updateCatalogConfigField(
        field: TransformCapabilityConfigField,
        rawValue: string,
    ) {
        updateSelectedNode((node) => {
            if (!CATALOG_CONFIG_KINDS.includes(node.kind)) {
                return node;
            }
            const current =
                (node as { config?: Record<string, unknown> }).config ?? {};
            const nextConfig: Record<string, number | string> = {
                ...(current as Record<string, number | string>),
            };
            nextConfig[field.id] =
                field.type === "number" ? Number(rawValue) : rawValue;
            return { ...node, config: nextConfig } as typeof node;
        });
        scheduleReactiveRestart(selectedNodeId);
    }

    // Phase 2: when a train job completes, auto-fill the resulting bundle path
    // into classify nodes so the operator never pastes a model path. Only fills
    // nodes whose model_path is empty, preserving a manually-edited path or one
    // loaded from a saved profile. emg_gesture_classify gets the self-describing
    // bundle; a legacy lda_classify node gets the raw LDA model path.
    let lastAutoFilledBundlePath: string | null = null;
    function autofillClassifyModelPath(
        bundlePath: string,
        ldaModelPath: string | null,
    ) {
        const nextGraph = cloneGraph(draftGraph);
        const restartNodeIds: string[] = [];
        for (const node of nextGraph.nodes) {
            if (node.kind !== "transform") {
                continue;
            }
            const path =
                node.transform_kind === "emg_gesture_classify"
                    ? bundlePath
                    : node.transform_kind === "lda_classify"
                      ? ldaModelPath
                      : null;
            if (!path) {
                continue;
            }
            const current = node.config?.model_path;
            if (typeof current === "string" && current.trim().length > 0) {
                continue;
            }
            node.config = { ...node.config, model_path: path };
            restartNodeIds.push(node.id);
        }
        if (restartNodeIds.length > 0) {
            markDraftChanged(nextGraph);
            for (const nodeId of restartNodeIds) {
                scheduleReactiveRestart(nodeId);
            }
        }
    }

    $effect(() => {
        const bundlePath = trainBundlePath;
        if (!bundlePath || bundlePath === lastAutoFilledBundlePath) {
            return;
        }
        lastAutoFilledBundlePath = bundlePath;
        autofillClassifyModelPath(bundlePath, trainModelPath);
    });

    // Phase 4: the train node whose job we most recently submitted, so a
    // completed job can be recorded onto the right node's model list.
    let pendingTrainNodeId: string | null = null;
    function submitTrainJobForNode(node: StreamGraphTrainNode) {
        pendingTrainNodeId = node.id;
        submitTrainJob(node.config);
    }

    // Associate each completed train job with the submitting train node: append
    // it to that node's config.models (deduped by job_id) so it round-trips
    // through editor_metadata and a train→classify provenance edge can offer it
    // in a re-selectable model dropdown.
    let lastRecordedTrainJobId: string | null = null;
    $effect(() => {
        const job = completedTrainJob;
        if (!job || job.job_id === lastRecordedTrainJobId) {
            return;
        }
        lastRecordedTrainJobId = job.job_id;
        const nodeId = pendingTrainNodeId;
        if (!nodeId) {
            return;
        }
        const nextGraph = cloneGraph(draftGraph);
        const target = nextGraph.nodes.find(
            (n) => n.id === nodeId && n.kind === "train",
        ) as StreamGraphTrainNode | undefined;
        if (!target) {
            return;
        }
        const existing = target.config.models ?? [];
        if (existing.some((m) => m.job_id === job.job_id)) {
            return;
        }
        target.config = {
            ...target.config,
            models: [...existing, { ...job }],
        };
        markDraftChanged(nextGraph);
    });

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
        if (boardIsImmutable) {
            // The backend rejects this anyway; not sending it keeps a normal action
            // from producing an error toast the user can do nothing about.
            connectionMessage =
                "This is an immutable recording — fork it to make changes.";
            return;
        }
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
        if (!draftGraph.graph_id) {
            return;
        }
        // A sealed recording has no live input: starting it would point its sources
        // at whatever is on the broker NOW, which is the opposite of what the panel
        // promises ("Replays from the Parquet on disk, not the broker"). Replay is
        // the control for a recording; Start is for live boards and forks.
        if (boardIsImmutable) {
            connectionMessage =
                "This is a recorded snapshot — use Replay (in the Instance panel) " +
                "to run it against its recording, or fork it to edit and run live.";
            return;
        }
        // Persist any unsaved edits first — the backend starts the STORED graph,
        // so starting a dirty draft (e.g. right after a train job auto-filled the
        // classifier's model path) would otherwise run the stale saved version.
        // Messages are processed in order on the connection, so save-then-start
        // is safe.
        if (graphDirty) {
            saveDraftGraph();
        }
        startStreamGraph(draftGraph.graph_id);
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

    async function createCompositeFromSelection() {
        if (selectedNodeIds.size === 0) {
            return;
        }
        const label = await askName({
            title: "Group into a composite",
            body: `${selectedNodeIds.size} selected node${selectedNodeIds.size === 1 ? "" : "s"} will become one reusable node you can drop onto any board.`,
            label: "Composite name",
            placeholder: "e.g. EMG preprocessing",
            initial: "New composite",
            noun: "composite",
            existing: compositeTemplates.map((template) => ({
                name: template.label,
                hint: `${template.nodes.length} nodes`,
            })),
            confirmLabel: "Create composite",
        });
        if (!label) {
            return;
        }
        const result = extractCompositeFromSelection(
            draftGraph,
            selectedNodeIds,
            label,
        );
        if (!result) {
            await showAlert({
                title: "This selection cannot be grouped",
                body: "Composites cannot contain other composites yet. Ungroup any composite in the selection first, or leave it out.",
            });
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

    // A modal's Escape handler only fires while focus is inside the overlay, so
    // an unfocused dialog ignores Escape until you happen to click it. Panels
    // already carry tabindex="-1" for exactly this; move focus there on open.
    function focusOnOpen(element: HTMLElement) {
        element.focus();
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

    // ⚠️ Runtime FIRST, config second, and the order matters. A running graph may
    // have rebound a source to a replay's scratch topic (`replay_id`), so its
    // runtime output_stream_id is the truth whenever there is one. The config
    // fallback is what lets a source be watched before Run is ever pressed
    // (TEC-NATKIT-98) -- it must not override a live rebinding.
    function viewableStreamId(nodeId: string | null): string | null {
        if (!nodeId) return null;
        const running = nodeRuntimeStatus(nodeId)?.output_stream_id;
        if (running) return String(running);
        return resolveSourceView(nodeId, draftGraph.nodes, draftGraph.edges)
            .streamId;
    }

    const expandedViewerStreamId = $derived(
        viewableStreamId(expandedViewerNodeId),
    );

    // --- Device controls, DISCOVERED (TEC-NATKIT-10) -------------------------
    //
    // ⚠️ NOTHING IS DECLARED HERE ANY MORE. Every control comes from the device's
    // own advertisement, forwarded by the backend with its words already resolved
    // against the registry. The hardcoded catalogue this replaced is what put
    // four BNO08x report toggles on a Muse node and left "Read from device"
    // timing out against hardware that has no such command.
    /** `Left Hand (13793649671244)`, or the bare id. One function, every site. */
    function displayStream(streamId: string | number | null | undefined): string {
        return streamDisplayName(streamId, streamAliases, streamDeviceNames);
    }

    const selectedNodeControlStreamId = $derived(
        selectedNode?.kind === "stream_source"
            ? viewableStreamId(selectedNode.id)
            : null,
    );

    const selectedNodeControlsEntry = $derived(
        selectedNodeControlStreamId
            ? (deviceHealth?.device_controls?.find(
                  (entry) => entry.device_id === selectedNodeControlStreamId,
              ) ?? null)
            : null,
    );

    const resolvedControls = $derived(resolveControls(selectedNodeControlsEntry));

    const selectedNodeControlAnswer = $derived(
        selectedNodeControlStreamId
            ? (deviceCommandResults[selectedNodeControlStreamId] ?? null)
            : null,
    );

    function controlPending(command: string | undefined): boolean {
        if (!selectedNodeControlStreamId || !command) return false;
        return (
            deviceCommandPending[
                `${selectedNodeControlStreamId}:${command}`
            ] === true
        );
    }

    // ⚠️ A recording pins the schema. Changing what a sensor collects partway
    // through would change the recording's shape mid-run, so the backend refuses
    // it — and the control is shown DISABLED WITH THE REASON rather than hidden,
    // because a control that silently fails is worse than one that explains.
    const controlsLockedByRecording = $derived(recordingInstanceGraphId !== null);

    // ⚠️ Device truth only. `null` means "never asked", which is a real state and
    // NOT the same as everything being off — a disabled sensor and one that has
    // not reported are identical in a frame, so this can never be inferred from
    // the data.
    let toggleStates = $state<Record<string, Record<string, boolean> | null>>({});
    let toggleError = $state<string | null>(null);

    $effect(() => {
        const answer = selectedNodeControlAnswer;
        if (!answer) return;
        for (const group of resolvedControls.toggleGroups) {
            if (!answerCarriesGroupState(group, answer.command)) continue;
            const message = answer.records.at(-1)?.message ?? "";
            const parsed = parseToggleStates(group.toggles, message);
            if (parsed) {
                toggleStates = { ...toggleStates, [group.group]: parsed };
                // A refusal still reports the CURRENT state, which is why the
                // state and the error come from the same answer.
                toggleError = answer.ok ? null : message;
            } else {
                toggleError = answer.error ?? message ?? "Unreadable answer";
            }
        }
    });

    function readToggleGroup(group: { read?: string }) {
        if (!selectedNodeControlStreamId || !group.read) return;
        toggleError = null;
        sendDeviceCommand(selectedNodeControlStreamId, group.read);
    }

    function flipToggle(groupId: string, toggle: DeviceControl) {
        const current = toggleStates[groupId];
        if (!selectedNodeControlStreamId || !current) return;
        if (controlsLockedByRecording) return;
        toggleError = null;
        sendDeviceCommand(
            selectedNodeControlStreamId,
            toggle.write,
            writeArgsFor(toggle, current),
        );
    }

    const expandedViewerNode = $derived(
        expandedViewerNodeId
            ? draftGraph.nodes.find((n) => n.id === expandedViewerNodeId) ?? null
            : null,
    );

    // Part D: a viewer's incoming channel carries markers (a "stream" or markers
    // channel), so a marker overlay is possible.
    function viewerChannelHasMarkers(node: EditorGraphNode): boolean {
        if (node.kind !== "viewer") return false;
        return resolveInputChannel(node.id).some((t) => t.type === "Marker");
    }

    // Whether the viewer's marker overlay is enabled (the phantom markers input
    // has been clicked). Off until enabled, per the plan's click-to-enable flow.
    function viewerShowsMarkers(node: EditorGraphNode): boolean {
        if (!viewerChannelHasMarkers(node)) return false;
        return node.kind === "viewer" ? node.show_markers === true : false;
    }

    // The phantom markers input state for the node card: absent when the channel
    // has no markers, else "on"/"available" from the overlay toggle.
    function viewerMarkersPhantom(
        node: EditorGraphNode,
    ): "on" | "available" | undefined {
        if (!viewerChannelHasMarkers(node)) return undefined;
        return viewerShowsMarkers(node) ? "on" : "available";
    }

    // Toggle the marker overlay for a viewer node (the phantom-input click).
    function toggleViewerMarkers(nodeId: string) {
        draftGraph = {
            ...draftGraph,
            nodes: draftGraph.nodes.map((node) =>
                node.id === nodeId && node.kind === "viewer"
                    ? { ...node, show_markers: node.show_markers !== true }
                    : node,
            ),
        };
    }

    function openViewerData(node: EditorGraphNode | null) {
        // ⚠️ A stream_source is openable in its own right now. That is the whole
        // point of TEC-NATKIT-98: "which stream is this node?" used to be a
        // board-start away, for data that was already in Kafka the entire time.
        if (!node || (node.kind !== "viewer" && node.kind !== "stream_source")) {
            return;
        }
        if (!viewableStreamId(node.id)) {
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
        } else if (node?.kind === "viewer" || node?.kind === "stream_source") {
            openViewerData(node);
        } else if (node?.kind === "markers" || node?.kind === "experiment") {
            expandedExperimentNodeId = node.id;
        }
    }

    function setInlineViewerGraph(nodeId: string, enabled: boolean) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (node.id === nodeId && node.kind === "viewer") {
                node.inline_graph = enabled;
            }
        }
        markViewStateChanged(nextGraph);
        // Subscriptions are reconciled by the effect below — each inline viewer
        // (and the expanded overlay) subscribes its own stream, so any number
        // render live at once.
    }

    // --- Experiment run surfaces (inline on-node + large modal) --------------
    let expandedExperimentNodeId = $state<string | null>(null);
    const expandedExperimentNode = $derived(
        expandedExperimentNodeId
            ? (draftGraph.nodes.find(
                  (n) => n.id === expandedExperimentNodeId,
              ) ?? null)
            : null,
    );

    function setInlineExperiment(nodeId: string, enabled: boolean) {
        const nextGraph = cloneGraph(draftGraph);
        for (const node of nextGraph.nodes) {
            if (
                node.id === nodeId &&
                (node.kind === "markers" || node.kind === "experiment")
            ) {
                node.inline_experiment = enabled;
            }
        }
        markDraftChanged(nextGraph);
    }

    // Everything a run surface needs, resolved from the board's bound experiment
    // plus the shared recording state (only one experiment records at a time).
    // Returns null when nothing is bound — there is no protocol to run.
    function experimentRunView() {
        const experiment = boundExperimentView;
        const protocol = experiment?.protocol;
        if (!experiment || !protocol) {
            return null;
        }
        const isRecording =
            sessionRecording?.experimentId === experiment.experiment_id;
        const schedule = isRecording
            ? sessionRecording!.schedule
            : scheduleForProtocol(protocol);
        const durationMs = isRecording
            ? sessionRecording!.durationMs
            : scheduleDurationMs(schedule);
        const elapsedMs = isRecording ? sessionRecording!.elapsedMs : 0;
        const activeCue = isRecording
            ? activeCueAtElapsedMs(schedule, elapsedMs)
            : null;
        const nextCue = isRecording
            ? nextCueAfterElapsedMs(schedule, elapsedMs)
            : null;
        const holdCuesList = schedule.filter((c) => c.phase === "hold");
        const holdCues = holdCuesList.length;
        // Progress info for the run surface: which repetition we're in, how many
        // gesture holds are left, so the participant can pace themselves.
        const holdsDone = isRecording
            ? holdCuesList.filter((c) => c.end_offset_ms <= elapsedMs).length
            : 0;
        const currentRep =
            activeCue && activeCue.rep_index >= 0
                ? activeCue.rep_index + 1
                : null;
        return {
            protocolLabel: protocol.label,
            // Carried through so the runner can show the PROTOCOL's words rather
            // than this component's (TEC-NATKIT-69).
            protocol,
            // A step protocol's classes are derived from its cue steps rather than
            // declared, so ask the shape-aware helper.
            classes: isStepProtocol(protocol)
                ? protocolClasses(protocol)
                : (protocol.classes ?? []),
            recording: isRecording,
            recordingElsewhere: sessionRecording != null && !isRecording,
            elapsedMs,
            durationMs,
            activeCue,
            nextCue,
            totalReps: protocol.repetitions,
            currentRep,
            holdsTotal: holdCues,
            holdsRemaining: Math.max(0, holdCues - holdsDone),
            summary: { holdCues, durationS: Math.round(durationMs / 1000) },
        };
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
                // Topic-aware channels (Part A): a viewer fed a data+markers
                // "stream" also receives markers on their own MARKER topic id —
                // subscribe to every topic in the incoming channel so both the
                // data and the marker feeds arrive.
                for (const topic of resolveInputChannel(node.id)) {
                    desired.add(String(topic.id));
                }
            }
            // Timeline (Part E): subscribe to EVERY channel that carries a MARKER
            // topic (a markers node's output, or a combine "stream" output), so
            // the strip shows recorded regions + cue ticks from any of them.
            const markerTopic = markerTopicOfChannel(nodeOutputTopics(node.id));
            if (markerTopic) {
                desired.add(String(markerTopic.id));
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
        // Send a queued experiment edit on the way out rather than dropping it —
        // navigating away from the board shouldn't silently lose a rename.
        flushExperimentEdit();
        if (timelineClock) {
            clearInterval(timelineClock);
            timelineClock = null;
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
            await showAlert({
                title:
                    templates.length > 0
                        ? "Imported with some problems"
                        : "Could not import that file",
                body:
                    templates.length > 0
                        ? `${templates.length} composite${templates.length === 1 ? "" : "s"} imported. The rest were skipped:`
                        : undefined,
                points: errors,
            });
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

    // Topic-aware channels (Part A): a node's output channel is a topic set. The
    // backend reports it in runtime status as `output_topics`; fall back to a
    // one-DATA-topic channel synthesised from output_stream_id so pre-topic
    // backends (and nodes that haven't reported topics yet) still resolve.
    function nodeOutputTopics(nodeId: string): OutputChannelTopic[] {
        const status = nodeRuntimeStatus(nodeId);
        if (status?.output_topics && status.output_topics.length > 0) {
            return status.output_topics;
        }
        if (status?.output_stream_id) {
            return [
                { type: "Data", id: String(status.output_stream_id), schema: "" },
            ];
        }
        return [];
    }

    // The output channel of a node — runtime-reported when the graph is running,
    // else a statically-inferred set from the node kind (Part C badge shows a
    // count pre-run: a source = 1 data, an experiment = 1 marker, a combine =
    // the per-type union of its inputs). `depth` guards the combine recursion.
    function channelTopicsForNode(
        node: EditorGraphNode | undefined,
        depth = 0,
    ): OutputChannelTopic[] {
        if (!node) return [];
        const runtime = nodeOutputTopics(node.id);
        if (runtime.length > 0) return runtime;
        if (depth > 8) return [];
        switch (node.kind) {
            case "stream_source":
                return node.stream_id
                    ? [
                          {
                              type: "Data",
                              id: String(node.stream_id),
                              schema: node.schema_name ?? "",
                          },
                      ]
                    : [];
            case "markers":
            case "experiment":
                return [{ type: "Marker", id: "", schema: "MarkerEventV1" }];
            case "transform": {
                // ⚠️ A transform PASSES MARKERS THROUGH. It used to answer a bare
                // Data topic, which silently dropped the marker half of an
                // incoming bundle: markers wired through a transform vanished
                // from everything downstream that asks this function what a
                // channel holds — the viewer's overlay, the port labels, the
                // edge colours. A transform reshapes samples; it has no opinion
                // about the marker timeline riding alongside them.
                const passthrough = new Map<string, OutputChannelTopic>();
                passthrough.set("Data", { type: "Data", id: "", schema: "" });
                for (const e of draftGraph.edges) {
                    if (e.target_node_id !== node.id) continue;
                    const src = draftGraph.nodes.find(
                        (n) => n.id === e.source_node_id,
                    );
                    for (const t of channelTopicsForNode(src, depth + 1)) {
                        if (t.type !== "Data" && !passthrough.has(t.type)) {
                            passthrough.set(t.type, {
                                type: t.type,
                                id: "",
                                schema: t.schema,
                            });
                        }
                    }
                }
                return [...passthrough.values()];
            }
            case "combine": {
                // Per-type union of the input source channels (one per type).
                const byType = new Map<string, OutputChannelTopic>();
                for (const e of draftGraph.edges) {
                    if (e.target_node_id !== node.id) continue;
                    const src = draftGraph.nodes.find(
                        (n) => n.id === e.source_node_id,
                    );
                    for (const t of channelTopicsForNode(src, depth + 1)) {
                        if (!byType.has(t.type)) {
                            byType.set(t.type, { type: t.type, id: "", schema: t.schema });
                        }
                    }
                }
                return [...byType.values()];
            }
            default:
                return [];
        }
    }

    // The channel feeding a node's input port (resolved via the incoming edge):
    // the topic set the upstream source node outputs, MINUS any topic types the
    // user hid on that edge (so the target acts on only the enabled part). `port`
    // narrows to the edge targeting that specific input port.
    function resolveInputChannel(
        nodeId: string,
        port?: string,
    ): OutputChannelTopic[] {
        const edge = draftGraph.edges.find(
            (e) =>
                e.target_node_id === nodeId &&
                (port === undefined || e.target_port === port),
        );
        if (!edge) return [];
        const hidden = new Set(edge.hidden_topic_types ?? []);
        return channelTopicsForNode(
            draftGraph.nodes.find((n) => n.id === edge.source_node_id),
        ).filter((t) => !hidden.has(t.type));
    }

    // The full channel carried by an edge = the source node's output channel
    // (unfiltered — the badge shows every topic with its enabled/hidden state).
    function edgeChannelTopics(edge: StreamGraphEdge): OutputChannelTopic[] {
        return channelTopicsForNode(
            draftGraph.nodes.find((n) => n.id === edge.source_node_id),
        );
    }

    function isEdgeTopicHidden(edge: StreamGraphEdge, type: string): boolean {
        return (edge.hidden_topic_types ?? []).includes(type);
    }

    // Toggle whether a topic type flows to the edge's target node (the badge
    // checkboxes). Persists on the edge; the frontend (viewer overlay/phantom,
    // combine relabel) reacts immediately, and a running combine is re-run so its
    // merge lanes pick up the change.
    function toggleEdgeTopic(edgeId: string, type: string) {
        let targetNodeId: string | null = null;
        draftGraph = {
            ...draftGraph,
            edges: draftGraph.edges.map((edge) => {
                if (edge.id !== edgeId) return edge;
                targetNodeId = edge.target_node_id;
                const hidden = new Set(edge.hidden_topic_types ?? []);
                if (hidden.has(type)) hidden.delete(type);
                else hidden.add(type);
                return { ...edge, hidden_topic_types: [...hidden] };
            }),
        };
        // A viewer only needs the frontend to stop rendering the topic (no re-run);
        // a combine must re-resolve its merge lanes, so restart it if running.
        const target = draftGraph.nodes.find((n) => n.id === targetNodeId);
        if (target?.kind === "combine") {
            scheduleReactiveRestart(targetNodeId);
        }
    }

    function inputChannelKind(nodeId: string, port?: string): ChannelKind {
        return channelKindFromTopics(resolveInputChannel(nodeId, port));
    }

    // Part B: relabel each connected combine input port data/markers/stream from
    // the channel it is fed, so the merge type is visible on the node itself.
    /**
     * Per-input-port labels, from the channel actually feeding each port.
     *
     * ⚠️ EXPORT NEEDS THIS AS MUCH AS COMBINE DOES, and only combine had it. An
     * export node's two ports rendered as "in1" and "in2" with nothing saying
     * which was the data and which the markers — and getting them the wrong way
     * round produces a Parquet file with an empty label column, which reads as a
     * successful export.
     */
    /**
     * The channel types a single LINK actually carries: data, markers, or both.
     *
     * ⚠️ Port ids win over resolved topics, and the fallback is Data. A channel
     * resolves only once the graph runs or a stream is bound, so keying purely
     * off topics would leave every link grey while it is being wired — which is
     * exactly when the colour is worth having. A port literally named `data` or
     * `markers` states its own contract and settles it without asking.
     */
    function edgeChannelTypes(edge: {
        source_node_id?: string;
        source_port?: string;
        target_node_id?: string;
        target_port?: string;
    }): ("Data" | "Marker")[] {
        const named = (port: string | undefined): "Data" | "Marker" | null =>
            port === "markers" ? "Marker" : port === "data" ? "Data" : null;

        const srcNamed = named(edge.source_port);
        const tgtNamed = named(edge.target_port);
        // A named port at EITHER end pins the link, and a named port at both
        // ends that disagree means the link is miswired — draw the target's
        // expectation, which is what the receiving node will try to read.
        if (tgtNamed) return [tgtNamed];
        if (srcNamed) return [srcNamed];

        const source = draftGraph.nodes.find((n) => n.id === edge.source_node_id);
        const types = new Set<"Data" | "Marker">();
        for (const topic of channelTopicsForNode(source)) {
            if (topic.type === "Data") types.add("Data");
            if (topic.type === "Marker") types.add("Marker");
        }
        if (types.size === 0) return ["Data"];
        // Data first so the pair always stacks the same way round.
        return [...(types.has("Data") ? ["Data" as const] : []),
                ...(types.has("Marker") ? ["Marker" as const] : [])];
    }

    /**
     * Output port labels — a bundle port says so instead of claiming to be one
     * of its halves.
     *
     * ⚠️ Only for a node with EXACTLY ONE output port. With several ports the
     * ids already partition the channel by type, and relabelling them from the
     * node's whole channel would tell every one of them it carries everything.
     */
    /**
     * The drawn line(s) for one link, and where each runs.
     *
     * Three shapes, all of which say the same thing — what is in this link:
     *  - one type              → one curve;
     *  - a bundle into one port → two curves running side by side the whole way,
     *    meeting at the two ports because the ports really are single points;
     *  - a bundle FANNED OUT into several ports of one node → the curves run
     *    together as a trunk and split only at the last ~46px, so the shared
     *    stretch reads as one cable rather than two coincidental links.
     */
    function edgeLines(
        edge: StreamGraphEdge,
        sourcePoint: { x: number; y: number },
        targetPoint: { x: number; y: number },
    ): { type: "Data" | "Marker"; d: string }[] {
        const types = edgeChannelTypes(edge);
        const curve = (
            sy: number,
            ty: number,
        ) =>
            `M ${sourcePoint.x} ${sourcePoint.y} C ${sourcePoint.x + 90} ${sy}, ${
                targetPoint.x - 90
            } ${ty}, ${targetPoint.x} ${targetPoint.y}`;

        // Siblings: same source PORT, same target NODE, different target port.
        const siblings = draftGraph.edges.filter(
            (other) =>
                other.source_node_id === edge.source_node_id &&
                other.source_port === edge.source_port &&
                other.target_node_id === edge.target_node_id,
        );
        if (siblings.length > 1) {
            const index = siblings.findIndex((other) => other.id === edge.id);
            const points = siblings.map((other) => {
                const node = draftGraph.nodes.find(
                    (n) => n.id === other.target_node_id,
                );
                return node
                    ? getPortPoint(node, other.target_port, "input")
                    : targetPoint;
            });
            const spread = (index - (siblings.length - 1) / 2) * 7;
            const forkY =
                points.reduce((sum, p) => sum + p.y, 0) / points.length + spread;
            const forkX = Math.min(...points.map((p) => p.x)) - 46;
            return [
                {
                    type: types[0] ?? "Data",
                    d:
                        `M ${sourcePoint.x} ${sourcePoint.y} C ${
                            sourcePoint.x + 90
                        } ${sourcePoint.y}, ${forkX - 60} ${forkY}, ${forkX} ${forkY} ` +
                        `C ${forkX + 20} ${forkY}, ${targetPoint.x - 32} ${
                            targetPoint.y
                        }, ${targetPoint.x} ${targetPoint.y}`,
                },
            ];
        }

        if (types.length > 1) {
            return types.map((type, index) => {
                const offset = (index - (types.length - 1) / 2) * 9;
                return {
                    type,
                    d: curve(sourcePoint.y + offset, targetPoint.y + offset),
                };
            });
        }
        return [{ type: types[0] ?? "Data", d: curve(sourcePoint.y, targetPoint.y) }];
    }

    /**
     * What a viewer or sink is reading — or, when it is reading nothing, WHICH
     * of the several possible reasons applies.
     *
     * ⚠️ The reasons matter more than the absence. "Connect an upstream stream"
     * was shown for all of them, including the common one on a fresh ADL board:
     * the viewer IS connected, and the Stream node upstream simply has no stream
     * picked yet. The same distinction the calibration readout already draws
     * (TEC-NATKIT-98), so both surfaces answer the question the same way.
     */
    function viewerSourceLabel(node: EditorGraphNode): string | null {
        const streamId = viewableStreamId(node.id);
        if (streamId) return `Stream ${displayStream(String(streamId))}`;
        const view = resolveSourceView(node.id, draftGraph.nodes, draftGraph.edges);
        switch (view.reason) {
            case "unbound_source":
                return "Pick a stream on the upstream Stream node";
            case "no_source":
                return "Connect an upstream stream";
            case "needs_worker":
                return "Start the graph — this reads through a transform";
            default:
                return null;
        }
    }

    function outputPortLabelsFor(
        node: EditorGraphNode,
    ): Record<string, string> | undefined {
        const ports = node.output_port_ids ?? [];
        if (ports.length !== 1) return undefined;
        const portId = ports[0];
        if (isProvenancePort(portId)) return undefined;
        // ⚠️ Read from the INCOMING LINKS, not from channelTopicsForNode, for
        // any node that has them. An unbound stream source resolves to no
        // topics at all, so a combine fed by eight unbound sources and one
        // markers node resolved as markers-ONLY and its output kept the default
        // "data" label — the one case where the label mattered most. The links
        // know their own types (edgeChannelTypes falls back to Data), and using
        // them is also what makes the label agree with the line colours, which
        // are computed the same way.
        const incoming = draftGraph.edges.filter(
            (edge) => edge.target_node_id === node.id,
        );
        const types = new Set<string>(
            incoming.length > 0
                ? incoming.flatMap((edge) => edgeChannelTypes(edge))
                : channelTopicsForNode(node)
                      .map((t) => t.type)
                      .filter((t) => t === "Data" || t === "Marker"),
        );
        if (types.size < 2) return undefined;
        return { [portId]: BOTH_LABEL };
    }

    function inputPortLabelsFor(
        node: EditorGraphNode,
    ): Record<string, string> | undefined {
        // ⚠️ COMBINE ONLY. Export's ports are now NAMED `data` and `markers`, and
        // relabelling them from the incoming channel actively hid that: the
        // combine feeding export's `data` port carries a BUNDLE, whose channel
        // kind resolves as "markers", so the override renamed the data port to
        // "markers" and the node rendered `markers markers`. A port that states
        // its own contract must not be renamed by what happens to be plugged
        // into it. Combine's in1..inN say nothing on their own, so they still are.
        if (node.kind !== "combine") return undefined;
        const labels: Record<string, string> = {};
        for (const portId of node.input_port_ids ?? []) {
            const kind = inputChannelKind(node.id, portId);
            if (kind !== "empty") {
                // ⚠️ THE PORT ID, and only the port id. Replacing it with the
                // channel kind made both of combine's inputs read "data" while
                // the marble strips directly beneath them read "in1"/"in2" —
                // the same two ports under two names, six pixels apart.
                // Appending the kind ("in1 · data") fixed the naming and broke
                // the layout: the pill is too narrow, so it wrapped onto two
                // lines and overlapped the strips. The dot's colour already
                // carries the channel kind, and the detail view states it.
                labels[portId] = portId;
            }
        }
        return Object.keys(labels).length > 0 ? labels : undefined;
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
        const markers = data?.markers ?? [];
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
        // A markers-ONLY stream (e.g. an experiment node's `markers` output) has
        // no channel-frame descriptor; once a marker arrives we know its schema,
        // so hint the registry to the marker renderer. But a "stream" channel
        // (data + markers, from a topic-aware combine) carries data too — keep
        // the DATA renderer and overlay the markers via the phantom input, rather
        // than replacing the whole waveform with the marker list (Part D).
        const hasData = latestEmg != null;
        const schemaNameHint =
            markers.length > 0 && !hasData
                ? MARKER_SCHEMA_NAME
                : descriptor?.schema_name;
        const imuSamples = data?.imuSamples ?? [];
        return {
            subscribed: data != null,
            emgSamples,
            imuSamples,
            markers,
            latestMuse,
            descriptor,
            renderer: chooseViewerRenderer(descriptor, hint, schemaNameHint),
            recordValue: latestEmg ?? latestMuse ?? imuSamples.at(-1),
        };
    }

    // --- Timeline & transport (Phase 4) --------------------------------------
    // A per-graph time context (Decision #2) drives the DVR-style strip: the
    // graph runs at the live head, or at a scrubbed point in recorded history.
    // The actual re-run of a replayed chain is Phase 5; here the strip sets the
    // context, shows recorded experiments/cues, and scrubs a playhead.
    let showTimeline = $state(false);
    let timelineNowUs = $state(Date.now() * 1000);
    let timelineClock: ReturnType<typeof setInterval> | null = null;
    let timeContextByGraph = $state<Record<string, TimeContext>>({});

    function currentTimeContext(): TimeContext {
        return (
            timeContextByGraph[draftGraph.graph_id] ??
            createLiveContext(timelineNowUs)
        );
    }

    // Part E: the timeline's event source is EVERY channel that carries a MARKER
    // topic — an experiment's markers, but also a combine "stream" output's merged
    // markers — merged, de-duplicated, and time-sorted (recorded regions + cue
    // ticks). Dedup by marker id + emitted_at because a combine re-publishes its
    // upstream markers under its own topic id, so the same cue can appear twice.
    const timelineMarkers = $derived.by<BufferedMarkerEvent[]>(() => {
        const out: BufferedMarkerEvent[] = [];
        const seen = new Set<string>();
        for (const node of draftGraph.nodes) {
            const markerTopic = markerTopicOfChannel(nodeOutputTopics(node.id));
            if (!markerTopic) continue;
            for (const m of liveStreams[String(markerTopic.id)]?.markers ?? []) {
                const key = `${m.marker_id}:${m.emitted_at_us}`;
                if (seen.has(key)) continue;
                seen.add(key);
                out.push(m);
            }
        }
        return out.sort((a, b) => a.emitted_at_us - b.emitted_at_us);
    });

    const timelineWindow = $derived(
        computeTimeWindow(currentTimeContext(), timelineNowUs, timelineMarkers),
    );
    const timelineTicks = $derived(layoutTicks(timelineMarkers, timelineWindow));
    const timelineRegions = $derived(
        layoutRegions(timelineMarkers, timelineWindow, timelineNowUs),
    );
    const playheadFraction = $derived(
        timeToFraction(currentTimeContext().playheadUs, timelineWindow),
    );
    const atLiveEdge = $derived(
        currentTimeContext().mode === "live" ||
            currentTimeContext().playheadUs >= timelineWindow.endUs - 1,
    );

    function ensureTimelineClock() {
        if (timelineClock !== null) return;
        timelineClock = setInterval(() => {
            timelineNowUs = Date.now() * 1000;
            const id = draftGraph.graph_id;
            const ctx = timeContextByGraph[id];
            if (ctx && ctx.mode === "replay" && ctx.playing) {
                const endUs = ctx.endUs ?? timelineNowUs;
                const { playheadUs, reachedEnd } = advancePlayhead(
                    ctx,
                    200,
                    endUs,
                );
                timeContextByGraph = {
                    ...timeContextByGraph,
                    [id]: {
                        ...ctx,
                        playheadUs,
                        playing: reachedEnd ? false : ctx.playing,
                    },
                };
            }
        }, 200);
    }

    // The clock also drives the always-visible time readout at the bottom of the
    // canvas, not just the (toggled) timeline strip, so it runs unconditionally.
    $effect(() => {
        ensureTimelineClock();
    });

    // --- IMU calibration readout --------------------------------------------
    // The IMU Experiment tab polls /api/get_accuracies once a second and colours a
    // body map; a calibration node shows the same thing for one upstream stream.
    // Poll only while such a node is on the board, so a graph without one costs
    // nothing.
    let sensorAccuracies = $state<Record<string, unknown>>({});
    let accuracyTimer: ReturnType<typeof setInterval> | null = null;
    let accuracySelectionMissing = $state(false);

    // Poll while EITHER a calibration node is on the board (it renders the
    // readout) OR any source states a body position (the Record gate needs the
    // accuracies to decide — TEC-NATKIT-63). Without the second condition a gated
    // board with no calibration node would report every sensor as Unknown and block
    // for a reason that is really "nobody is looking".
    const hasCalibrationNode = $derived(
        draftGraph.nodes.some(
            (node) =>
                node.kind === "viewer" &&
                (node as { display_mode?: string }).display_mode ===
                    "imu_calibration",
        ) ||
            draftGraph.nodes.some(
                (node) =>
                    node.kind === "stream_source" &&
                    isAssignedPosition(
                        (node as { sensor_position?: string }).sensor_position,
                    ),
            ),
    );

    async function pollSensorAccuracies() {
        try {
            const response = await fetch("/api/get_accuracies");
            if (!response.ok) return;
            const json = await response.json();
            // The endpoint returns null until /api/set_streams has been called
            // (the IMU Experiment page's Stream Selection step). That selection
            // lives in backend memory, so it is lost on every backend restart --
            // worth telling the operator rather than showing a bare "Unknown".
            sensorAccuracies = json?.accuracies ?? {};
            accuracySelectionMissing =
                json?.accuracies == null ||
                Object.keys(json.accuracies).length === 0;
        } catch (error) {
            // A failed poll must not disturb the editor; the readout just stays
            // on its last value and reports Unknown for streams it never saw.
            console.warn("Could not read sensor accuracies:", error);
        }
    }

    $effect(() => {
        if (!hasCalibrationNode) {
            if (accuracyTimer) {
                clearInterval(accuracyTimer);
                accuracyTimer = null;
            }
            return;
        }
        if (accuracyTimer) return;
        void pollSensorAccuracies();
        accuracyTimer = setInterval(pollSensorAccuracies, 1000);
        return () => {
            if (accuracyTimer) {
                clearInterval(accuracyTimer);
                accuracyTimer = null;
            }
        };
    });

    // Calibration of each POSITIONED source, for the Record gate (TEC-NATKIT-63).
    // Read straight from the polled accuracies by stream id, so the gate does not
    // require a calibration node per sensor — a board can be gated without also
    // being instrumented.
    const positionedSourceCalibration = $derived(
        sourcePositions
            .filter((entry) => isAssignedPosition(entry.position))
            .map((entry) => {
                const raw = entry.stream_id
                    ? sensorAccuracies[String(entry.stream_id)]
                    : undefined;
                const status = calibration_status_for_accuracies(raw);
                return {
                    ...entry,
                    status,
                    statusLabel: calibration_status_to_string(status),
                    ok: meetsCalibrationMinimum(status),
                };
            }),
    );

    const undercalibratedSources = $derived(
        positionedSourceCalibration.filter((entry) => !entry.ok),
    );

    // ⚠️ TWO TIERS, and the distinction is deliberate.
    //
    // A duplicate or missing body position is an OPERATOR ERROR: it is fixable in
    // five seconds and a run recorded with it is worthless, so it is a hard block.
    //
    // Calibration below threshold — or unknown, which a gate must treat the same
    // way — is a JUDGEMENT. A pilot, a bench test, or a rig whose accuracy feed is
    // not configured are all legitimate reasons to record anyway. So it is
    // overridable, and the override is recorded IN THE RUN, because a session
    // recorded below threshold on purpose is fine and one that cannot be
    // identified afterwards is not.
    const hardBlockReason = $derived(positionMappingProblem);

    const calibrationWarning = $derived.by(() => {
        if (undercalibratedSources.length === 0) return null;
        const parts = undercalibratedSources
            .map((entry) => `${entry.position} (${entry.statusLabel})`)
            .join(", ");
        return `Calibration below the minimum on ${parts}. Move each sensor through its full range until it reads Medium or better.`;
    });

    // Resolve the calibration state for a calibration node: its upstream stream's
    // per-sensor accuracies, plus the worst-case overall.
    function calibrationViewFor(node: EditorGraphNode) {
        // ⚠️ Not nodeRuntimeStatus alone. Calibration is exactly the reading you
        // want BEFORE pressing Record — the Record gate refuses an uncalibrated
        // rig, so "start the graph to find out whether you may start" was a loop.
        // viewableStreamId walks upstream to the bound source the same way the
        // live viewer does (TEC-NATKIT-98), and still prefers the runtime id when
        // the graph IS running, so a replay-rebound source stays correct.
        const streamId = viewableStreamId(node.id);
        const raw = streamId ? sensorAccuracies[String(streamId)] : undefined;
        const overall = calibration_status_for_accuracies(raw);
        const parts =
            typeof raw === "object" && raw !== null && "accelerometer" in raw
                ? (raw as SensorAccuracies)
                : null;
        // ⚠️ WHY there is no stream, not just that there is none. "Start the
        // graph" was the only message, and after TEC-NATKIT-98 it became wrong in
        // the common case: on a fresh ADL board every source is deliberately
        // UNBOUND, so the honest answer is "pick a stream", and telling somebody
        // to press Start sends them to a button that will not help.
        const view = resolveSourceView(node.id, draftGraph.nodes, draftGraph.edges);
        return {
            unresolvedReason: streamId ? null : view.reason,
            streamId: streamId ? String(streamId) : null,
            // Distinguish "the backend has no IMU selection" from "this stream is
            // not one of the selected ones" -- the fixes differ.
            selectionMissing: accuracySelectionMissing,
            streamNotSelected:
                !accuracySelectionMissing && streamId != null && raw === undefined,
            overall,
            overallLabel: calibration_status_to_string(overall),
            overallColor: calibration_status_to_color(overall),
            position:
                (node as { sensor_position?: string }).sensor_position || "N/A",
            // ⚠️ One row per sub-sensor the DEVICE IS REPORTING, magnetometer
            // included. Three were hard-coded, so the magnetometer — on the wire
            // since frame v2 — was invisible, and a sensor whose report is
            // switched off was listed as "Unreliable" rather than as off. Both
            // readings are wrong in the same direction: they describe a sensor
            // that is not in use as a badly calibrated one.
            parts: parts
                ? SENSOR_KEYS.map(({ key, label }) => {
                      const reporting = sensorIsReporting(parts, key);
                      const status = accuracy_int_to_calibration_status(
                          Number(parts[key] ?? 0),
                      );
                      return {
                          label,
                          reporting,
                          status,
                          text: reporting
                              ? calibration_status_to_string(status)
                              : "Not reporting",
                          color: reporting
                              ? calibration_status_to_color(status)
                              : "faded",
                      };
                  })
                : [],
        };
    }

    // Compact time readout: wall-clock time and time since the run started.
    //
    // Which "start" that is depends on what the board is doing, and the three
    // cases genuinely differ:
    //   - replaying  -> the RECORDING's own clock, so the numbers match the data
    //                   on screen rather than the wall clock you are watching it
    //                   at. Replay preserves original device timestamps, so
    //                   last_published_ts_us is exactly where the pipeline is.
    //   - running    -> wall clock, elapsed since the run began (active_run_id
    //                   carries the start as "<graph_id>:<start_us>").
    //   - a sealed recording that is not replaying -> when it was captured.
    // The backend's replay progress messages are sparse (two in the first fifteen
    // seconds), so a readout driven only by them sits frozen at +0.0s. A review
    // replay is PACED at a known speed, so the position between updates is exactly
    // (elapsed wall time x speed) — interpolate it, and re-anchor on every message
    // so drift cannot accumulate. Recompute mode is unpaced and has no such
    // relationship, so it just shows the last reported position.
    let replayAnchorAtUs = $state(0);
    let replayAnchorPositionUs = $state(0);

    $effect(() => {
        const replay = replayForSelectedInstance;
        if (!replay) {
            replayAnchorAtUs = 0;
            return;
        }
        replayAnchorPositionUs =
            replay.last_published_ts_us || replay.first_ts_us;
        replayAnchorAtUs = Date.now() * 1000;
    });

    const timeReadout = $derived.by(() => {
        const replay = replayForSelectedInstance;
        if (replay && replay.first_ts_us) {
            const reported = replay.last_published_ts_us || replay.first_ts_us;
            const interpolated =
                replayMode === "review" && replayAnchorAtUs > 0
                    ? replayAnchorPositionUs +
                      (timelineNowUs - replayAnchorAtUs) * replaySpeed
                    : reported;
            const position = Math.min(
                replay.last_ts_us || reported,
                Math.max(reported, interpolated),
            );
            const total = Math.max(0, replay.last_ts_us - replay.first_ts_us);
            const elapsed = Math.max(0, position - replay.first_ts_us);
            return {
                kind: "replay" as const,
                label: "REPLAY",
                clock: formatReadoutClock(position),
                elapsed: formatElapsed(elapsed),
                total: total > 0 ? formatElapsed(total) : null,
                fraction: total > 0 ? Math.min(1, elapsed / total) : 0,
                // Only once the server has actually reported progress — otherwise
                // a stale "0/1709" sits next to a time that is visibly advancing.
                detail:
                    replay.frames_published > 0
                        ? `${replay.frames_published}/${replay.total_frames} frames`
                        : null,
            };
        }
        const runId = selectedGraphStatus?.active_run_id ?? "";
        const startUs = Number(runId.slice(runId.lastIndexOf(":") + 1));
        if (selectedGraphActive && Number.isFinite(startUs) && startUs > 0) {
            return {
                kind: "live" as const,
                label: "LIVE",
                clock: formatReadoutClock(timelineNowUs),
                elapsed: formatElapsed(Math.max(0, timelineNowUs - startUs)),
                total: null,
                fraction: 0,
                detail: null,
            };
        }
        const rec = selectedInstance?.recording;
        if (rec?.window_start_us) {
            const total = Math.max(0, (rec.window_end_us ?? 0) - rec.window_start_us);
            return {
                kind: "recorded" as const,
                label: "RECORDED",
                clock: formatReadoutClock(rec.window_start_us),
                elapsed: total > 0 ? formatElapsed(total) : "—",
                total: null,
                fraction: 0,
                detail: total > 0 ? "duration" : null,
            };
        }
        return {
            kind: "idle" as const,
            label: "IDLE",
            clock: formatReadoutClock(timelineNowUs),
            elapsed: "—",
            total: null,
            fraction: 0,
            detail: null,
        };
    });

    // Wall-clock time of a microsecond timestamp. The date is shown only when it
    // is not today, so a live readout stays short but an old recording is never
    // mistaken for something that happened this afternoon.
    function formatReadoutClock(timestampUs: number): string {
        if (!Number.isFinite(timestampUs) || timestampUs <= 0) return "—";
        const at = new Date(timestampUs / 1000);
        const time = at.toLocaleTimeString(undefined, { hour12: false });
        const isToday = at.toDateString() === new Date(timelineNowUs / 1000).toDateString();
        return isToday ? time : `${at.toLocaleDateString()} ${time}`;
    }

    // Elapsed time, always with a leading "+" so it reads as a delta rather than
    // another clock. Sub-minute keeps tenths, which matters when scrubbing cues.
    function formatElapsed(deltaUs: number): string {
        if (!Number.isFinite(deltaUs) || deltaUs < 0) return "—";
        const totalSeconds = deltaUs / 1_000_000;
        if (totalSeconds < 60) return `+${totalSeconds.toFixed(1)}s`;
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);
        return hours > 0
            ? `+${hours}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s`
            : `+${minutes}m ${String(seconds).padStart(2, "0")}s`;
    }

    function setTimeContext(patch: Partial<TimeContext>) {
        const id = draftGraph.graph_id;
        timeContextByGraph = {
            ...timeContextByGraph,
            [id]: { ...currentTimeContext(), ...patch },
        };
    }

    function timelineScrub(fraction: number) {
        const us = fractionToTime(fraction, timelineWindow);
        // Scrubbing enters replay at the picked time (paused).
        setTimeContext({ mode: "replay", playheadUs: us, playing: false });
    }

    function timelineJumpToLive() {
        setTimeContext({
            mode: "live",
            playheadUs: timelineNowUs,
            playing: true,
        });
    }

    function timelineTogglePlay() {
        setTimeContext({ playing: !currentTimeContext().playing });
    }

    function timelineSetSpeed(speed: PlaybackSpeed) {
        setTimeContext({ speed });
    }

    function formatClock(us: number): string {
        return new Date(us / 1000).toLocaleTimeString([], { hour12: false });
    }

    // Reprocess the chain from the playhead time (Phase 5): resolve the primary
    // root source's offset for the scrubbed timestamp, then re-run the graph
    // from that offset. The backend seeks only the root sources and re-runs the
    // chain live; the timestamp-aligned combine keeps multi-stream correct.
    let pendingReprocess = $state<{ streamId: string; requestId: string } | null>(
        null,
    );
    let reprocessNonce = 0;

    function primaryRootSourceStreamId(): string | null {
        for (const node of draftGraph.nodes) {
            if (node.kind === "stream_source" && node.stream_id) {
                return String(node.stream_id);
            }
        }
        return null;
    }

    function timelineReprocess() {
        const sid = primaryRootSourceStreamId();
        if (!sid) {
            connectionMessage = "No source stream to reprocess from.";
            return;
        }
        const requestId = `reprocess:${sid}:${++reprocessNonce}`;
        pendingReprocess = { streamId: sid, requestId };
        queryStreamTime(sid, currentTimeContext().playheadUs, requestId);
    }

    // Experiment library (Phase 6): selecting a recorded run sets the graph's
    // time context to that experiment's window (Decision #2, per-graph). The
    // user can then Reprocess to re-run the chain over it.
    function loadExperiment(run: RecordedRunSummary) {
        showTimeline = true;
        const endUs = run.end_us ?? Date.now() * 1000;
        setTimeContext({
            mode: "replay",
            playheadUs: run.start_us,
            endUs,
            playing: false,
            sessionId: run.session_id,
        });
    }

    // When the offset for a pending reprocess query lands, re-run from it.
    $effect(() => {
        const pending = pendingReprocess;
        if (!pending) return;
        const extent = streamTimeExtents[pending.streamId];
        if (!extent || extent.request_id !== pending.requestId) return;
        pendingReprocess = null;
        if (!extent.valid) {
            connectionMessage = "Could not resolve a replay offset for that time.";
            return;
        }
        const offset =
            (extent.offset_for_timestamp ?? -1) >= 0
                ? (extent.offset_for_timestamp as number)
                : (extent.earliest_offset ?? -2);
        if (selectedGraphStatus?.run_state === "running") {
            stopStreamGraph(draftGraph.graph_id);
        }
        startStreamGraph(draftGraph.graph_id, offset);
        setTimeContext({ mode: "replay", playing: true });
    });

</script>

<svelte:window
    onmousemove={handlePointerMove}
    onmouseup={endPointerInteraction}
    onmousedown={handleWindowPointerDown}
    onkeydown={handleWindowKeydown}
/>

<!-- The inspector body, as a SNIPPET so the sidebar and the node detail view
     (TEC-NATKIT-124) render the SAME markup. It is ~1,700 lines driven
     entirely by selectedNodeId, so a second copy for the modal would
     guarantee the two drift apart — it would quietly stop growing the moment
     anybody edited only the first.

     ⚠️ DECLARED AT TOP LEVEL, not beside the panel that uses it. A snippet is
     only visible inside the block it is declared in; this sat three <div>s
     deep at first and the detail view, a sibling further out, could not see
     it at all — "inspectorBody is not defined", thrown during render and
     swallowed, so the modal simply never appeared with no console error. -->
<!-- The board-level section of the inspector. Split out from
     inspectorBody so the node detail view (TEC-NATKIT-124) can render the
     NODE's sections without the board's description, which belongs to the
     graph rather than to any node. -->
<!-- The node's live runtime block. Split out of inspectorBody so the detail
     view (TEC-NATKIT-126) can put it in the LEFT pane under the node card,
     where 'what this node IS and what it is doing' belongs — leaving the
     right pane as purely the fields you edit. The sidebar renders it in its
     original position. -->
{#snippet inspectorGeneratedJson()}
    <!-- ⚠️ COLLAPSED, and LAST. This sat at the top of the panel in a small box
         with two scrollbars, pushing the Inspector and Diagnostics — the things
         somebody actually reads — below the fold. It is a debugging aid, so it
         is a <details> that remembers nothing and starts shut. -->
    <details class="inspector-section json-section">
        <summary class="eyebrow">Generated JSON</summary>
        <pre>{graphJsonPreview}</pre>
    </details>
{/snippet}

{#snippet inspectorRuntimeCard()}
                        {#if selectedNodeRuntimeStatus}
                            <div class="runtime-card">
                                <div class="summary-row">
                                    <span>Runtime</span>
                                    <strong class={graphRunStateClass(selectedNodeRuntimeStatus.state)}>
                                        {graphRunStateLabel(selectedNodeRuntimeStatus.state)}
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
                                {#if (selectedNode as { display_mode?: string }).display_mode === "imu_calibration"}
                                    <!-- Which body position this board is worn at,
                                         so the readout is labelled the way the
                                         person is actually set up. -->
                                    <label>
                                        <span>Worn at</span>
                                        <select
                                            disabled={boardIsImmutable}
                                            value={(selectedNode as { sensor_position?: string })
                                                .sensor_position ?? "N/A"}
                                            onchange={(event) =>
                                                updateSelectedNode((node) => ({
                                                    ...node,
                                                    sensor_position: (
                                                        event.currentTarget as HTMLSelectElement
                                                    ).value,
                                                }))}
                                        >
                                            {#each SENSOR_POSITION_NAMES as name}
                                                <option value={name}>{name}</option>
                                            {/each}
                                        </select>
                                    </label>
                                {/if}
                            </div>
                        {/if}
{/snippet}

{#snippet inspectorGraphSection()}
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
{/snippet}

{#snippet inspectorBody()}

                {#if selectedInstance}
                    {@const rec = selectedInstance.recording}
                    {@const artifacts = rec?.artifacts}
                    <div class="inspector-section">
                        <div class="inspector-section-header">
                            <p class="eyebrow">Instance</p>
                            <span
                                class={`instance-badge ${selectedInstance.immutable ? "sealed" : "editable"}`}
                            >
                                {selectedInstance.immutable
                                    ? "IMMUTABLE"
                                    : selectedInstance.origin === "fork"
                                      ? "FORK"
                                      : (rec?.status ?? "draft")}
                            </span>
                        </div>
                        <div class="summary-row">
                            <span>Instance</span>
                            <strong>{selectedInstance.instance_id}</strong>
                        </div>
                        {#if selectedInstance.forked_from}
                            <div class="summary-row">
                                <span>Forked from</span>
                                <strong>{selectedInstance.forked_from}</strong>
                            </div>
                        {/if}
                        <div class="summary-row">
                            <span>Recorded</span>
                            <strong>
                                {formatWindow(rec?.window_start_us, rec?.window_end_us)}
                            </strong>
                        </div>
                        <div class="summary-row">
                            <span>Status</span>
                            <strong class={`instance-status ${rec?.status ?? ""}`}>
                                {rec?.status ?? "unknown"}
                            </strong>
                        </div>
                        {#if rec?.message}
                            <p class="muted-text">{rec.message}</p>
                        {/if}

                        <!-- Whether the clocks could be trusted while this ran
                             (TEC-NATKIT-77). Shown on the sealed instance because
                             this is the only copy: the status frames it came from
                             have aged out of Kafka by the time anybody asks. -->
                        {#if rec?.clock_quality}
                            {@const clock = rec.clock_quality}
                            {@const troubled = clock.devices.filter(
                                (device) =>
                                    device.status !== "reported" ||
                                    device.valid === false ||
                                    device.epoch_changed_during_run === true,
                            )}
                            <div class="clock-record">
                                <div class="summary-row">
                                    <span>Clocks</span>
                                    <!-- ⚠️ The empty case is its own answer. With no
                                         devices this read "all 0 held", which is a
                                         reassurance about nothing — and a run whose
                                         sources were never resolved is exactly when
                                         somebody needs telling. -->
                                    <strong
                                        class={clock.devices.length === 0
                                            ? "clock-troubled"
                                            : troubled.length === 0
                                              ? "clock-clean"
                                              : "clock-troubled"}
                                    >
                                        {clock.devices.length === 0
                                            ? "no devices recorded"
                                            : troubled.length === 0
                                              ? `all ${clock.devices.length} held`
                                              : `${troubled.length} of ${clock.devices.length} in question`}
                                    </strong>
                                </div>
                                {#each clock.devices as device (device.device_id)}
                                    <div class="clock-device">
                                        <span class="clock-device-id">{device.device_id}</span>
                                        {#if device.status === "no_status_frames"}
                                            <!-- Not a fault: most sources publish
                                                 no status frame. But it IS the
                                                 absence of a claim, and it must
                                                 not read as a clean bill. -->
                                            <span class="clock-note">no clock data — this device does not report one</span>
                                        {:else if device.status === "went_quiet"}
                                            <span class="clock-note bad">stopped reporting during the run</span>
                                        {:else if device.valid === false}
                                            <span class="clock-note bad">no usable fit — timestamps not comparable across devices</span>
                                        {:else}
                                            <span class="clock-note ok">
                                                fit held{device.residual_rms_ns !== undefined
                                                    ? `, residual ${(device.residual_rms_ns / 1000).toFixed(1)} µs`
                                                    : ""}{device.beacons_missed_per_s !== undefined
                                                    ? `, ${device.beacons_missed_per_s.toFixed(2)} beacons/s missed`
                                                    : ""}
                                            </span>
                                        {/if}
                                        {#if device.epoch_changed_during_run}
                                            <span class="clock-note bad">the fit was rebuilt mid-run — timestamps before and after sit on different fits</span>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {/if}

                        {#if artifacts?.data?.length}
                            <p class="eyebrow">Artifacts</p>
                            {#each artifacts.data as artifact}
                                <div class="artifact-card">
                                    <div class="summary-row">
                                        <span>{artifact.path}</span>
                                        <strong>{artifact.rows ?? 0} rows</strong>
                                    </div>
                                    <div class="summary-row">
                                        <span>{artifact.schema_name ?? "—"}</span>
                                        <strong class="artifact-hash"
                                            >{(artifact.sha256 ?? "").slice(0, 12)}</strong
                                        >
                                    </div>
                                    {#if artifact.truncated}
                                        <p class="muted-text">
                                            ⚠ Truncated — this file is a prefix of the
                                            stream, not the whole window.
                                        </p>
                                    {/if}
                                    {#if artifact.label_counts}
                                        <div class="label-histogram">
                                            {#each Object.entries(artifact.label_counts).sort((a, b) => b[1] - a[1]) as [label, count]}
                                                {@const share =
                                                    (count / Math.max(1, artifact.rows ?? count)) * 100}
                                                <div class="label-row">
                                                    <span class="label-name">{label}</span>
                                                    <span class="label-bar">
                                                        <span
                                                            class="label-bar-fill"
                                                            class:unlabelled={label === "(unlabelled)"}
                                                            style={`width: ${Math.max(2, share)}%`}
                                                        ></span>
                                                    </span>
                                                    <span class="label-count">{count}</span>
                                                </div>
                                            {/each}
                                        </div>
                                    {/if}
                                    <a
                                        class="artifact-download"
                                        href={artifactDownloadUrl(selectedInstance.graph_id, artifact.path)}
                                        download
                                    >
                                        <Download size={13} />
                                        Download parquet
                                    </a>
                                </div>
                            {/each}
                            {#if artifacts.markers}
                                <a
                                    class="artifact-download"
                                    href={artifactDownloadUrl(selectedInstance.graph_id, artifacts.markers)}
                                    download
                                >
                                    <Download size={13} />
                                    Download markers
                                </a>
                            {/if}
                        {:else if rec?.status === "complete"}
                            <p class="muted-text">
                                Sealed, but no artifacts are listed — the record and
                                the store disagree.
                            </p>
                        {/if}

                        {#if artifacts?.data?.length}
                            <p class="eyebrow">Replay</p>
                            {#if replayForSelectedInstance}
                                {@const replay = replayForSelectedInstance}
                                {@const done = replay.total_frames
                                    ? Math.min(
                                          100,
                                          (replay.frames_published /
                                              replay.total_frames) *
                                              100,
                                      )
                                    : 0}
                                <div class="runtime-card">
                                    <div class="summary-row">
                                        <span>Streaming</span>
                                        <strong>
                                            {replay.frames_published} / {replay.total_frames}
                                            frames
                                        </strong>
                                    </div>
                                    <span class="replay-bar">
                                        <span
                                            class="replay-bar-fill"
                                            style={`width: ${Math.max(1, done)}%`}
                                        ></span>
                                    </span>
                                    <div class="summary-row">
                                        <span>Markers</span>
                                        <strong>{replay.markers_published}</strong>
                                    </div>
                                    <p class="muted-text">
                                        Publishing to a scratch topic; the board's
                                        sources are bound to it for this run. Original
                                        timestamps are preserved, so cue labels still
                                        line up.
                                    </p>
                                </div>
                                <div class="inspector-action-row">
                                    <button
                                        type="button"
                                        class="action-btn secondary"
                                        onclick={stopSelectedReplay}
                                    >
                                        <Square size={15} />
                                        Stop replay
                                    </button>
                                </div>
                            {:else}
                                <div class="field-row">
                                    <label>
                                        <span>Mode</span>
                                        <select
                                            value={replayMode}
                                            onchange={(event) =>
                                                (replayMode = (
                                                    event.currentTarget as HTMLSelectElement
                                                ).value as "review" | "recompute")}
                                        >
                                            <option value="review">Review (paced)</option>
                                            <option value="recompute"
                                                >Recompute (as fast as possible)</option
                                            >
                                        </select>
                                    </label>
                                    {#if replayMode === "review"}
                                        <label>
                                            <span>Speed</span>
                                            <select
                                                value={String(replaySpeed)}
                                                onchange={(event) =>
                                                    (replaySpeed = Number(
                                                        (
                                                            event.currentTarget as HTMLSelectElement
                                                        ).value,
                                                    ))}
                                            >
                                                {#each [0.25, 0.5, 1, 2, 4, 8] as option}
                                                    <option value={String(option)}
                                                        >{option}×</option
                                                    >
                                                {/each}
                                            </select>
                                        </label>
                                    {/if}
                                </div>
                                <div class="inspector-action-row">
                                    <button
                                        type="button"
                                        class="action-btn"
                                        onclick={replaySelectedInstance}
                                        title="Stream this recording back through the board's pipeline"
                                    >
                                        <Play size={15} />
                                        Replay
                                    </button>
                                </div>
                                <p class="muted-text">
                                    Replays from the Parquet on disk, not the broker —
                                    a recording from a year ago replays the same as one
                                    from a minute ago.
                                </p>
                            {/if}
                        {/if}

                        <div class="inspector-action-row">
                            <button
                                type="button"
                                class="action-btn"
                                onclick={forkSelectedInstance}
                                title="Create an editable copy that reuses this recording's data"
                            >
                                <GitBranch size={15} />
                                Fork to edit
                            </button>
                            {#if artifacts?.data?.length}
                                <button
                                    type="button"
                                    class="action-btn secondary"
                                    onclick={() => verifyExperimentInstance(selectedInstance.graph_id)}
                                    title="Re-check the artifacts against their recorded checksums"
                                >
                                    <ScanSearch size={15} />
                                    Verify
                                </button>
                            {/if}
                        </div>
                        {#if selectedInstanceVerification}
                            <div class="runtime-card">
                                <div class="summary-row">
                                    <span>Integrity</span>
                                    <strong class={selectedInstanceVerification.ok ? "ok" : "error"}>
                                        {selectedInstanceVerification.ok
                                            ? "all artifacts match"
                                            : "MISMATCH"}
                                    </strong>
                                </div>
                                {#each selectedInstanceVerification.artifacts.filter((entry) => !entry.ok) as bad}
                                    <p class="muted-text">{bad.path}: {bad.problem}</p>
                                {/each}
                            </div>
                        {/if}
                        <p class="muted-text">
                            {selectedInstance.immutable
                                ? "This board is the graph as it was when the data was captured. It is read-only; fork it to change the pipeline and re-run against the same data."
                                : "This instance is editable — its pipeline can change, but it still points at the recording's original files."}
                        </p>
                    </div>
                {/if}

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
                                            {displayStream(stream.streamId)} - {stream.schemaName}
                                        </option>
                                    {/each}
                                </select>
                            </label>
                            <!-- Where this sensor is worn (TEC-NATKIT-62). On the
                                 SOURCE because it is a property of the sensor, and
                                 because it is the stream↔limb pairing an exported
                                 file needs to say which signal came from which arm. -->
                            <label>
                                <span>Worn at</span>
                                <select
                                    disabled={boardIsImmutable}
                                    value={selectedSourceNode.sensor_position ??
                                        "N/A"}
                                    onchange={(event) =>
                                        updateSelectedNode((node) =>
                                            node.kind === "stream_source"
                                                ? {
                                                      ...node,
                                                      sensor_position: (
                                                          event.currentTarget as HTMLSelectElement
                                                      ).value,
                                                  }
                                                : node,
                                        )}
                                >
                                    {#each SENSOR_POSITION_NAMES as name}
                                        <option value={name}>{name}</option>
                                    {/each}
                                </select>
                            </label>
                            {#if positionDuplicates.includes(
                                (selectedSourceNode.sensor_position ??
                                    "") as (typeof positionDuplicates)[number],
                            )}
                                <!-- Named on the offending node, not only in the
                                     board-level summary: the operator is looking at
                                     this inspector when they make the mistake. -->
                                <p class="position-clash">
                                    Another source is also set to {selectedSourceNode.sensor_position}.
                                    A swapped limb cannot be seen in the data or
                                    fixed afterwards, so give each its own.
                                </p>
                            {/if}

                            <!-- This stream's clock fit (TEC-NATKIT-7).
                                 ⚠️ HERE rather than on the node card, and that is
                                 a measurement, not a preference. A source node's
                                 card is 220x92 and its header is over budget
                                 before anything is added — its label wants 111px
                                 in 62. A dot in the header collapsed `.node-kind`
                                 to a 5px sliver; making that hold its width
                                 overflowed the card by 31px; a third meta line
                                 was clipped out of view entirely; and appended
                                 after the truncating stream label it landed
                                 outside the card. The inspector has room for the
                                 numbers, which is what somebody diagnosing a
                                 clock actually needs.
                                 Rendered only when the device publishes a fit:
                                 most sources (a Muse, an EMG pill) publish none,
                                 and a row on every one of them would train people
                                 to ignore it. -->
                            {@const fit = clockFitForStream(
                                deviceHealth,
                                selectedSourceNode.stream_id,
                            )}
                            {#if fit.state !== "unknown"}
                                <div class="clock-fit-row clock-{fit.state}">
                                    <span class="clock-dot"></span>
                                    <span class="clock-state">
                                        {fit.state === "ok"
                                            ? "Clock fit held"
                                            : fit.state === "no_fit"
                                              ? "No usable clock fit"
                                              : "Clock fit is stale"}
                                    </span>
                                    <span class="clock-detail">{fit.detail}</span>
                                </div>
                            {/if}
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

                                {#if classifyModelOptions.length > 0}
                                    <label>
                                        <span>Model (from wired trainer)</span>
                                        <select
                                            value={selectedTransformNode.config
                                                ?.model_path ?? ""}
                                            onchange={(event) =>
                                                selectClassifyModel(
                                                    (
                                                        event.currentTarget as HTMLSelectElement
                                                    ).value,
                                                )}
                                        >
                                            <option value="" disabled
                                                >Pick a trained model…</option
                                            >
                                            {#each classifyModelOptions as model}
                                                {@const path =
                                                    classifyModelPath(model)}
                                                {#if path}
                                                    <option value={path}>
                                                        {model.family ?? "model"}
                                                        {model.accuracy != null
                                                            ? `· ${(model.accuracy * 100).toFixed(1)}%`
                                                            : ""}
                                                        · {new Date(
                                                            model.completed_at_us /
                                                                1000,
                                                        ).toLocaleString()}
                                                    </option>
                                                {/if}
                                            {/each}
                                        </select>
                                    </label>
                                    {#if selectedClassifyModel}
                                        <p class="run-picker-scope">
                                            Serving {selectedClassifyModel.family ??
                                                "model"}{selectedClassifyModel.accuracy !=
                                            null
                                                ? ` · ${(selectedClassifyModel.accuracy * 100).toFixed(1)}% val`
                                                : ""}.
                                        </p>
                                    {:else if !selectedTransformNode.config
                                        ?.model_path}
                                        <p class="run-picker-scope warn">
                                            No model selected — pick one to go
                                            live.
                                        </p>
                                    {/if}
                                {/if}

                                <NodeConfigFields
                                    fields={selectedNodeCapability.config_fields}
                                    config={selectedTransformNode.config}
                                    onChange={updateTransformConfigField}
                                />
                            {/if}
                            {#if selectedGraphActive}
                                <div class="inspector-action-row">
                                    <button
                                        type="button"
                                        class="action-btn"
                                        title="Restart just this node (and its downstream) to apply the current config — e.g. a newly trained model — without stopping the graph"
                                        onclick={restartSelectedNode}
                                    >
                                        <RefreshCw size={15} />
                                        Restart node
                                    </button>
                                </div>
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
                            {#if catalogConfigFields.length > 0}
                                <NodeConfigFields
                                    fields={catalogConfigFields}
                                    config={selectedCombineNode.config ?? {}}
                                    onChange={updateCatalogConfigField}
                                />
                                <p class="muted-text">
                                    {combineJoinPolicyHint}
                                </p>
                            {/if}
                        {/if}

                        {#if selectedLaneCrossingNode}
                            <label>
                                <span>Output identifier</span>
                                <input
                                    value={selectedLaneCrossingNode.output_identifier ??
                                        ""}
                                    oninput={(event) =>
                                        updateSelectedNode((node) =>
                                            TOPIC_PUBLISHING_KINDS.includes(
                                                node.kind,
                                            )
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
                            {#if catalogConfigFields.length > 0}
                                <NodeConfigFields
                                    fields={catalogConfigFields}
                                    config={selectedLaneCrossingNode.config ??
                                        {}}
                                    onChange={updateCatalogConfigField}
                                />
                            {/if}
                            <p class="muted-text">{laneCrossingHint}</p>
                        {/if}

                        {#if selectedMarkersNode}
                            <p class="muted-text">
                                This node republishes the board's experiment
                                marker timeline — cue and session events on
                                <code>Marker/&lt;experiment_id&gt;</code>. There is
                                nothing to configure: it follows whichever
                                experiment owns the board.
                            </p>
                            <div class="summary-row">
                                <span>Experiment</span>
                                <strong>
                                    {boundExperimentView
                                        ? boundExperimentView.label ||
                                          boundExperimentView.experiment_id
                                        : "none bound"}
                                </strong>
                            </div>
                            <div class="inspector-action-row">
                                <button
                                    type="button"
                                    class="action-btn secondary"
                                    onclick={() => (showExperimentPanel = true)}
                                >
                                    <FlaskConical size={15} />
                                    {boundExperimentView
                                        ? "Open experiment"
                                        : "Bind an experiment"}
                                </button>
                                {#if boundExperimentView}
                                    <!-- The portal: this node carries the
                                         experiment's markers, so the protocol
                                         lives "inside" it. -->
                                    <button
                                        type="button"
                                        class="action-btn secondary"
                                        title="Look inside this node at the protocol producing its markers"
                                        onclick={() => {
                                            designerInitialView = "canvas";
                                            showExperimentDesigner = true;
                                        }}
                                    >
                                        <Network size={15} />
                                        Open protocol
                                    </button>
                                {/if}
                            </div>
                        {/if}

                        {#if selectedLegacyExperimentNode}
                            <!-- A board saved before the experiment became a
                                 first-class object. Its protocol is still here in
                                 the node config, so it keeps recording; converting
                                 lifts it into an experiment record and swaps the
                                 node for a markers source in place, keeping every
                                 edge. -->
                            <p class="muted-text">
                                Legacy experiment node. The experiment is now an
                                object that owns this board, so its protocol,
                                participant and Record button live in the
                                Experiment panel. Convert to move
                                <strong
                                    >{selectedLegacyExperimentNode.config.protocol
                                        ?.label ??
                                        selectedLegacyExperimentNode.label}</strong
                                >
                                into an experiment bound to this board — the node
                                becomes a <code>markers</code> source and its
                                wiring is unchanged.
                            </p>
                            <div class="inspector-action-row">
                                <button
                                    type="button"
                                    class="action-btn"
                                    onclick={() =>
                                        convertExperimentNode(
                                            selectedLegacyExperimentNode,
                                        )}
                                >
                                    <FlaskConical size={15} />
                                    Convert to experiment + markers
                                </button>
                            </div>
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
                            <div class="run-picker">
                                <div class="run-picker-head">
                                    <span>Recorded runs</span>
                                    <button
                                        type="button"
                                        class="icon-btn"
                                        onclick={requestRecordedRuns}
                                        title="Refresh recorded experiments"
                                    >
                                        <RefreshCw size={13} />
                                    </button>
                                </div>
                                {#if trainableInstances.length > 0}
                                    <p class="eyebrow">Recorded instances</p>
                                    <p class="run-picker-scope">
                                        Training from an instance reads its
                                        materialized Parquet, so it works long after
                                        the broker would have dropped the records —
                                        and the same files give the same features
                                        every time.
                                    </p>
                                    <div class="instance-picker">
                                        {#each trainableInstances as instance}
                                            {@const rows =
                                                instance.recording?.artifacts
                                                    ?.total_rows ?? 0}
                                            {@const counts =
                                                instance.recording?.artifacts?.data?.[0]
                                                    ?.label_counts ?? {}}
                                            {@const classes = Object.keys(counts).filter(
                                                (label) => label !== "(unlabelled)",
                                            )}
                                            <div class="instance-pick-row">
                                                <span class="instance-pick-label">
                                                    <strong>{instance.instance_id}</strong>
                                                    <span class="instance-pick-meta">
                                                        {rows} rows{classes.length
                                                            ? ` · ${classes.join(", ")}`
                                                            : " · no classes"}
                                                    </span>
                                                </span>
                                                <button
                                                    type="button"
                                                    class="run-chip"
                                                    class:active={(
                                                        cfg.train_instances ?? []
                                                    ).includes(instance.graph_id)}
                                                    onclick={() =>
                                                        toggleTrainInstance(
                                                            instance.graph_id,
                                                            "train",
                                                        )}
                                                >
                                                    train
                                                </button>
                                                <button
                                                    type="button"
                                                    class="run-chip"
                                                    class:active={(
                                                        cfg.eval_instances ?? []
                                                    ).includes(instance.graph_id)}
                                                    onclick={() =>
                                                        toggleTrainInstance(
                                                            instance.graph_id,
                                                            "eval",
                                                        )}
                                                >
                                                    validate
                                                </button>
                                            </div>
                                            {#if classes.length === 0}
                                                <p class="run-picker-scope warn">
                                                    {instance.instance_id} has no
                                                    labelled classes — training on it
                                                    would produce a model that predicts
                                                    one thing.
                                                </p>
                                            {/if}
                                        {/each}
                                    </div>
                                    <p class="eyebrow">Or reconstruct from Kafka</p>
                                {/if}
                                {#if trainLineageExperimentIds.length > 0}
                                    <p class="run-picker-scope">
                                        Runs from the wired experiment{trainLineageExperimentIds.length >
                                        1
                                            ? "s"
                                            : ""} ({trainLineageExperimentIds.join(
                                            ", ",
                                        )}) are shown first; all recorded runs are
                                        listed so you can train across sessions.
                                    </p>
                                {:else}
                                    <p class="run-picker-scope warn">
                                        No experiment wired — listing every
                                        recorded run. Draw an experiment→train
                                        edge to surface its runs first.
                                    </p>
                                {/if}
                                {#if trainScopedRuns.length === 0}
                                    <p class="muted-text">
                                        No recorded runs yet. Record a session,
                                        then refresh.
                                    </p>
                                {:else}
                                    {#each trainScopedRuns as run}
                                        {@const sel = runSelector(run)}
                                        <div class="run-pick-row">
                                            <span class="run-pick-label">
                                                {run.session_id} · run {run.run_index}
                                                {#if isRunInScope(run)}
                                                    <span class="run-pick-scope-badge"
                                                        >wired</span
                                                    >
                                                {/if}
                                                <span class="run-pick-meta">
                                                    {run.marker_count} markers{run.protocol_id
                                                        ? ` · ${run.protocol_id}`
                                                        : ""}
                                                </span>
                                            </span>
                                            <button
                                                type="button"
                                                class="run-pick-btn"
                                                class:active={cfg.train_runs.includes(
                                                    sel,
                                                )}
                                                onclick={() =>
                                                    toggleRunSelection(run, "train")}
                                                title="Use as a training run"
                                            >
                                                Train
                                            </button>
                                            <button
                                                type="button"
                                                class="run-pick-btn"
                                                class:active={cfg.eval_runs.includes(
                                                    sel,
                                                )}
                                                onclick={() =>
                                                    toggleRunSelection(run, "eval")}
                                                title="Use as a validation run"
                                            >
                                                Eval
                                            </button>
                                        </div>
                                    {/each}
                                {/if}
                            </div>
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
                                <span
                                    >Eval / validation runs (optional,
                                    comma-separated)</span
                                >
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
                                        cfg.train_runs.length === 0 &&
                                        (cfg.train_instances ?? []).length === 0}
                                    onclick={() =>
                                        submitTrainJobForNode(selectedTrainNode)}
                                >
                                    <Cpu size={15} />
                                    Submit training job
                                </button>
                            </div>
                            {#if cfg.train_runs.length > 0 && cfg.eval_runs.length === 0}
                                <p class="run-picker-scope">
                                    No validation run — trains on the selected
                                    run(s), no held-out accuracy reported. Add an
                                    Eval run for an accuracy estimate.
                                </p>
                            {/if}
                            {#if trainJobStatus}
                                <div class="summary-row">
                                    <span>Job</span>
                                    <strong>{trainJobStatus}</strong>
                                </div>
                            {/if}
                            {#if trainAccuracy}
                                <div class="summary-row">
                                    <span>Validation accuracy</span>
                                    <strong>
                                        {(trainAccuracy.mean_accuracy * 100).toFixed(1)}%
                                        {#if trainAccuracy.family}
                                            ({trainAccuracy.family})
                                        {/if}
                                    </strong>
                                </div>
                                <div class="summary-row">
                                    <span>Min acc / coverage</span>
                                    <strong>
                                        {(trainAccuracy.min_accuracy * 100).toFixed(1)}% /
                                        {(trainAccuracy.mean_coverage * 100).toFixed(1)}%
                                    </strong>
                                </div>
                            {/if}
                            {#if trainModelPath}
                                <div class="summary-row">
                                    <span>Model</span>
                                    <strong>{trainModelPath}</strong>
                                </div>
                            {/if}
                            {#if trainBundlePath}
                                <div class="summary-row">
                                    <span>Bundle</span>
                                    <strong>{trainBundlePath}</strong>
                                </div>
                                <p class="muted-text">
                                    Auto-filled into this graph's EMG Gesture
                                    Classify node — no manual paste needed. Start
                                    the graph to classify live.
                                </p>
                            {/if}
                        {/if}

                        {#if selectedExportNode}
                            {@const ecfg = selectedExportNode.config}
                            <p class="muted-text">
                                Writes one Parquet file per export: the data
                                frames as rows, with the active cue joined on as a
                                label column. Wire a data stream in for the rows
                                and an experiment's markers in for the session
                                window + labels.
                            </p>

                            <div class="run-picker">
                                <div class="run-picker-head">
                                    <span>Wired inputs</span>
                                </div>
                                {#if exportInputs.data.length === 0}
                                    <p class="run-picker-scope warn">
                                        No data input — wire a stream, transform,
                                        or combine into this node.
                                    </p>
                                {:else}
                                    {#each exportInputs.data as entry}
                                        <div class="summary-row">
                                            <span>Data · {entry.label}</span>
                                            <strong>
                                                {entry.topic
                                                    ? `${entry.topic.schema} (#${entry.topic.id})`
                                                    : "unresolved — start the graph"}
                                            </strong>
                                        </div>
                                    {/each}
                                {/if}
                                {#if exportInputs.experiments.length === 0}
                                    <p class="run-picker-scope warn">
                                        No experiment wired — its markers define
                                        the session window and the labels.
                                    </p>
                                {:else}
                                    {#each exportInputs.experiments as entry}
                                        <div class="summary-row">
                                            <span>Markers · {entry.label}</span>
                                            <strong>{entry.sessionId}</strong>
                                        </div>
                                    {/each}
                                {/if}
                            </div>

                            <label>
                                <span>Label column</span>
                                <input
                                    value={ecfg.label_field}
                                    oninput={(event) =>
                                        updateExportConfig({
                                            label_field: (
                                                event.currentTarget as HTMLInputElement
                                            ).value,
                                        })}
                                />
                            </label>
                            <label>
                                <span>Run index (blank = whole session)</span>
                                <input
                                    type="number"
                                    min="1"
                                    value={ecfg.run_index ?? ""}
                                    oninput={(event) => {
                                        const raw = (
                                            event.currentTarget as HTMLInputElement
                                        ).value;
                                        updateExportConfig({
                                            run_index: raw ? Number(raw) : null,
                                        });
                                    }}
                                />
                            </label>
                            <div class="inspector-action-row">
                                <button
                                    type="button"
                                    class="action-btn"
                                    disabled={!exportReadiness.ready ||
                                        exportDownload?.status === "downloading"}
                                    onclick={() =>
                                        downloadExportForNode(selectedExportNode)}
                                >
                                    <FileDown size={15} />
                                    {exportDownload?.status === "downloading"
                                        ? "Exporting…"
                                        : "Download Parquet"}
                                </button>
                            </div>
                            {#if !exportReadiness.ready && exportReadiness.reason}
                                <p class="run-picker-scope warn">
                                    {exportReadiness.reason}
                                </p>
                            {/if}

                            {#if exportDownload}
                                <div class="summary-row">
                                    <span>Export</span>
                                    <strong>{exportDownload.message}</strong>
                                </div>
                                {#if exportDownload.frameCount != null}
                                    <div class="summary-row">
                                        <span>Frames (labelled)</span>
                                        <strong>
                                            {exportDownload.frameCount}
                                            ({exportDownload.labelledFrameCount ?? 0})
                                        </strong>
                                    </div>
                                {/if}
                                {#if exportDownload.markerCount != null}
                                    <div class="summary-row">
                                        <span>Markers</span>
                                        <strong>{exportDownload.markerCount}</strong>
                                    </div>
                                {/if}
                                {#if exportDownload.truncated}
                                    <p class="run-picker-scope warn">
                                        Hit the backend's export time budget — this
                                        file is a prefix of the stream, not all of
                                        it. Narrow the window and export again.
                                    </p>
                                {/if}
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

                {#if selectedNodeControlStreamId}
                    <div class="inspector-section">
                        <p class="eyebrow">Controls</p>

                        <!-- ⚠️ The name is a property of the STREAM, not of this
                             node: two nodes bound to one stream are one board, and
                             renaming from either must change both. So it is stored
                             on the backend by stream id, not in node config. -->
                        <label>
                            Friendly name
                            <input
                                type="text"
                                placeholder="e.g. Left Hand"
                                value={streamAliases[selectedNodeControlStreamId] ?? ""}
                                onchange={(event) =>
                                    setStreamAlias(
                                        selectedNodeControlStreamId!,
                                        event.currentTarget.value.trim(),
                                    )}
                            />
                        </label>
                        <p class="muted-text">
                            Shown everywhere as
                            <strong>{displayStream(selectedNodeControlStreamId)}</strong>.
                            The id is always kept: it is what topics, recordings
                            and log lines are keyed by. Clear the field to remove
                            the name.
                        </p>

                        {#if resolvedControls.availability === "unadvertised" || resolvedControls.availability === "none"}
                            <!-- ⚠️ NO CONTROLS ARE INVENTED. This is the whole
                                 point: a device that has not said what it
                                 supports gets nothing, rather than a default set
                                 of IMU toggles it may not have. -->
                            <p class="muted-text">{resolvedControls.reason}</p>
                        {:else}
                            {#if resolvedControls.availability === "unreachable"}
                                <!-- Shown, disabled, WITH the reason. Hiding them
                                     would be indistinguishable from a board that
                                     never had them. -->
                                <p class="calib-command-result failed">
                                    {resolvedControls.reason}
                                </p>
                            {:else}
                                <p class="muted-text">
                                    Acts on the board itself, not on the graph.
                                    Works whether or not the graph is running.
                                </p>
                            {/if}

                            {@const offline =
                                resolvedControls.availability === "unreachable"}

                            <div class="inspector-action-row">
                                {#each resolvedControls.buttons as control (control.id)}
                                    {@const pending = controlPending(control.write)}
                                    <button
                                        type="button"
                                        class="action-btn secondary inspector-action"
                                        disabled={pending || offline}
                                        title={control.description ??
                                            controlLabel(control)}
                                        onclick={() =>
                                            sendDeviceCommand(
                                                selectedNodeControlStreamId!,
                                                control.write,
                                            )}
                                    >
                                        <Lightbulb size={15} />
                                        {pending ? "Working…" : controlLabel(control)}
                                    </button>
                                {/each}
                                <button
                                    type="button"
                                    class="action-btn secondary inspector-action"
                                    title="Watch this sensor's live data without starting the graph"
                                    onclick={() => openViewerData(selectedNode)}
                                >
                                    <Monitor size={15} />
                                    Open Live Stream
                                </button>
                            </div>

                            {#each resolvedControls.toggleGroups as group (group.group)}
                                {@const known = toggleStates[group.group] ?? null}
                                {@const reading = controlPending(group.read)}
                                {@const writing = controlPending(
                                    group.toggles[0]?.write,
                                )}
                                <div class="control-group">
                                    <div class="control-group-head">
                                        <span class="control-group-title">
                                            {group.group}
                                        </span>
                                        {#if group.read}
                                            <button
                                                type="button"
                                                class="action-btn secondary inspector-action"
                                                disabled={reading || writing || offline}
                                                onclick={() => readToggleGroup(group)}
                                            >
                                                <RefreshCw size={14} />
                                                {known ? "Refresh" : "Read from device"}
                                            </button>
                                        {/if}
                                    </div>

                                    {#if controlsLockedByRecording}
                                        <p class="muted-text">
                                            A recording is in progress. Changing
                                            what a sensor collects would change
                                            the recording's schema partway
                                            through, so it is refused until the
                                            recording stops.
                                        </p>
                                    {/if}

                                    {#if known}
                                        <div class="control-toggles">
                                            {#each group.toggles as toggle (toggle.id)}
                                                {@const key = toggle.field ?? toggle.id}
                                                <label
                                                    class="control-toggle"
                                                    class:off={!known[key]}
                                                    title={toggle.description ??
                                                        controlLabel(toggle)}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={known[key]}
                                                        disabled={reading ||
                                                            writing ||
                                                            offline ||
                                                            controlsLockedByRecording}
                                                        onchange={() =>
                                                            flipToggle(
                                                                group.group,
                                                                toggle,
                                                            )}
                                                    />
                                                    {controlLabel(toggle)}
                                                </label>
                                            {/each}
                                        </div>
                                    {:else if !reading}
                                        <p class="muted-text">
                                            The device has not been asked yet.
                                            This cannot be read from the data: a
                                            disabled sensor looks exactly like one
                                            that has not reported.
                                        </p>
                                    {/if}

                                    {#if reading || writing}
                                        <p class="muted-text">
                                            Waiting for the device…
                                        </p>
                                    {/if}
                                </div>
                            {/each}

                            {#each resolvedControls.inputs as control (control.id)}
                                <div class="control-group">
                                    <div class="control-group-head">
                                        <span class="control-group-title">
                                            {controlLabel(control)}
                                        </span>
                                        {#if control.read}
                                            <button
                                                type="button"
                                                class="action-btn secondary inspector-action"
                                                disabled={controlPending(control.read) ||
                                                    offline}
                                                onclick={() =>
                                                    sendDeviceCommand(
                                                        selectedNodeControlStreamId!,
                                                        control.read!,
                                                    )}
                                            >
                                                <RefreshCw size={14} />
                                                Read from device
                                            </button>
                                        {/if}
                                    </div>
                                    <p class="muted-text">
                                        {control.description ?? ""}
                                        {#if control.min !== undefined && control.max !== undefined}
                                            Range {control.min}–{control.max}{control.unit
                                                ? ` ${control.unit}`
                                                : ""}.
                                        {/if}
                                    </p>
                                </div>
                            {/each}

                            {#if toggleError}
                                <p class="calib-command-result failed">
                                    {toggleError}
                                </p>
                            {:else if selectedNodeControlAnswer}
                                <p
                                    class="calib-command-result"
                                    class:failed={!selectedNodeControlAnswer.ok}
                                    title={selectedNodeControlAnswer.command}
                                >
                                    {selectedNodeControlAnswer.records.at(-1)
                                        ?.message ??
                                        selectedNodeControlAnswer.error ??
                                        (selectedNodeControlAnswer.ok
                                            ? "Done."
                                            : "No answer.")}
                                </p>
                            {/if}
                        {/if}
                    </div>
                {/if}

                <div class="inspector-section">
                    <p class="eyebrow">Diagnostics</p>
                    {#if graphValidationCount === 0 && runtimeIssues.length === 0 && labelMismatches.length === 0}
                        <div class="diagnostic success">
                            <Check size={14} />
                            <span>No issues.</span>
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

                {#if labelMismatches.length > 0}
                    <div class="inspector-section">
                        <p class="eyebrow">Naming</p>
                        {#each labelMismatches as { label, message }}
                            <div class="diagnostic warn">
                                <span><strong>{label}</strong> — {message}</span>
                            </div>
                        {/each}
                    </div>
                {/if}

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

{/snippet}

{#snippet streamRenderer(
    streamId: string | null,
    compact: boolean,
    showMarkers: boolean = false,
)}
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
    {:else if view.renderer === "marker"}
        <MarkerViewer markers={view.markers} />
    {:else if view.renderer === "classification"}
        <ClassificationViewer samples={view.emgSamples} {formatNumber} />
    {:else if view.renderer === "feature_vector"}
        <FeatureVectorViewer samples={view.emgSamples} {formatNumber} />
    {:else if view.renderer === "channel_frame"}
        {#if view.emgSamples.length > 0}
            <ChannelFrameViewer
                samples={view.emgSamples}
                markers={showMarkers ? view.markers : []}
                {formatNumber}
                {compact}
            />
        {:else}
            <p class="inline-note">Waiting for data…</p>
        {/if}
    {:else if view.renderer === "imu"}
        {#if view.imuSamples.length > 0}
            <ImuViewer samples={view.imuSamples} {formatNumber} {compact} />
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
    {#if (node as { display_mode?: string }).display_mode === "imu_calibration"}
        {@render calibrationReadout(node)}
    {:else}
        {@const streamId = viewableStreamId(node.id)}
        {@render streamRenderer(
            streamId,
            true,
            viewerShowsMarkers(node),
        )}
    {/if}
{/snippet}

<!-- Calibration quality of the upstream IMU while it is worn: the worst-case
     status headline, then each sub-sensor. Colour language matches the IMU
     Experiment tab so the two surfaces cannot disagree. -->
{#snippet calibrationReadout(node: EditorGraphNode)}
    {@const view = calibrationViewFor(node)}
    <div class="calib-panel">
        {#if !view.streamId}
            <p class="inline-note">
                {#if view.unresolvedReason === "unbound_source"}
                    Pick a stream on the upstream Stream node to read its
                    calibration.
                {:else if view.unresolvedReason === "no_source"}
                    Wire this to a Stream node to read its calibration.
                {:else if view.unresolvedReason === "needs_worker"}
                    Start the graph to read calibration — this reads through a
                    transform, which needs the graph running.
                {:else}
                    Start the graph to read calibration.
                {/if}
            </p>
        {:else if view.selectionMissing}
            <p class="inline-note">
                No IMU streams selected. Pick them under IMU Experiment → Stream
                Selection (the choice lives in backend memory, so redo it after a
                backend restart).
            </p>
        {:else if view.streamNotSelected}
            <p class="inline-note">
                This stream is not in the IMU selection — add it under IMU
                Experiment → Stream Selection.
            </p>
        {:else}
            <div class="calib-headline">
                <span class={`calib-dot ${view.overallColor}`}></span>
                <strong>{view.overallLabel}</strong>
                {#if view.position !== "N/A"}
                    <span class="calib-position">{view.position}</span>
                {/if}
            </div>
            {#if view.parts.length > 0}
                <div class="calib-parts">
                    {#each view.parts as part}
                        <div class="calib-part">
                            <span class={`calib-dot ${part.color}`}></span>
                            <span class="calib-part-label">{part.label}</span>
                            <span class="calib-part-value">{part.text}</span>
                        </div>
                    {/each}
                </div>
            {:else}
                <p class="inline-note">
                    No accuracy reported for this stream yet.
                </p>
            {/if}
        {/if}

        <!-- Deliberately OUTSIDE the branches above: these talk to the sensor and
             need nothing but its stream id. Nesting them under the "accuracy is
             readable" branch made them vanish whenever the IMU selection was
             missing -- which is exactly when you want to ask the device what it
             thinks its calibration is. -->
        {#if view.streamId}
            <!-- Commands to the sensor itself, over the EXECUTION_COMMAND
                 channel. "Save to device" matters because the hub only writes
                 dynamic calibration to flash on a non-power-up reset, so a board
                 that is simply switched off forgets what it learned. -->
            {@const savePending =
                deviceCommandPending[
                    `${view.streamId}:calibrate.save_dcd`
                ] === true}
            {@const statusPending =
                deviceCommandPending[`${view.streamId}:calibrate.status`] ===
                true}
            {@const result = deviceCommandResults[view.streamId]}
            <div
                class="calib-commands"
                onmousedown={(e) => e.stopPropagation()}
                role="presentation"
            >
                <button
                    type="button"
                    class="calib-command-btn"
                    disabled={savePending}
                    title="Persist the sensor's current calibration to its flash, so it survives a power cycle"
                    onclick={(e) => {
                        e.stopPropagation();
                        sendDeviceCommand(
                            view.streamId!,
                            "calibrate.save_dcd",
                        );
                    }}
                >
                    {savePending ? "Saving…" : "Save to device"}
                </button>
                <button
                    type="button"
                    class="calib-command-btn"
                    disabled={statusPending}
                    title="Ask the sensor what calibration it has enabled and what accuracy it reports"
                    onclick={(e) => {
                        e.stopPropagation();
                        sendDeviceCommand(view.streamId!, "calibrate.status");
                    }}
                >
                    {statusPending ? "Reading…" : "Read config"}
                </button>
            </div>
            {#if result}
                <p
                    class="calib-command-result"
                    class:failed={!result.ok}
                    title={result.command}
                >
                    {result.records.at(-1)?.message ??
                        result.error ??
                        (result.ok ? "Done." : "No answer.")}
                </p>
            {/if}
        {/if}
    </div>
{/snippet}

{#snippet instanceBranch(entry: { graph: StreamGraphDefinition; children: any[] }, depth: number)}
    <!-- `data-graph-id` is an explicit, stable handle. The `title` below is the
         run's MESSAGE when it has one, so keying on the title identifies a row
         only for runs that finished cleanly — which is how a test looking for a
         FAILED run concluded it was missing from the tree entirely
         (TEC-NATKIT-80). -->
    {@const status = entry.graph.recording?.status ?? "unknown"}
    {@const rows = entry.graph.recording?.artifacts?.total_rows}
    <button
        type="button"
        class="tree-instance"
        class:selected={entry.graph.graph_id === selectedGraphId}
        style={`padding-left: ${0.5 + depth * 0.7}rem`}
        data-graph-id={entry.graph.graph_id}
        title={entry.graph.recording?.message ?? entry.graph.graph_id}
        onclick={() => selectGraph(entry.graph.graph_id)}
    >
        <span class="tree-instance-id">
            {entry.graph.origin === "fork" ? "↳ " : ""}{entry.graph.instance_id}
        </span>
        <span class={`tree-instance-status ${status}`}>
            {status === "complete"
                ? `${rows ?? 0} rows`
                : status === "failed"
                  ? "failed"
                  : status}
        </span>
    </button>
    {#each entry.children as child}
        {@render instanceBranch(child, depth + 1)}
    {/each}
{/snippet}

{#snippet inlineExperiment(node: EditorGraphNode)}
    {#if node.kind === "markers" || node.kind === "experiment"}
        {@const view = experimentRunView()}
        {#if view && boundExperimentView}
            <ExperimentRunner
                protocolLabel={view.protocolLabel}
                protocol={view.protocol}
                classes={view.classes}
                recording={view.recording}
                recordingElsewhere={view.recordingElsewhere}
                elapsedMs={view.elapsedMs}
                durationMs={view.durationMs}
                activeCue={view.activeCue}
                nextCue={view.nextCue}
                totalReps={view.totalReps}
                currentRep={view.currentRep}
                holdsRemaining={view.holdsRemaining}
                holdsTotal={view.holdsTotal}
                summary={view.summary}
                onRecord={() => startSessionRecording(boundExperimentView)}
                onStop={() => finishSessionRecording(false)}
                onContinue={continueSessionWait}
            />
        {:else}
            <p class="inline-note">
                No experiment bound to this board — bind one from the Experiment
                panel to run a protocol.
            </p>
        {/if}
    {/if}
{/snippet}

<div
    class="graph-editor"
    style={`--panel-top: ${toolbarHeight + 28}px`}
>
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
            {#if boardDefinitions.length === 0}
                <div class="empty-state">
                    <Workflow size={18} />
                    <p>No saved graphs yet.</p>
                </div>
            {:else}
                {#each boardDefinitions as graph}
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
            <div class="library-header-row">
                <span class="library-title">Experiments &amp; history</span>
            </div>
            <div class="library-actions">
                {#if experimentTree.length === 0}
                    <div class="empty-state">
                        <p>
                            No experiments yet. Bind one to a board from the header
                            to start recording.
                        </p>
                    </div>
                {:else}
                    {#each experimentTree as branch}
                        <div class="tree-experiment">
                            <button
                                type="button"
                                class="tree-experiment-row"
                                class:bound={branch.experiment.experiment_id ===
                                    boundExperimentId}
                                title={`Open this experiment's board (${branch.experiment.live_graph_id || "no board bound"})`}
                                onclick={() =>
                                    branch.experiment.live_graph_id &&
                                    selectGraph(branch.experiment.live_graph_id)}
                            >
                                <FlaskConical size={13} />
                                <span class="tree-experiment-label">
                                    {branch.experiment.label ||
                                        branch.experiment.experiment_id}
                                </span>
                                <span class="tree-count">
                                    {branch.instances.length}
                                </span>
                            </button>
                            {#each branch.instances as instance}
                                {@render instanceBranch(instance, 1)}
                            {/each}
                        </div>
                    {/each}
                {/if}
            </div>
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

        <div class="library-group">
            <div class="library-header-row">
                <span class="library-title">Profiles</span>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={saveCurrentAsProfile}
                    title="Save the current saved graph as a profile"
                >
                    <UserPlus size={16} />
                </button>
            </div>
            <div class="library-actions">
                {#if profiles.length === 0}
                    <div class="empty-state">
                        <p>
                            No profiles yet. Train a person's classifier, save the
                            graph, then save it as a profile to resume later.
                        </p>
                    </div>
                {:else}
                    {#each profiles as profile}
                        <div class="profile-row">
                            <button
                                type="button"
                                class="graph-list-item profile-load"
                                title={`Resume ${profile.display_name}'s classifier`}
                                onclick={() => loadProfile(profile)}
                            >
                                <span class="graph-list-title"
                                    >{profile.display_name}</span
                                >
                                <span class="graph-list-meta">
                                    {profile.best_accuracy > 0
                                        ? `${(profile.best_accuracy * 100).toFixed(0)}% · `
                                        : ""}{profile.graph_id}
                                </span>
                            </button>
                            <button
                                type="button"
                                class="icon-btn"
                                title={`Delete ${profile.display_name}`}
                                onclick={() => removeProfile(profile)}
                            >
                                <Trash2 size={14} />
                            </button>
                        </div>
                    {/each}
                {/if}
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
                    <!-- ⚠️ ONE ENTRY, not one per live stream. The old palette
                         changed shape with the rig, so a board could not be laid
                         out before the hardware was on and the same board offered
                         different nodes on different days. Which stream this
                         carries is chosen in the inspector. -->
                    <button
                        type="button"
                        class="graph-list-item"
                        onclick={() => addSourceNode()}
                    >
                        <span class="graph-list-title">Stream</span>
                        <span class="graph-list-meta">
                            {availableStreams.length} available — pick one after
                            adding
                        </span>
                    </button>
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
        <div class="graph-toolbar" bind:clientHeight={toolbarHeight}>
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
                <!-- Workspace picker (TEC-NATKIT-56). First in the toolbar
                     because it scopes everything to its right: which boards are
                     listed, which experiments can be bound, whose names the
                     participant roster offers. -->
                <div class="workspace-picker">
                    <FolderOpen size={14} />
                    <select
                        class="workspace-select"
                        bind:value={workspaceSelectValue}
                        onchange={(event) => {
                            const picked = (
                                event.currentTarget as HTMLSelectElement
                            ).value;
                            selectWorkspace(picked === "" ? null : picked);
                        }}
                        title="Workspace — scopes the boards, experiments and participant roster"
                    >
                        <!-- Unfiled is a real view, not a migration artifact:
                             everything that predates workspaces lives here. -->
                        <option value="">Unfiled</option>
                        {#each workspaces as workspace}
                            <option value={workspace.workspace_id}>
                                {workspace.label || workspace.workspace_id}
                            </option>
                        {/each}
                    </select>
                    <button
                        type="button"
                        class="icon-btn"
                        onclick={createWorkspace}
                        title="New workspace"
                    >
                        <Plus size={14} />
                    </button>
                    {#if selectedWorkspace}
                        <button
                            type="button"
                            class="icon-btn"
                            onclick={renameWorkspace}
                            title="Rename this workspace"
                        >
                            <Pencil size={13} />
                        </button>
                        <button
                            type="button"
                            class="icon-btn"
                            onclick={removeWorkspace}
                            title="Delete this workspace — its contents move to Unfiled"
                        >
                            <Trash2 size={13} />
                        </button>
                    {/if}
                    <button
                        type="button"
                        class="icon-btn"
                        onclick={downloadCohort}
                        disabled={cohortDownload.status === "downloading"}
                        title="Download every completed run in this workspace as one archive"
                    >
                        <Download size={13} />
                    </button>
                    {#if cohortDownload.status !== "idle"}
                        <span
                            class="cohort-status"
                            class:failed={cohortDownload.status === "failed"}
                            title={cohortDownload.message}
                        >
                            {cohortDownload.status === "downloading"
                                ? "Collecting…"
                                : cohortDownload.message}
                        </span>
                    {/if}
                    {#if hiddenTotal > 0}
                        <span
                            class="workspace-hidden"
                            title={`Filed in other workspaces: ${hiddenCounts.graphs} board(s), ${hiddenCounts.experiments} experiment(s), ${hiddenCounts.profiles} participant(s). Switch workspace to see them.`}
                        >
                            {hiddenTotal} in other workspaces
                        </span>
                    {/if}
                </div>
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
                {#if boardIsImmutable}
                    <span class="immutable-pill" title="Recorded snapshot — read-only">
                        Immutable
                    </span>
                {/if}
                <button
                    type="button"
                    class="experiment-pill"
                    class:bound={boundExperimentView !== null}
                    onclick={() => (showExperimentPanel = !showExperimentPanel)}
                    title="Bind an experiment, author its protocol, and record"
                >
                    <FlaskConical size={13} />
                    {boundExperimentView
                        ? boundExperimentView.label ||
                          boundExperimentView.experiment_id
                        : "No experiment"}
                </button>
                {#if sessionRecording}
                    <span class="recording-pill">
                        ● REC {(sessionRecording.elapsedMs / 1000).toFixed(0)}s
                    </span>
                {/if}
                <span
                    class="conn-pill {connectionState}"
                    title={`Backend: ${connectionState}`}
                >
                    <span class="conn-dot"></span>
                    {connectionState === "connected"
                        ? "Connected"
                        : connectionState === "connecting"
                          ? "Connecting…"
                          : "Disconnected"}
                </span>
                <!-- Next to the connection pill on purpose: "is the backend
                     there?" and "is the rig there?" are the same question asked
                     of two different things, and they are asked together. -->
                <DeviceHealthPanel
                    health={deviceHealth}
                    {connectionState}
                    {sendDeviceCommand}
                    {deviceCommandPending}
                    {deviceCommandResults}
                />
            </div>
            <div class="toolbar-actions">
                {#if boardIsImmutable}
                    <!-- A sealed recording has no live input, so "Start" is
                         meaningless here — but replaying it is exactly the
                         equivalent action, so the primary button becomes that
                         rather than a greyed-out control that does nothing. Mode
                         and speed stay in the Instance panel. -->
                    {#if replayForSelectedInstance}
                        <button
                            type="button"
                            class="action-btn secondary"
                            onclick={stopSelectedReplay}
                            title="Stop replaying this recording"
                        >
                            <Square size={16} />
                            Stop replay
                        </button>
                    {:else}
                        <button
                            type="button"
                            class="action-btn secondary"
                            onclick={replaySelectedInstance}
                            disabled={!canReplaySelectedInstance}
                            title={canReplaySelectedInstance
                                ? "Replay this recording through the board's pipeline (mode and speed in the Instance panel)"
                                : "This recording has no materialised data to replay"}
                        >
                            <Play size={16} />
                            Replay
                        </button>
                    {/if}
                {:else}
                    <button
                        type="button"
                        class="action-btn secondary"
                        onclick={startSelectedGraph}
                        disabled={selectedGraphStatus?.run_state === "starting"}
                        title="Start this graph"
                    >
                        {#if selectedGraphStatus?.run_state === "starting"}
                            <RefreshCw size={16} class="spin" />
                            Starting…
                        {:else}
                            <Play size={16} />
                            Start
                        {/if}
                    </button>
                {/if}
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
                    class:active={showTimeline}
                    onclick={() => (showTimeline = !showTimeline)}
                    title={showTimeline ? "Hide timeline" : "Show timeline"}
                    aria-pressed={showTimeline}
                >
                    <Clock size={16} />
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
            <!-- The board is a pan/zoom drawing surface: role="application" is the
                 honest role and it needs focus for keyboard panning, but Svelte's
                 checker only accepts tabindex/mouse handlers on widget roles. -->
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
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
                <!-- contextmenu bubbles to .graph-canvas above, and openContextMenu
                     reads only clientX/clientY — inner handlers would be redundant. -->
                <div class="canvas-grid"></div>
                <svg class="graph-edges">
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
                            {@const lines = edgeLines(edge, sourcePoint, targetPoint)}
                            {#each lines as line, lineIndex}
                                <path
                                    class:selected={edge.id === selectedEdgeId}
                                    class:edge-invalid={edgeDiagnostics(edge.id)
                                        .length > 0}
                                    class:edge-provenance={edge.edge_kind ===
                                        "provenance"}
                                    class:edge-running={selectedGraphStatus?.run_state ===
                                        "running" && edge.edge_kind !== "provenance"}
                                    class:edge-markers={line.type === "Marker"}
                                    class="graph-edge"
                                    d={line.d}
                                />
                            {/each}
                            <!-- ⚠️ The CLICK TARGET is this invisible 18px-wide
                                 path, not the 3px line above. Selecting an edge
                                 was the only way to delete one and it needed a
                                 pixel-perfect hit; edges were effectively
                                 undeletable. Drawn after the visible lines so it
                                 sits on top, and with no stroke of its own so it
                                 never changes what is seen. -->
                            <path
                                class="graph-edge-hit"
                                role="button"
                                tabindex="0"
                                aria-label={`Link ${edge.source_node_id} to ${edge.target_node_id}`}
                                d={lines[0].d}
                                onmousedown={(event) => event.stopPropagation()}
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
                            {#if edge.id === selectedEdgeId && !boardIsImmutable}
                                {@const midX = (sourcePoint.x + targetPoint.x) / 2}
                                {@const midY = (sourcePoint.y + targetPoint.y) / 2}
                                <g
                                    class="edge-delete"
                                    role="button"
                                    tabindex="0"
                                    aria-label="Delete this link"
                                    onmousedown={(event) => {
                                        // ⚠️ Without this the canvas's mousedown
                                        // runs FIRST and clears the selection, so
                                        // the click that follows asks to remove
                                        // the selected item and finds none — the
                                        // button appeared to do nothing at all.
                                        event.stopPropagation();
                                    }}
                                    onclick={(event) => {
                                        event.stopPropagation();
                                        removeSelectedItem();
                                    }}
                                    onkeydown={(event) => {
                                        if (
                                            event.key === "Enter" ||
                                            event.key === " "
                                        ) {
                                            event.preventDefault();
                                            event.stopPropagation();
                                            removeSelectedItem();
                                        }
                                    }}
                                >
                                    <circle cx={midX} cy={midY} r="10" />
                                    <path
                                        d={`M ${midX - 3.5} ${midY - 3.5} L ${
                                            midX + 3.5
                                        } ${midY + 3.5} M ${midX + 3.5} ${
                                            midY - 3.5
                                        } L ${midX - 3.5} ${midY + 3.5}`}
                                    />
                                </g>
                            {/if}
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
                    style={`transform: translate(${draftGraph.ui?.viewport?.x ?? 0}px, ${
                        draftGraph.ui?.viewport?.y ?? 0
                    }px) scale(${draftGraph.ui?.viewport?.zoom ?? 1});`}
                >
                    {#each draftGraph.nodes as node}
                        <StreamGraphNodeCard
                            {node}
                            runtimeStatus={nodeRuntimeStatus(node.id)}
                            {marbleAxisEndUs}
                            {backendNowUs}
                            selected={selectedNodeIds.has(node.id)}
                            invalid={nodeDiagnostics(node.id).length > 0}
                            {pendingConnection}
                            {inlineViewerChart}
                            {inlineExperiment}
                            boundExperimentLabel={boundExperimentView
                                ? boundExperimentView.label ||
                                  boundExperimentView.experiment_id
                                : null}
                            {streamDeviceNames}
                            inputPortLabels={inputPortLabelsFor(node)}
                            outputPortLabels={outputPortLabelsFor(node)}
                            sourceLabel={node.kind === "viewer" ||
                            node.kind === "sink"
                                ? viewerSourceLabel(node)
                                : undefined}
                            markersPhantom={viewerMarkersPhantom(node)}
                            onToggleMarkers={toggleViewerMarkers}
                            onPortLayout={handlePortLayout}
                            onResize={handleNodeResize}
                            onToggleInlineGraph={setInlineViewerGraph}
                            onToggleInlineExperiment={setInlineExperiment}
                            onSelect={selectNode}
                            onOpenDetail={openNodeDetail}
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

                    <!-- Part C: per-edge topic badge at the link midpoint. -->
                    {#each draftGraph.edges as edge (edge.id)}
                        {@const sourceNode = draftGraph.nodes.find(
                            (n) => n.id === edge.source_node_id,
                        )}
                        {@const targetNode = draftGraph.nodes.find(
                            (n) => n.id === edge.target_node_id,
                        )}
                        {#if sourceNode && targetNode && edge.edge_kind !== "provenance"}
                            {@const sp = getPortPoint(
                                sourceNode,
                                edge.source_port,
                                "output",
                            )}
                            {@const tp = getPortPoint(
                                targetNode,
                                edge.target_port,
                                "input",
                            )}
                            {@const topics = edgeChannelTopics(edge)}
                            {#if topics.length > 0}
                                {@const enabledCount = topics.filter(
                                    (t) => !isEdgeTopicHidden(edge, t.type),
                                ).length}
                                <div
                                    class="edge-badge-wrap"
                                    style={`left:${(sp.x + tp.x) / 2}px; top:${
                                        (sp.y + tp.y) / 2
                                    }px;`}
                                >
                                    <button
                                        type="button"
                                        class="edge-badge"
                                        class:multi={topics.length > 1}
                                        class:quiet={topics.length === 1 &&
                                            enabledCount === topics.length &&
                                            openBadgeEdgeId !== edge.id}
                                        class:filtered={enabledCount <
                                            topics.length}
                                        title={`${enabledCount} of ${
                                            topics.length
                                        } topic${
                                            topics.length > 1 ? "s" : ""
                                        } active on this link`}
                                        onmousedown={(e) => e.stopPropagation()}
                                        onclick={(e) => {
                                            e.stopPropagation();
                                            openBadgeEdgeId =
                                                openBadgeEdgeId === edge.id
                                                    ? null
                                                    : edge.id;
                                        }}
                                    >
                                        {enabledCount < topics.length
                                            ? `${enabledCount}/${topics.length}`
                                            : topics.length}
                                    </button>
                                    {#if openBadgeEdgeId === edge.id}
                                        <div
                                            class="edge-badge-menu"
                                            onmousedown={(e) =>
                                                e.stopPropagation()}
                                            role="presentation"
                                        >
                                            <div class="edge-badge-hint">
                                                Toggle which topics reach {targetNode.label ??
                                                    targetNode.kind}
                                            </div>
                                            {#each topics as t}
                                                {@const hidden = isEdgeTopicHidden(
                                                    edge,
                                                    t.type,
                                                )}
                                                <label
                                                    class="edge-badge-row"
                                                    class:row-hidden={hidden}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={!hidden}
                                                        onchange={() =>
                                                            toggleEdgeTopic(
                                                                edge.id,
                                                                t.type,
                                                            )}
                                                    />
                                                    <span
                                                        class="badge-type badge-type-{t.type.toLowerCase()}"
                                                    >
                                                        {t.type}
                                                    </span>
                                                    <span class="badge-schema"
                                                        >{t.schema || "—"}</span
                                                    >
                                                    {#if t.id}
                                                        <span class="badge-id"
                                                            >#{t.id}</span
                                                        >
                                                    {/if}
                                                </label>
                                            {/each}
                                        </div>
                                    {/if}
                                </div>
                            {/if}
                        {/if}
                    {/each}
                </div>

                {#if draftGraph.nodes.length === 0}
                    <div class="canvas-empty">
                        <Activity size={18} />
                        <p>Right-click the board to add a source, transform, viewer, or sink.</p>
                    </div>
                {/if}

                <!-- Compact time readout. pointer-events: none is deliberate —
                     it floats over the canvas and must never swallow a drag,
                     a right-click, or a node click. -->
                <div class={`time-readout ${timeReadout.kind}`}>
                    <span class="time-readout-badge">{timeReadout.label}</span>
                    <span class="time-readout-clock" title="Wall-clock time">
                        <Clock size={12} />
                        {timeReadout.clock}
                    </span>
                    <span
                        class="time-readout-elapsed"
                        title="Time since this run started"
                    >
                        {timeReadout.elapsed}{#if timeReadout.total}<span
                                class="time-readout-total"
                                >/ {timeReadout.total}</span
                            >{/if}
                    </span>
                    {#if timeReadout.detail}
                        <span class="time-readout-detail">{timeReadout.detail}</span>
                    {/if}
                    {#if timeReadout.kind === "replay" && timeReadout.total}
                        <span class="time-readout-track">
                            <span
                                class="time-readout-fill"
                                style={`width:${(timeReadout.fraction * 100).toFixed(1)}%`}
                            ></span>
                        </span>
                    {/if}
                </div>
            </div>

            {#if showExperimentPanel}
                <div class="graph-experiment-panel">
                    <ExperimentPanel
                        {experiments}
                        {workspaces}
                        {selectedWorkspaceId}
                        {hardBlockReason}
                        {calibrationWarning}
                        bound={boundExperimentView}
                        boardId={selectedGraphId}
                        readOnly={boardIsImmutable}
                        summary={boundExperimentSummary}
                        recordedDevices={recordedDeviceIds}
                        recording={sessionRecording &&
                        boundExperimentView &&
                        sessionRecording.experimentId ===
                            boundExperimentView.experiment_id
                            ? {
                                  sessionId: sessionRecording.sessionId,
                                  elapsedMs: sessionRecording.elapsedMs,
                                  durationMs: sessionRecording.durationMs,
                                  activeCue: activeSessionCue,
                              }
                            : null}
                        recordingElsewhere={sessionRecording !== null &&
                            sessionRecording.experimentId !==
                                boundExperimentView?.experiment_id}
                        message={sessionRecordMessage}
                        instances={boundExperimentInstances}
                        onDeleteInstance={deleteInstance}
                        onBind={bindExperiment}
                        onCreate={createExperiment}
                        onPatch={patchBoundExperiment}
                onEditProtocol={() => {
                            designerInitialView = "list";
                            showExperimentDesigner = true;
                        }}
                        onDelete={deleteBoundExperiment}
                        onRecord={() =>
                            boundExperimentView &&
                            startSessionRecording(boundExperimentView)}
                        onStop={() => finishSessionRecording(false)}
                onContinue={continueSessionWait}
                    />
                </div>
            {/if}

            <div class="graph-inspector" class:panel-hidden={!showInspector}>
                {@render inspectorGraphSection()}
                {@render inspectorBody()}
                {@render inspectorRuntimeCard()}
                {@render inspectorGeneratedJson()}
            </div>
        </div>

        {#if showTimeline}
            <div class="timeline-dock">
                <div class="experiment-library">
                    <span class="lib-title">Experiments</span>
                    <button
                        type="button"
                        class="lib-refresh"
                        onclick={requestRecordedRuns}
                        title="Refresh recorded experiments"
                    >
                        <RefreshCw size={13} />
                    </button>
                    {#if recordedRuns.length === 0}
                        <span class="lib-empty">No recorded experiments — refresh, or record one.</span>
                    {:else}
                        <div class="lib-list">
                            {#each recordedRuns as run}
                                <button
                                    type="button"
                                    class="lib-item"
                                    class:selected={currentTimeContext().sessionId === run.session_id}
                                    onclick={() => loadExperiment(run)}
                                    title={`${run.session_id} · run ${run.run_index}`}
                                >
                                    <span class="lib-item-name">{run.session_id}</span>
                                    <span class="lib-item-meta"
                                        >{run.protocol_id} · {run.marker_count} markers · {run.device_ids.length} stream(s)</span
                                    >
                                </button>
                            {/each}
                        </div>
                    {/if}
                </div>
                <TimelineStrip
                    mode={currentTimeContext().mode}
                    speed={currentTimeContext().speed}
                    playing={currentTimeContext().playing}
                    {playheadFraction}
                    {atLiveEdge}
                    ticks={timelineTicks}
                    regions={timelineRegions}
                    startLabel={formatClock(timelineWindow.startUs)}
                    endLabel={formatClock(timelineWindow.endUs)}
                    playheadLabel={formatClock(currentTimeContext().playheadUs)}
                    recording={sessionRecording !== null}
                    onScrub={timelineScrub}
                    onJumpToLive={timelineJumpToLive}
                    onTogglePlay={timelineTogglePlay}
                    onSpeedChange={timelineSetSpeed}
                    onReprocess={timelineReprocess}
                />
            </div>
        {/if}
    </div>

    <!-- NODE DETAIL VIEW (TEC-NATKIT-124). Double-click a node to work on it
         full-screen instead of reading a ~1,700-line inspector through a narrow
         right-hand rail.

         ⚠️ It renders the SAME inspectorBody snippet the sidebar does, against
         the SAME selectedNodeId — no second copy of the markup and no state of
         its own, so the two can never disagree about what is being edited or
         drift apart as the inspector grows. -->
    {#if detailNode}
        <div
            class="node-detail-backdrop"
            role="presentation"
            onmousedown={closeNodeDetail}
        >
            <div
                class="node-detail"
                role="dialog"
                aria-modal="true"
                aria-label={`${detailNode.label || detailNode.id} details`}
                onmousedown={(event) => event.stopPropagation()}
            >
                <header class="node-detail-header">
                    <div class="node-detail-title">
                        <strong>{detailNode.label || detailNode.id}</strong>
                        <span class="node-detail-kind">{detailNode.kind}</span>
                        {#if nodeRuntimeStatus(detailNode.id)}
                            <span
                                class={`node-runtime-badge ${graphRunStateClass(
                                    nodeRuntimeStatus(detailNode.id)?.state ??
                                        "draft",
                                )}`}
                            >
                                {graphRunStateLabel(nodeRuntimeStatus(detailNode.id)?.state)}
                            </span>
                        {/if}
                    </div>
                    <div class="node-detail-actions">
                        <!-- The kinds that used to expand on double-click keep
                             that action here, as a labelled button rather than a
                             gesture that meant three different things depending
                             on which node you happened to be over. -->
                        {#if ["composite", "viewer", "stream_source", "markers", "experiment"].includes(detailNode.kind)}
                            <button
                                type="button"
                                class="action-btn"
                                onclick={() => {
                                    const id = detailNode.id;
                                    closeNodeDetail();
                                    handleNodeExpand(id);
                                }}
                            >
                                <Maximize2 size={14} />
                                {detailNode.kind === "composite"
                                    ? "Open internals"
                                    : detailNode.kind === "markers" ||
                                        detailNode.kind === "experiment"
                                      ? "Open experiment"
                                      : "Open data"}
                            </button>
                        {/if}
                        <button
                            type="button"
                            class="icon-btn"
                            onclick={closeNodeDetail}
                            title="Close (Esc)"
                            aria-label="Close node details"
                        >
                            <X size={16} />
                        </button>
                    </div>
                </header>
                <div class="node-detail-body">
                    <!-- The node exactly as it appears on the canvas, so the
                         thing being edited is visible beside the fields editing
                         it. ⚠️ The SAME component, in preview mode — a second
                         rendering of "what a node looks like" would drift from
                         the real card the first time either changed. -->
                    <aside class="node-detail-preview">
                        <StreamGraphNodeCard
                            node={detailNode}
                            runtimeStatus={nodeRuntimeStatus(detailNode.id)}
                            {marbleAxisEndUs}
                            {backendNowUs}
                            preview
                            selected={false}
                            invalid={nodeDiagnostics(detailNode.id).length > 0}
                            pendingConnection={null}
                            boundExperimentLabel={boundExperimentView
                                ? boundExperimentView.label ||
                                  boundExperimentView.experiment_id
                                : null}
                            {streamDeviceNames}
                            inputPortLabels={inputPortLabelsFor(detailNode)}
                            onSelect={() => {}}
                            onStartDrag={() => {}}
                            onPortClick={() => {}}
                            onPortMouseDown={() => {}}
                        />
                        {#if nodeDiagnostics(detailNode.id).length > 0}
                            <ul class="node-detail-diagnostics">
                                {#each nodeDiagnostics(detailNode.id) as diagnostic}
                                    <li>{diagnostic.message}</li>
                                {/each}
                            </ul>
                        {/if}
                        <!-- What the node IS and what it is doing lives with the
                             node; the right pane is then purely the fields you
                             edit. It also fills a column that was otherwise a
                             small card above a lot of nothing. -->
                        {@render inspectorRuntimeCard()}
                    </aside>
                    <div class="node-detail-fields">
                        {@render inspectorBody()}
                    </div>
                </div>
            </div>
        </div>
    {/if}

    {#if contextMenu.open}
        <div
            class="context-menu"
            role="menu"
            tabindex="-1"
            style={`left:${contextMenu.x}px; top:${contextMenu.y}px;`}
            onmousedown={(event) => event.stopPropagation()}
        >
            <!-- A titled, searchable, closable palette. It had none of the
                 three: no heading saying what it was, no way to filter
                 seventeen transforms, and no close control except clicking
                 away. -->
            <div class="context-header">
                <span class="context-heading">Add node</span>
                <button
                    type="button"
                    class="context-close"
                    title="Close (Esc)"
                    aria-label="Close the node palette"
                    onclick={closeContextMenu}
                >
                    <X size={14} />
                </button>
            </div>
            <input
                class="context-search"
                type="search"
                placeholder="Search nodes…"
                aria-label="Filter nodes"
                bind:value={paletteFilter}
                onkeydown={(event) => event.stopPropagation()}
            />
            {#if paletteMatches("stream", "source")}
                <div class="context-group">
                    <span class="context-title">Streams</span>
                    <button
                        type="button"
                        class="context-item"
                        onclick={() => addSourceNode()}
                    >
                        <span>Stream</span>
                        <small>pick the stream in the inspector</small>
                    </button>
                </div>
            {/if}
            {#if transformCapabilities.some((c) => paletteMatches(c.label, c.kind))}
            <div class="context-group">
                <span class="context-title">Transforms</span>
                {#each transformCapabilities.filter((c) => paletteMatches(c.label, c.kind)) as capability}
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
            {/if}
            {#if utilityCatalog.some((e) => paletteMatches(e.label, e.description, e.kind))}
            <div class="context-group">
                <span class="context-title">Utility</span>
                {#each utilityCatalog.filter((e) => paletteMatches(e.label, e.description, e.kind)) as entry}
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
            {/if}
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

<!-- One host renders whichever in-app dialog is pending; it sits above the
     designer and composite overlays. -->
<DialogHost />

{#if showExperimentDesigner && boundExperimentView}
    <ExperimentDesigner
        bound={boundExperimentView}
        readOnly={boardIsImmutable}
        initialView={designerInitialView}
        onPatch={patchBoundExperiment}
        onPatchProtocol={patchBoundProtocol}
        onClose={() => (showExperimentDesigner = false)}
    />
{/if}

{#if expandedComposite}
    {@const layout = compositeInternalsLayout(expandedComposite)}
    <div
        class="composite-internals-overlay"
        role="presentation"
        onclick={(event) => {
            // Only a click on the backdrop itself dismisses; clicks inside the
            // panel bubble up here and are ignored.
            if (event.target === event.currentTarget) closeCompositeInternals();
        }}
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
            use:focusOnOpen
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
        onclick={(event) => {
            if (event.target === event.currentTarget) closeViewerData();
        }}
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
            use:focusOnOpen
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
                    expandedViewerNode
                        ? viewerShowsMarkers(expandedViewerNode)
                        : false,
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

{#if expandedExperimentNode && experimentRunView() && boundExperimentView}
    {@const view = experimentRunView()!}
    <div
        class="viewer-data-overlay experiment-modal-overlay"
        role="presentation"
        onclick={(event) => {
            if (event.target === event.currentTarget) expandedExperimentNodeId = null;
        }}
        onkeydown={(event) => {
            if (event.key === "Escape") expandedExperimentNodeId = null;
        }}
    >
        <div
            class="viewer-data-panel experiment-modal-panel"
            role="dialog"
            tabindex="-1"
            aria-label="Run experiment"
            use:focusOnOpen
        >
            <div class="viewer-data-header">
                <div>
                    <p class="eyebrow">Experiment</p>
                    <h3>
                        {boundExperimentView.label ||
                            boundExperimentView.experiment_id}
                    </h3>
                </div>
                <button
                    type="button"
                    class="icon-btn"
                    onclick={() => (expandedExperimentNodeId = null)}
                >
                    <X size={16} />
                </button>
            </div>
            <div class="viewer-data-body experiment-modal-body">
                <ExperimentRunner
                    large
                    protocolLabel={view.protocolLabel}
                    protocol={view.protocol}
                    classes={view.classes}
                    recording={view.recording}
                    recordingElsewhere={view.recordingElsewhere}
                    elapsedMs={view.elapsedMs}
                    durationMs={view.durationMs}
                    activeCue={view.activeCue}
                    nextCue={view.nextCue}
                    totalReps={view.totalReps}
                    currentRep={view.currentRep}
                    holdsRemaining={view.holdsRemaining}
                    holdsTotal={view.holdsTotal}
                    summary={view.summary}
                    onRecord={() => startSessionRecording(boundExperimentView)}
                    onStop={() => finishSessionRecording(false)}
                onContinue={continueSessionWait}
                />
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
                        value={`stream ${stream.streamId} ${displayStream(stream.streamId)} ${stream.schemaName}`}
                        onSelect={() =>
                            runPaletteAction(() =>
                                addSourceNode(stream.streamId),
                            )}
                    >
                        <CircleDot size={16} />
                        <span>{displayStream(stream.streamId)}</span>
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

    /* ⚠️ .graph-sidebar and .graph-inspector were in this selector list and did
       NOT belong: they are absolutely-positioned COLUMN panels with their own
       complete rules further down, while this styles a small horizontal control
       in the toolbar. Everything the panels' own rules did not happen to
       override leaked in — and `align-items: center` is the one that showed.
       On a column flex it makes children shrink-to-fit and centre, so anything
       wider than the panel (a long stream label, an action row) overflowed
       EQUALLY ON BOTH SIDES and was clipped left and right. That is why the
       inspector read "NSPECTOR", "abel", "ource stream".
       `border-right` and `margin-right` were leaking too. */
    /* Workspace picker (TEC-NATKIT-56). Grouped and set apart from the board
       title beside it: the two are different scopes, and reading them as one
       control is how you record into the wrong cohort. */
    .workspace-picker {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        padding-right: 0.5rem;
        margin-right: 0.25rem;
        border-right: 1px solid rgba(255, 255, 255, 0.12);
        color: #9fb2c8;
    }

    .workspace-select {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 4px;
        color: #e8eef6;
        font-size: 0.76rem;
        padding: 0.15rem 0.3rem;
        max-width: 11rem;
    }

    .cohort-status {
        font-size: 0.68rem;
        color: #86e3a8;
        max-width: 22rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .cohort-status.failed {
        color: #fca5a5;
    }

    .workspace-hidden {
        font-size: 0.68rem;
        color: #8b9bb0;
        white-space: nowrap;
    }

    /* Position clash. Deliberately the warning colour rather than an error: the
       board is still savable, it is RECORDING that must be refused. */
    .clock-record {
        margin-top: 0.35rem;
        padding-top: 0.35rem;
        border-top: 1px solid #1e2632;
    }

    .clock-clean { color: #4ade80; }
    .clock-troubled { color: #fbbf24; }

    .clock-device {
        display: flex;
        flex-direction: column;
        gap: 0.05rem;
        margin-top: 0.25rem;
        font-size: 0.74rem;
    }

    .clock-device-id {
        color: #93c5fd;
        font-family: ui-monospace, monospace;
    }

    .clock-note {
        color: #7f8ea3;
        line-height: 1.35;
    }

    .clock-note.ok { color: #94a3b8; }
    .clock-note.bad { color: #fcd34d; }

    .clock-fit-row {
        display: grid;
        grid-template-columns: auto 1fr;
        grid-template-areas: "dot state" ". detail";
        gap: 0.15rem 0.4rem;
        align-items: baseline;
        margin-top: 0.4rem;
        font-size: 0.78rem;
    }

    .clock-fit-row .clock-dot {
        grid-area: dot;
        width: 0.45rem;
        height: 0.45rem;
        border-radius: 50%;
        background: #64748b;
        align-self: center;
    }

    .clock-state {
        grid-area: state;
        color: #cbd5e1;
    }

    .clock-detail {
        grid-area: detail;
        color: #7f8ea3;
        line-height: 1.4;
    }

    .clock-ok .clock-dot { background: #4ade80; }
    /* Two colours: RED means the hub says there is no usable fit, AMBER means we
       have stopped hearing from the device and cannot say. */
    .clock-no_fit .clock-dot { background: #f87171; }
    .clock-no_fit .clock-state { color: #fca5a5; }
    .clock-stale .clock-dot { background: #fbbf24; }
    .clock-stale .clock-state { color: #fcd34d; }

    .position-clash {
        margin: 0.2rem 0 0;
        font-size: 0.7rem;
        line-height: 1.4;
        color: #fbd88a;
    }

    .graph-toolbar {
        background: rgba(8, 13, 26, 0.9);
        border: 1px solid rgba(110, 138, 255, 0.18);
        box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
    }

    .graph-sidebar,
    /* NODE DETAIL VIEW (TEC-NATKIT-124) */
    .node-detail-backdrop {
        position: fixed;
        inset: 0;
        z-index: 200;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 3vh 3vw;
        background: rgba(4, 7, 16, 0.72);
        backdrop-filter: blur(2px);
    }

    .node-detail {
        display: flex;
        flex-direction: column;
        /* "Full-ish": big enough that the inspector stops being a rail, short of
           edge-to-edge so the board stays visible behind it. */
        width: min(1100px, 94vw);
        height: min(880px, 94vh);
        /* ⚠️ max-height as well as height. Without it the flex parent lets the
           panel grow to its CONTENT: a 1,700-line inspector measured 1397px
           tall inside a 950px viewport, and its own scroll area never engaged. */
        max-height: 94vh;
        max-width: 94vw;
        border-radius: 12px;
        border: 1px solid rgba(110, 138, 255, 0.28);
        background: rgba(9, 14, 28, 0.98);
        box-shadow: 0 30px 90px rgba(0, 0, 0, 0.55);
        overflow: hidden;
    }

    .node-detail-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        flex: 0 0 auto;
        padding: 0.7rem 0.9rem;
        border-bottom: 1px solid rgba(110, 138, 255, 0.18);
        background: rgba(14, 20, 38, 0.9);
    }

    .node-detail-title {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        min-width: 0;
    }

    .node-detail-title strong {
        font-size: 0.95rem;
        color: #e8eeff;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .node-detail-kind {
        font-size: 0.66rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #7f92c4;
    }

    .node-detail-actions {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        flex: 0 0 auto;
    }

    .node-detail-body {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        padding: 0;
        /* ⚠️ hidden here, and each pane scrolls itself. One shared scroll made
           both panes 1705px tall inside an 880px panel, so the node scrolled
           away the moment you touched the fields beside it. */
        overflow: hidden;
        /* The node on the left, the fields editing it on the right.
           ⚠️ A GRID, not CSS columns. Columns fill sequentially and an
           .inspector-section cannot break across them, so an earlier cut put
           the node's single tall section entirely in the right column with the
           left one empty — worse than the rail it replaced. */
        display: grid;
        grid-template-columns: 340px minmax(0, 1fr);
        align-items: stretch;
    }

    /* The left pane reads as part of the panel rather than a card dropped onto
       it: its own ground, a full-height divider, and the node sitting at the
       top of a column that carries its runtime beneath. */
    .node-detail-preview {
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        min-height: 0;
        overflow-y: auto;
        padding: 1.2rem;
        background: rgba(6, 10, 22, 0.6);
        border-right: 1px solid rgba(110, 138, 255, 0.14);
    }

    /* The preview card is the pane's content, not a floating object on it:
       flush to the column, no drop shadow competing with the panel's own. */
    .node-detail-preview :global(.node.preview) {
        border-color: rgba(122, 148, 255, 0.3);
    }

    /* ⚠️ Inside the detail view the recommended-next list must NOT scroll. A
       240px scroll area nested inside the panel's own scroll gives two
       scrollbars a few pixels apart, and the inner one swallows the wheel. */
    .node-detail-fields :global(.library-actions) {
        max-height: none;
        overflow: visible;
    }

    .json-section summary {
        cursor: pointer;
        list-style: none;
    }

    .json-section summary::-webkit-details-marker {
        display: none;
    }

    .json-section summary::before {
        content: "▸ ";
        color: #6d7fae;
    }

    .json-section[open] summary::before {
        content: "▾ ";
    }

    .node-detail-preview :global(.runtime-card) {
        margin: 0;
    }

    /* The runtime rows are label-left / value-right at sidebar width. In a
       340px pane a 19-digit stream id wraps under its own label and reads as a
       mistake, so stack them deliberately instead. */
    .node-detail-preview :global(.runtime-card .summary-row) {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.1rem;
    }

    .node-detail-preview :global(.runtime-card .summary-row:first-child) {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
    }

    .node-detail-preview :global(.runtime-card .summary-row strong) {
        font-size: 0.74rem;
        font-weight: 500;
        word-break: break-all;
    }

    .node-detail-diagnostics {
        margin: 0.7rem 0 0;
        padding-left: 1rem;
        font-size: 0.72rem;
        color: #e0a06a;
    }

    .node-detail-fields {
        padding: 1.2rem 1.4rem;
        min-width: 0;
        min-height: 0;
        overflow-y: auto;
    }

    .node-detail-fields :global(.inspector-section) {
        max-width: 680px;
        margin: 0 0 1rem;
    }

    /* Narrow viewports: the preview stacks above the fields rather than
       squeezing both. */
    @media (max-width: 820px) {
        .node-detail-body {
            grid-template-columns: minmax(0, 1fr);
        }

        .node-detail-preview {
            position: static;
            border-right: none;
            border-bottom: 1px solid rgba(110, 138, 255, 0.14);
        }
    }


    .graph-inspector {
        border-radius: 8px;
    }

    .graph-sidebar {
        position: absolute;
        top: var(--panel-top, 72px);
        left: 14px;
        bottom: 14px;
        width: 280px;
        z-index: 15;
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        /* ⚠️ min-width:0 so a long child (a stream label like
           "Stream 13793649553360 - NatImuBulkDataSchema") can shrink instead of
           forcing the panel wider than itself. A flex item's default min-width
           is auto, which refuses to go below its intrinsic content width. */
        min-width: 0;
        /* ⚠️ min-width:0 so a long child (a stream label like
           "Stream 13793649553360 - NatImuBulkDataSchema") can shrink instead of
           forcing the panel wider than itself. A flex item's default min-width
           is auto, which refuses to go below its intrinsic content width. */
        min-width: 0;
        overflow: auto;
        border-radius: 8px;
        transition: transform 0.18s ease, opacity 0.18s ease;
    }

    /* Each section keeps its natural height and the sidebar scrolls as a whole.
       Without this, flexbox shrinks the sections to fit the column height and
       their (overflow-visible) content spills over and overlaps neighbours. */
    .graph-sidebar > * {
        flex-shrink: 0;
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
        /* ⚠️ WRAP RATHER THAN RUN OFF THE EDGE. These rows hold a variable number
           of items — the board picker, the run pill, the rig-health pill, the
           panel toggles — so their width depends on rig state, not on layout. On
           a 1016 px window the row measured 990 px starting at x=28, putting its
           right edge at 1018 and clipping the last control. A toolbar button you
           cannot see is one you cannot press. */
        flex-wrap: wrap;
        row-gap: 0.4rem;
        /* A flex item's default min-width is auto, so without this the row
           refuses to shrink below its content and wrapping never engages. */
        min-width: 0;
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

    .library-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .profile-row {
        display: flex;
        align-items: stretch;
        gap: 0.35rem;
    }

    .run-picker {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        border: 1px solid #26324d;
        border-radius: 8px;
        padding: 0.5rem;
        max-height: 200px;
        overflow: auto;
    }

    .run-picker-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #9dafdf;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .run-picker-scope {
        margin: 0;
        color: #8ea2f5;
        font-size: 0.7rem;
    }
    .run-picker-scope.warn {
        color: #e0b072;
    }

    .run-pick-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    .run-pick-label {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        font-size: 0.78rem;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .run-pick-meta {
        color: #6b7a99;
        font-size: 0.68rem;
    }

    .run-pick-scope-badge {
        display: inline-block;
        margin-left: 6px;
        padding: 0 6px;
        border-radius: 999px;
        background: #21406e;
        color: #9dc3ff;
        font-size: 0.62rem;
        vertical-align: middle;
    }

    .run-pick-btn {
        border: 1px solid #34406080;
        background: transparent;
        color: #9dafdf;
        border-radius: 6px;
        padding: 0.15rem 0.5rem;
        font-size: 0.72rem;
        cursor: pointer;
    }

    .run-pick-btn.active {
        background: #2563eb;
        border-color: #2563eb;
        color: #fff;
    }

    .profile-load {
        flex: 1;
        min-width: 0;
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

    .timeline-dock {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 25;
        box-shadow: 0 -6px 18px rgba(0, 0, 0, 0.3);
    }

    .experiment-library {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 14px;
        background: #0b1219;
        border-top: 1px solid #1e2a36;
        color: #94a3b8;
        font-size: 12px;
        overflow-x: auto;
    }

    .lib-title {
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
        white-space: nowrap;
    }

    .lib-refresh {
        display: inline-flex;
        background: #1e293b;
        color: #cbd5e1;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 3px 6px;
        cursor: pointer;
    }

    .lib-empty {
        color: #64748b;
        font-style: italic;
    }

    .lib-list {
        display: flex;
        gap: 8px;
    }

    .lib-item {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
        background: #16212e;
        border: 1px solid #24313f;
        border-radius: 6px;
        padding: 4px 10px;
        cursor: pointer;
        white-space: nowrap;
    }

    .lib-item:hover {
        background: #1d2a3a;
    }

    .lib-item.selected {
        border-color: #60a5fa;
    }

    .lib-item-name {
        color: #e2e8f0;
        font-weight: 600;
    }

    .lib-item-meta {
        color: #64748b;
        font-size: 11px;
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

    .conn-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        border-radius: 999px;
        padding: 0.22rem 0.7rem;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid rgba(114, 142, 255, 0.22);
        color: #9dafdf;
        background: rgba(8, 13, 26, 0.7);
        white-space: nowrap;
        flex-shrink: 0;
    }

    .conn-pill .conn-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: currentColor;
    }

    .conn-pill.connected {
        color: #8ef2bf;
        border-color: rgba(142, 242, 191, 0.3);
    }

    .conn-pill.connecting {
        color: #ffcf85;
        border-color: rgba(255, 176, 32, 0.3);
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
        /* ⚠️ THE STAGE IS A FULL-CANVAS OVERLAY. It is `position: absolute;
           inset: 0` and comes after the edge <svg> in the DOM, so it covered
           every link and ate the click — which is why edges could never be
           selected, and so never deleted, even though the handler to do it has
           been there all along. The stage itself is empty space between the node
           cards; only the cards should take a click, so it opts out and its
           children opt back in. Clicks that fall through land on .graph-canvas
           below, which is what clicking empty canvas already did. */
        pointer-events: none;
    }

    /* ⚠️ :global() is load-bearing. The stage's children are <StreamGraphNode>
       components, and Svelte's scoped CSS does not cross a component boundary —
       a plain `.graph-stage > *` compiled to a scope class those cards never
       carry, so pointer-events stayed `none` on every node and the whole canvas
       went dead to the mouse. */
    .graph-stage > :global(*) {
        pointer-events: auto;
    }

    .graph-edge {
        fill: none;
        stroke: rgba(104, 215, 255, 0.58);
        stroke-width: 3;
        cursor: pointer;
        transition: stroke 0.15s ease, stroke-width 0.15s ease;
    }

    /* Part C: per-edge topic badge (positioned in graph coords in .graph-stage). */
    .edge-badge-wrap {
        position: absolute;
        transform: translate(-50%, -50%);
        z-index: 6;
    }
    .edge-badge {
        min-width: 20px;
        height: 20px;
        padding: 0 6px;
        border-radius: 999px;
        border: 1px solid rgba(104, 215, 255, 0.55);
        background: #10222b;
        color: #cbeefb;
        font: 600 11px/1 var(--mono, ui-monospace, monospace);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: background 0.12s ease, border-color 0.12s ease;
    }
    /* ⚠️ A badge reading "1" on every edge is six identical circles competing
       with the graph, and it says nothing: one topic is the normal case. It
       fades to a small dot and only becomes a readable badge on hover, on
       focus, or when it actually has something to report (more than one topic,
       or some of them hidden). */
    .edge-badge.quiet {
        opacity: 0.28;
        color: transparent;
        transform: scale(0.55);
    }

    .edge-badge.quiet:hover,
    .edge-badge.quiet:focus-visible {
        opacity: 1;
        color: inherit;
        transform: none;
    }

    .edge-badge:hover {
        background: #16303c;
        border-color: #89f4ff;
    }
    .edge-badge.multi {
        border-color: rgba(180, 145, 255, 0.75);
        color: #e4d7ff;
    }
    .edge-badge.filtered {
        border-color: rgba(255, 205, 120, 0.8);
        color: #f2d69a;
    }
    .edge-badge-hint {
        font-size: 10px;
        color: #7f9098;
        padding: 1px 2px 4px;
        border-bottom: 1px solid rgba(104, 215, 255, 0.14);
        margin-bottom: 2px;
    }
    .edge-badge-row input[type="checkbox"] {
        flex: 0 0 auto;
        margin: 0;
        cursor: pointer;
        accent-color: #68d7ff;
    }
    .edge-badge-row {
        cursor: pointer;
    }
    .edge-badge-row.row-hidden {
        opacity: 0.5;
    }
    .edge-badge-menu {
        position: absolute;
        top: 24px;
        left: 50%;
        transform: translateX(-50%);
        min-width: 210px;
        background: #0e1a20;
        border: 1px solid rgba(104, 215, 255, 0.35);
        border-radius: 8px;
        padding: 6px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        display: flex;
        flex-direction: column;
        gap: 4px;
        z-index: 20;
    }
    .edge-badge-row {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        white-space: nowrap;
    }
    .badge-type {
        flex: 0 0 auto;
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 700;
        font-family: var(--mono, ui-monospace, monospace);
        background: rgba(104, 215, 255, 0.16);
        color: #9fe0f5;
    }
    .badge-type-marker {
        background: rgba(180, 145, 255, 0.18);
        color: #d3c1ff;
    }
    .badge-type-meta {
        background: rgba(255, 205, 120, 0.16);
        color: #f2d69a;
    }
    .badge-schema {
        flex: 1 1 auto;
        color: #b9c6cd;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .badge-id {
        flex: 0 0 auto;
        color: #6f8088;
        font-family: var(--mono, ui-monospace, monospace);
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

    /* Markers travel a different kind of link, and it is worth seeing at a
       glance. The same purple the marker PORTS use, so a line and the dots it
       joins read as one thing rather than two conventions. */
    /* Invisible, wide, and on top: the thing a click actually lands on. */
    .graph-edge-hit {
        fill: none;
        stroke: transparent;
        stroke-width: 18;
        cursor: pointer;
    }
    .graph-edge-hit:focus-visible {
        outline: none;
        stroke: rgba(137, 244, 255, 0.25);
    }
    .edge-delete {
        cursor: pointer;
    }
    .edge-delete circle {
        fill: rgba(18, 24, 38, 0.92);
        stroke: rgba(255, 121, 121, 0.9);
        stroke-width: 1.5;
    }
    .edge-delete path {
        stroke: #ff9d9d;
        stroke-width: 1.8;
        stroke-linecap: round;
        fill: none;
    }
    .edge-delete:hover circle,
    .edge-delete:focus-visible circle {
        fill: rgba(120, 30, 40, 0.95);
    }
    .graph-edge.edge-markers {
        stroke: #b491ff;
    }
    .graph-edge.edge-markers.edge-running {
        stroke: #c9b0ff;
    }

    .graph-edge.edge-invalid {
        stroke: rgba(255, 121, 121, 0.9);
    }

    .graph-edge.edge-running {
        stroke-dasharray: 6 6;
        animation: edge-flow 0.6s linear infinite;
    }

    /* Provenance edges: lineage/control wiring (source→experiment, experiment→
       train, train→classify), not a streaming data path. Rendered dashed + blue
       so they read as distinct from solid data edges; excluded from execution. */
    .graph-edge.edge-provenance {
        stroke: rgba(91, 123, 219, 0.85);
        stroke-width: 2.5;
        stroke-dasharray: 7 5;
    }
    .graph-edge.edge-provenance.selected {
        stroke: #8ea2f5;
        stroke-width: 3.5;
        filter: drop-shadow(0 0 4px rgba(91, 123, 219, 0.6));
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

    /* IMU calibration readout on a viewer node. */
    .calib-panel {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        padding: 0.15rem 0.1rem;
        font-size: 0.7rem;
    }

    .calib-headline {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        color: #e4ecff;
    }

    .calib-position {
        margin-left: auto;
        font-size: 0.64rem;
        color: #7f91c8;
    }

    .calib-parts {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
    }

    .calib-part {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.64rem;
        color: #b9c8f0;
    }

    .calib-part-label {
        flex: 1 1 auto;
    }

    .calib-part-value {
        color: #7f91c8;
    }

    .calib-commands {
        display: flex;
        gap: 0.3rem;
        margin-top: 0.35rem;
    }

    .calib-command-btn {
        flex: 1 1 0;
        padding: 0.2rem 0.3rem;
        font-size: 0.62rem;
        color: #cfdaf7;
        background: #2b3457;
        border: 1px solid #3d4a75;
        border-radius: 4px;
        cursor: pointer;
    }

    .calib-command-btn:hover:not(:disabled) {
        background: #35406a;
    }

    .calib-command-btn:disabled {
        opacity: 0.6;
        cursor: progress;
    }

    .calib-command-result {
        margin: 0.3rem 0 0;
        font-size: 0.6rem;
        line-height: 1.3;
        color: #8fa8dd;
        word-break: break-word;
    }

    .calib-command-result.failed {
        color: #e2a0a0;
    }

    .calib-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex: 0 0 auto;
        background: #3a4568;
    }

    .calib-dot.faded {
        background: #2b3552;
    }

    .calib-dot.gray {
        background: #6b7280;
    }

    .calib-dot.red {
        background: #ef4444;
    }

    .calib-dot.yellow {
        background: #eab308;
    }

    .calib-dot.green {
        background: #22c55e;
    }

    /* Compact time readout, bottom-centre of the canvas. */
    .time-readout {
        position: absolute;
        bottom: 0.75rem;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.3rem 0.7rem;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: rgba(10, 15, 30, 0.86);
        backdrop-filter: blur(6px);
        font-size: 0.72rem;
        color: #b9c8f0;
        white-space: nowrap;
        /* Never intercept canvas interaction (pan, right-click, node drags). */
        pointer-events: none;
        z-index: 5;
    }

    .time-readout-badge {
        font-size: 0.6rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 0.1rem 0.4rem;
        border-radius: 999px;
        background: #1b2440;
        color: #7f91c8;
    }

    .time-readout.live .time-readout-badge {
        background: #10331f;
        color: #58d68d;
    }

    .time-readout.replay .time-readout-badge {
        background: #1a2748;
        color: #7aa2ff;
    }

    .time-readout.recorded .time-readout-badge {
        background: #2c2340;
        color: #c39bf0;
    }

    .time-readout-clock {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        font-variant-numeric: tabular-nums;
    }

    .time-readout-elapsed {
        font-variant-numeric: tabular-nums;
        font-weight: 600;
        color: #e4ecff;
    }

    .time-readout-total,
    .time-readout-detail {
        color: #7f91c8;
        font-weight: 400;
        margin-left: 0.25rem;
    }

    .time-readout-track {
        width: 88px;
        height: 3px;
        border-radius: 999px;
        background: #1b2440;
        overflow: hidden;
    }

    .time-readout-fill {
        display: block;
        height: 100%;
        background: #4f7ef7;
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
        top: var(--panel-top, 72px);
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

    /* The experiment panel floats over the canvas beside the inspector: it is a
       board-level surface, not a node inspector, so it gets its own column. */
    .graph-experiment-panel {
        position: absolute;
        top: var(--panel-top, 72px);
        right: 390px;
        bottom: 14px;
        width: 320px;
        z-index: 16;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        border-radius: 8px;
        border: 1px solid rgba(114, 142, 255, 0.16);
        background: rgba(9, 14, 26, 0.94);
        backdrop-filter: blur(6px);
    }

    /* --- Experiment history tree (Phase 4) --- */
    .tree-experiment {
        display: flex;
        flex-direction: column;
        gap: 1px;
    }

    .tree-experiment-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        width: 100%;
        border: 1px solid transparent;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.03);
        color: #cfe0ff;
        padding: 0.3rem 0.45rem;
        font-size: 0.78rem;
        cursor: pointer;
        text-align: left;
    }

    .tree-experiment-row.bound {
        border-color: rgba(120, 205, 255, 0.32);
        background: rgba(58, 150, 221, 0.16);
    }

    .tree-experiment-label {
        flex: 1;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .tree-count {
        font-size: 0.7rem;
        color: #7f91c8;
    }

    .tree-instance {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.4rem;
        width: 100%;
        border: 1px solid transparent;
        border-radius: 5px;
        background: transparent;
        color: #9dafdf;
        padding: 0.22rem 0.4rem;
        font-size: 0.74rem;
        cursor: pointer;
        text-align: left;
    }

    .tree-instance:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .tree-instance.selected {
        border-color: rgba(160, 130, 255, 0.4);
        background: rgba(160, 130, 255, 0.14);
        color: #e6ecf5;
    }

    .tree-instance-id {
        font-family: ui-monospace, SFMono-Regular, monospace;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .tree-instance-status {
        font-size: 0.68rem;
        white-space: nowrap;
    }

    .tree-instance-status.complete {
        color: #9ce6b4;
    }

    .tree-instance-status.failed {
        color: #ffb4b4;
    }

    .tree-instance-status.recording,
    .tree-instance-status.materializing {
        color: #ffcf85;
    }

    /* --- Instance review (Phase 4) --- */
    .instance-badge {
        border-radius: 999px;
        padding: 0.18rem 0.5rem;
        font-size: 0.68rem;
        letter-spacing: 0.06em;
    }

    .instance-badge.sealed {
        background: rgba(160, 130, 255, 0.18);
        color: #cbbcff;
    }

    .instance-badge.editable {
        background: rgba(120, 205, 255, 0.16);
        color: #bfe6ff;
    }

    .instance-status.complete {
        color: #9ce6b4;
    }

    .instance-status.failed {
        color: #ffb4b4;
    }

    .artifact-card {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.09);
        background: rgba(9, 14, 26, 0.6);
        padding: 0.5rem 0.6rem;
    }

    .artifact-hash {
        font-family: ui-monospace, SFMono-Regular, monospace;
        font-size: 0.72rem;
        color: #7f91c8;
    }

    .artifact-download {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        font-size: 0.74rem;
        color: #9ad4ff;
        text-decoration: none;
    }

    .artifact-download:hover {
        text-decoration: underline;
    }

    .instance-picker {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .instance-pick-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: rgba(9, 14, 26, 0.55);
        padding: 0.3rem 0.4rem;
    }

    .instance-pick-label {
        flex: 1;
        display: flex;
        flex-direction: column;
        font-size: 0.74rem;
        overflow: hidden;
    }

    .instance-pick-label strong {
        font-family: ui-monospace, SFMono-Regular, monospace;
        color: #e6ecf5;
    }

    .instance-pick-meta {
        font-size: 0.68rem;
        color: #7f91c8;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .replay-bar {
        display: block;
        height: 6px;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.08);
        overflow: hidden;
    }

    .replay-bar-fill {
        display: block;
        height: 100%;
        border-radius: 3px;
        background: rgba(156, 230, 180, 0.7);
        transition: width 0.2s linear;
    }

    .field-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.4rem;
    }

    .label-histogram {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
    }

    .label-row {
        display: grid;
        grid-template-columns: minmax(60px, 30%) 1fr auto;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.7rem;
        color: #9dafdf;
    }

    .label-name {
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .label-bar {
        display: block;
        height: 6px;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.07);
        overflow: hidden;
    }

    .label-bar-fill {
        display: block;
        height: 100%;
        border-radius: 3px;
        background: rgba(120, 205, 255, 0.65);
    }

    .label-bar-fill.unlabelled {
        background: rgba(255, 255, 255, 0.22);
    }

    .label-count {
        font-family: ui-monospace, SFMono-Regular, monospace;
        color: #cfe0ff;
    }

    .experiment-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        border-radius: 999px;
        border: 1px solid rgba(114, 142, 255, 0.2);
        background: rgba(255, 255, 255, 0.04);
        color: #9dafdf;
        padding: 0.24rem 0.6rem;
        font-size: 0.78rem;
        cursor: pointer;
        max-width: 220px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    .experiment-pill.bound {
        border-color: rgba(120, 205, 255, 0.35);
        background: rgba(58, 150, 221, 0.18);
        color: #dceeff;
    }

    .immutable-pill {
        border-radius: 999px;
        padding: 0.24rem 0.6rem;
        font-size: 0.76rem;
        background: rgba(160, 130, 255, 0.16);
        color: #cbbcff;
    }

    .recording-pill {
        border-radius: 999px;
        padding: 0.24rem 0.6rem;
        font-size: 0.76rem;
        background: rgba(255, 74, 74, 0.18);
        color: #ffb4b4;
    }


    /* --- device controls (TEC-NATKIT-99 / -40) ----------------------------- */
    .control-group {
        margin-top: 0.6rem;
        padding-top: 0.5rem;
        border-top: 1px solid rgba(148, 163, 184, 0.25);
    }
    .control-group-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }
    .control-group-title {
        font-weight: 600;
        font-size: 0.85rem;
    }
    .control-toggles {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        margin: 0.4rem 0;
    }
    .control-toggle {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.85rem;
        cursor: pointer;
    }
    /* A report that is switched OFF is dimmed rather than hidden: the point of
       the control is seeing what this board is not collecting. */
    .control-toggle.off {
        opacity: 0.55;
    }
    .control-toggle input:disabled {
        cursor: not-allowed;
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

    .diagnostic.warn {
        color: #e0a06a;
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

    /* ⚠️ STATUS IS NOT A BUTTON. `Unfiled`, `Unsaved`, `Connected`, `Rig …`,
       `No experiment` and the board id all rendered as the same rounded chip,
       so nothing distinguished the three you can press from the four that are
       only reporting. Status now reads as flat text on the bar — no border, no
       fill, no hover — and the pressable ones keep the chip. */
    .graph-id,
    .dirty-pill,
    .immutable-pill,
    .workspace-hidden,
    .conn-pill,
    .rig-pill {
        border: none !important;
        background: none !important;
        box-shadow: none !important;
        cursor: default;
    }

    .graph-id,
    .workspace-hidden {
        color: #93a5cf;
    }

    .context-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
        padding: 0.1rem 0.15rem 0.4rem;
        border-bottom: 1px solid rgba(110, 138, 255, 0.16);
        margin-bottom: 0.4rem;
    }

    .context-heading {
        font-size: 0.78rem;
        font-weight: 600;
        color: #e2e9ff;
    }

    .context-close {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.15rem;
        border: none;
        background: none;
        color: #8fa4d8;
        cursor: pointer;
        border-radius: 4px;
    }

    .context-close:hover {
        color: #e5ecff;
        background: rgba(110, 138, 255, 0.14);
    }

    .context-search {
        width: 100%;
        box-sizing: border-box;
        margin-bottom: 0.45rem;
        padding: 0.32rem 0.5rem;
        border-radius: 5px;
        border: 1px solid rgba(110, 138, 255, 0.24);
        background: rgba(6, 10, 22, 0.85);
        color: #e2e9ff;
        font-size: 0.74rem;
    }

    .context-search:focus {
        outline: none;
        border-color: rgba(110, 138, 255, 0.55);
    }

    /* ⚠️ CONTRAST. Secondary text sat at #6d7fae on a near-navy ground, which
       is roughly 3:1 — under the 4.5:1 that small text needs, and the critique
       called it out as "low-contrast blue-on-navy". Lifted a step across the
       secondary scale rather than per-component, so it cannot drift back.  */
    .graph-list-meta,
    .muted-text,
    .context-item small {
        color: #93a5cf;
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

    /* Full-screen focus mode: run the experiment edge-to-edge with nothing else
       on screen (participant/operator focus during a recording session). */
    .experiment-modal-overlay {
        padding: 0;
        background: rgba(3, 6, 14, 0.94);
    }

    .experiment-modal-panel {
        width: 100vw;
        height: 100vh;
        max-height: 100vh;
        border: none;
        border-radius: 0;
        padding: 1.5rem clamp(1.5rem, 6vw, 6rem);
        gap: 1.25rem;
    }

    .experiment-modal-body {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 0;
        /* ⚠️ THE CLIPPING BUG (TEC-NATKIT-68). `.viewer-data-body` caps itself at
         * `max-height: 60vh`, which is right for a data inspector in a windowed
         * modal and wrong for this one: the panel is deliberately 100vh
         * "full-screen focus mode", yet its content area was still capped at 60% of
         * the window and centred, so a runner taller than that spilled off BOTH ends
         * — the stimulus image starting above the viewport and the countdown cut off
         * the bottom.
         *
         * Measured at 1280x720: body 432px (= 60vh) of a 608px budget, so 176px of
         * usable height was simply unavailable. Two earlier attempts at this bug
         * tried to shrink the image to fit 432px, which was treating the symptom. */
    }

    /* ⚠️ COMPOUND selector on purpose. `.experiment-modal-body` alone has the same
     * specificity as `.viewer-data-body`, which is declared LATER in this file and
     * therefore won on source order — a plain `max-height: none` here was silently
     * ignored, and the measurement still read 432px. */
    .viewer-data-body.experiment-modal-body {
        max-height: none;
        overflow: visible;
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
        /* Below the toolbar, whose height varies with wrapping (see --panel-top).
           At a fixed offset it rendered on top of the board title and pills. */
        top: calc(var(--panel-top, 72px) - 58px);
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
