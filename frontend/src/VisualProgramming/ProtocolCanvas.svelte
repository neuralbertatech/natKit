<script lang="ts">
    // The spatial view of a protocol (experiment-authoring-ux-rework, Phase 4).
    //
    // The step list is precise but flat: a shuffled x3 group of ten steps reads
    // as an indented run of rows, and the shape of a session is something you
    // reconstruct in your head. This renders the same protocol as a sequence of
    // nodes you can see at once, with repeat groups as black boxes you zoom
    // into.
    //
    // A protocol is CONTROL FLOW, not dataflow. So unlike the graph editor there
    // is no free-form wiring: order is the only relationship, the layout is
    // computed, and the connectors are drawn rather than drawn-by-the-user.
    // Nothing invalid can be expressed, and there is no second graph model to
    // validate.
    //
    // The list stays canonical (it is the accessible, keyboard-complete
    // surface); this is a view toggle over the same StepProtocol, and editing
    // happens through the same StepFields component the list rows use.
    import {
        ChevronRight,
        CornerDownRight,
        Dices,
        Home,
        Layers,
        Plus,
        Repeat,
        Trash2,
    } from "@lucide/svelte";
    import StepFields from "./StepFields.svelte";
    import type {
        ExperimentStep,
        ExperimentStepKind,
        InterleavedRest,
        RepeatStep,
        StepProtocol,
    } from "../StreamViewer/experimentSteps";

    interface Props {
        protocol: StepProtocol;
        readOnly: boolean;
        /** Which media slot is mid-upload, keyed by step id. */
        uploading: Record<string, "image" | "audio" | null>;
        stepKindLabels: Record<ExperimentStepKind, string>;
        kindColors: Record<ExperimentStepKind, string>;
        retypeStep: (step: ExperimentStep, kind: ExperimentStepKind) => ExperimentStep;
        rollSeed: () => number;
        mediaLabel: (step: ExperimentStep, slot: "image" | "audio") => string;
        groupSummary: (step: RepeatStep) => string;
        // Tree edits, addressed the same way the list addresses them.
        onPatchStep: (parentId: string | null, stepId: string, patch: Record<string, unknown>) => void;
        onReplaceStep: (parentId: string | null, stepId: string, next: ExperimentStep) => void;
        onPatchInterleave: (parentId: string | null, step: RepeatStep, patch: Partial<InterleavedRest>) => void;
        onToggleInterleave: (parentId: string | null, step: RepeatStep, enabled: boolean) => void;
        onUploadMedia: (parentId: string | null, step: ExperimentStep, slot: "image" | "audio", file: File) => void;
        onClearMedia: (parentId: string | null, step: ExperimentStep, slot: "image" | "audio") => void;
        onAddStep: (parentId: string | null, kind: ExperimentStepKind) => void;
        onRemoveStep: (parentId: string | null, stepId: string) => void;
        onMoveStep: (parentId: string | null, stepId: string, delta: number) => void;
    }

    let {
        protocol,
        readOnly,
        uploading,
        stepKindLabels,
        kindColors,
        retypeStep,
        rollSeed,
        mediaLabel,
        groupSummary,
        onPatchStep,
        onReplaceStep,
        onPatchInterleave,
        onToggleInterleave,
        onUploadMedia,
        onClearMedia,
        onAddStep,
        onRemoveStep,
        onMoveStep,
    }: Props = $props();

    // --- Zoom level ---------------------------------------------------------
    // `zoomedInto` is the repeat group whose interior fills the canvas, or null
    // for the top level. Only one level deep is reachable because the step tree
    // is only one container deep — but the breadcrumb is written generally so
    // nesting would not need a rewrite.
    let zoomedInto = $state<string | null>(null);
    let selectedId = $state<string | null>(null);

    const zoomedGroup = $derived.by(() => {
        if (!zoomedInto) return null;
        const found = protocol.steps.find(
            (step) => step.kind === "repeat" && step.id === zoomedInto,
        );
        return (found as RepeatStep | undefined) ?? null;
    });

    // A group deleted while zoomed into it would strand the canvas.
    $effect(() => {
        if (zoomedInto && !zoomedGroup) {
            zoomedInto = null;
        }
    });

    /** The steps currently on the canvas, and the parent they belong to. */
    const view = $derived.by(() => {
        if (zoomedGroup) {
            return { parentId: zoomedGroup.id, steps: zoomedGroup.steps };
        }
        return { parentId: null as string | null, steps: protocol.steps };
    });

    const selected = $derived.by(() => {
        if (!selectedId) return null;
        return view.steps.find((step) => step.id === selectedId) ?? null;
    });

    // Clear a selection that is no longer on screen (zoom change, deletion).
    $effect(() => {
        if (selectedId && !view.steps.some((s) => s.id === selectedId)) {
            selectedId = null;
        }
    });

    /** What a node shows under its title. */
    function nodeSubtitle(step: ExperimentStep): string {
        if (step.kind === "repeat") {
            const parts = [`x${step.times ?? 1}`];
            if (step.shuffle) parts.push(`shuffled (seed ${step.seed ?? 1})`);
            if (step.interleave_rest) parts.push("rests between");
            return parts.join(" · ");
        }
        if (step.kind === "wait") return "holds for input";
        if (step.kind === "instruction" && step.wait_for_input) {
            return "holds for input";
        }
        const duration = (step as { duration_s?: number }).duration_s ?? 0;
        const jitter = (step as { jitter_s?: number }).jitter_s ?? 0;
        return jitter > 0 ? `${duration}s ±${jitter}` : `${duration}s`;
    }

    function nodeTitle(step: ExperimentStep): string {
        if (step.kind === "repeat") return "Repeat group";
        if (step.kind === "cue") {
            return (step as { label?: string }).label || "(no class)";
        }
        return step.text || stepKindLabels[step.kind];
    }

    function isTutorial(step: ExperimentStep): boolean {
        return step.tutorial === true || (zoomedGroup?.tutorial === true);
    }

    function openGroup(step: ExperimentStep) {
        if (step.kind !== "repeat") return;
        zoomedInto = step.id;
        selectedId = null;
    }

    const ADDABLE: ExperimentStepKind[] = ["instruction", "cue", "rest"];
</script>

<div class="protocol-canvas">
    <div class="canvas-head">
        <nav class="breadcrumb" aria-label="Protocol location">
            <button
                type="button"
                class="crumb"
                class:current={!zoomedGroup}
                onclick={() => {
                    zoomedInto = null;
                    selectedId = null;
                }}
            >
                <Home size={12} />
                {protocol.label || "Protocol"}
            </button>
            {#if zoomedGroup}
                <ChevronRight size={12} class="crumb-sep" />
                <span class="crumb current">
                    <Repeat size={12} />
                    Repeat group ×{zoomedGroup.times ?? 1}
                </span>
            {/if}
        </nav>
        <span class="canvas-hint">
            {#if zoomedGroup}
                Inside a repeat group — these steps run {zoomedGroup.times ?? 1}
                times{zoomedGroup.shuffle ? ", shuffled each pass" : ""}.
            {:else}
                Steps run left to right. Double-click a repeat group to look
                inside it.
            {/if}
        </span>
    </div>

    <div class="canvas-body">
        <div class="lane" role="list">
            {#each view.steps as step, index (step.id)}
                {#if index > 0}
                    <span class="connector" aria-hidden="true"></span>
                {/if}
                <div
                    class="node"
                    class:selected={selectedId === step.id}
                    class:tutorial={isTutorial(step)}
                    class:is-group={step.kind === "repeat"}
                    style={`--kind:${kindColors[step.kind]}`}
                    role="listitem"
                >
                    <button
                        type="button"
                        class="node-hit"
                        title={step.kind === "repeat"
                            ? "Click to select · double-click to look inside"
                            : "Click to select"}
                        onclick={() =>
                            (selectedId = selectedId === step.id ? null : step.id)}
                        ondblclick={() => openGroup(step)}
                    >
                        <span class="node-kind">{stepKindLabels[step.kind]}</span>
                        <span class="node-title">{nodeTitle(step)}</span>
                        <span class="node-sub">{nodeSubtitle(step)}</span>
                        {#if step.kind !== "repeat" && step.image_url}
                            <img
                                class="node-thumb"
                                src={step.image_url}
                                alt=""
                            />
                        {/if}
                        {#if isTutorial(step)}
                            <span class="node-tag">practice</span>
                        {/if}
                    </button>

                    {#if step.kind === "repeat"}
                        <!-- The black box: what is inside, without opening it. -->
                        <div class="container-foot">
                            <span>{groupSummary(step)}</span>
                            <button
                                type="button"
                                class="open-btn"
                                onclick={() => openGroup(step)}
                            >
                                <Layers size={11} />
                                Open
                            </button>
                        </div>
                    {/if}
                </div>
            {/each}

            {#if view.steps.length === 0}
                <p class="empty">
                    Nothing here yet — add a step below.
                </p>
            {/if}
        </div>

        <div class="lane-add">
            {#each ADDABLE as kind}
                <button
                    type="button"
                    class="add-btn"
                    disabled={readOnly}
                    onclick={() => onAddStep(view.parentId, kind)}
                >
                    <Plus size={11} />
                    <span
                        class="kind-dot"
                        style={`background:${kindColors[kind]}`}
                    ></span>
                    {stepKindLabels[kind]}
                </button>
            {/each}
            {#if !zoomedGroup}
                <button
                    type="button"
                    class="add-btn"
                    disabled={readOnly}
                    onclick={() => onAddStep(null, "repeat")}
                >
                    <Plus size={11} />
                    <span
                        class="kind-dot"
                        style={`background:${kindColors.repeat}`}
                    ></span>
                    Repeat group
                </button>
            {/if}
        </div>
    </div>

    <!-- Detail on demand: the selected step's fields, rather than every field
         on every node. Same component the list rows render. -->
    {#if selected}
        {@const step = selected}
        <div class="inspector">
            <div class="inspector-head">
                <span
                    class="inspector-kind"
                    style={`--kind:${kindColors[step.kind]}`}
                >
                    {stepKindLabels[step.kind]}
                </span>
                <div class="inspector-actions">
                    <button
                        type="button"
                        class="icon-btn"
                        disabled={readOnly}
                        title="Move earlier"
                        onclick={() => onMoveStep(view.parentId, step.id, -1)}
                    >
                        <CornerDownRight size={12} style="transform:rotate(180deg)" />
                    </button>
                    <button
                        type="button"
                        class="icon-btn"
                        disabled={readOnly}
                        title="Move later"
                        onclick={() => onMoveStep(view.parentId, step.id, 1)}
                    >
                        <CornerDownRight size={12} />
                    </button>
                    <button
                        type="button"
                        class="icon-btn"
                        disabled={readOnly}
                        title="Remove this step"
                        onclick={() => {
                            onRemoveStep(view.parentId, step.id);
                            selectedId = null;
                        }}
                    >
                        <Trash2 size={12} />
                    </button>
                </div>
            </div>
            <div class="inspector-fields">
                <StepFields
                    {step}
                    {readOnly}
                    restClass={protocol.rest_class || "rest"}
                    uploadingSlot={uploading[step.id] ?? null}
                    groupSummaryText={step.kind === "repeat"
                        ? groupSummary(step)
                        : ""}
                    {retypeStep}
                    {rollSeed}
                    stepKindLabels={stepKindLabels}
                    {mediaLabel}
                    onPatch={(patch) =>
                        onPatchStep(view.parentId, step.id, patch)}
                    onReplace={(next) =>
                        onReplaceStep(view.parentId, step.id, next)}
                    onPatchInterleave={(patch) =>
                        step.kind === "repeat" &&
                        onPatchInterleave(view.parentId, step, patch)}
                    onToggleInterleave={(enabled) =>
                        step.kind === "repeat" &&
                        onToggleInterleave(view.parentId, step, enabled)}
                    onUploadMedia={(slot, file) =>
                        onUploadMedia(view.parentId, step, slot, file)}
                    onClearMedia={(slot) =>
                        onClearMedia(view.parentId, step, slot)}
                />
            </div>
        </div>
    {/if}
</div>

<style>
    .protocol-canvas {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .canvas-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .breadcrumb {
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }

    .crumb {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        border: none;
        background: none;
        color: #7f91c8;
        font-size: 0.72rem;
        padding: 0.1rem 0.2rem;
        border-radius: 4px;
        cursor: pointer;
    }

    .crumb.current {
        color: #e6ecf5;
        font-weight: 600;
        cursor: default;
    }

    .crumb:not(.current):hover {
        color: #b9c8f0;
        background: rgba(255, 255, 255, 0.05);
    }

    .canvas-hint {
        font-size: 0.68rem;
        color: #7f91c8;
    }

    .canvas-body {
        border: 1px solid #24304f;
        border-radius: 8px;
        background:
            radial-gradient(
                circle at 1px 1px,
                rgba(120, 140, 200, 0.14) 1px,
                transparent 0
            )
            0 0 / 18px 18px;
        padding: 0.7rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        min-height: 8rem;
    }

    /* Wrapping flow rather than one long row: a 30-step protocol is graspable
       reading left-to-right then down, and unreadable as a 30-wide line. */
    .lane {
        display: flex;
        flex-wrap: wrap;
        /* Pack from the top-left. Without these the wrapped lines distribute
           across the container and the sequence stops reading as a sequence. */
        justify-content: flex-start;
        align-content: flex-start;
        align-items: stretch;
        gap: 0.35rem;
    }

    .connector {
        align-self: center;
        width: 0.6rem;
        height: 2px;
        background: linear-gradient(
            to right,
            rgba(140, 160, 220, 0.15),
            rgba(140, 160, 220, 0.5)
        );
        flex: none;
    }

    .node {
        display: flex;
        flex: 0 0 auto;
        flex-direction: column;
        border: 1px solid #24304f;
        border-top: 3px solid var(--kind);
        border-radius: 7px;
        background: #101830;
        min-width: 8.5rem;
        max-width: 13rem;
        overflow: hidden;
    }

    .node.selected {
        border-color: #4f7ef7;
        box-shadow: 0 0 0 1px #4f7ef7;
    }

    .node.tutorial {
        background: #17142b;
        border-left-color: #4a3d6b;
    }

    /* NOT ".container": a dependency ships a global `.container { margin: auto }`
       which centred this node and blew a 300px gap either side of it. Svelte
       scopes our rules, but a global rule still matches our element by class
       name, so generic class names are unsafe here. */
    .node.is-group {
        min-width: 11rem;
        background: #131a33;
    }

    .node-hit {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
        align-items: flex-start;
        text-align: left;
        border: none;
        background: none;
        color: inherit;
        padding: 0.4rem 0.5rem;
        cursor: pointer;
        width: 100%;
    }

    .node-kind {
        font-size: 0.56rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--kind);
    }

    .node-title {
        font-size: 0.78rem;
        color: #e6ecf5;
        font-weight: 600;
        overflow-wrap: anywhere;
    }

    .node-sub {
        font-size: 0.64rem;
        color: #7f91c8;
        font-variant-numeric: tabular-nums;
    }

    .node-thumb {
        margin-top: 0.2rem;
        width: 100%;
        height: 2.6rem;
        object-fit: contain;
        border-radius: 4px;
        background: #0a0f1e;
    }

    .node-tag {
        margin-top: 0.18rem;
        border-radius: 999px;
        background: rgba(167, 139, 250, 0.18);
        color: #cbbcff;
        font-size: 0.55rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 0.02rem 0.32rem;
    }

    .container-foot {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.35rem;
        border-top: 1px dashed #2b3860;
        padding: 0.25rem 0.4rem;
        font-size: 0.62rem;
        color: #9fb0d8;
    }

    .open-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.2rem;
        border: 1px solid #33436e;
        border-radius: 999px;
        background: #16203c;
        color: #b9c8f0;
        font-size: 0.6rem;
        padding: 0.08rem 0.35rem;
        cursor: pointer;
    }

    .open-btn:hover {
        border-color: #4f7ef7;
        color: #e4ecff;
    }

    .empty {
        margin: 0;
        font-size: 0.72rem;
        color: #7f91c8;
    }

    .lane-add {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
    }

    .add-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.2rem;
        font-size: 0.64rem;
        padding: 0.18rem 0.4rem;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #16203c;
        color: #b9c8f0;
        cursor: pointer;
    }

    .add-btn:hover:not(:disabled) {
        border-color: #4f7ef7;
        color: #e4ecff;
    }

    .add-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .kind-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        flex: none;
    }

    .inspector {
        border: 1px solid #24304f;
        border-radius: 8px;
        background: rgba(12, 18, 28, 0.6);
        padding: 0.5rem 0.6rem;
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }

    .inspector-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }

    .inspector-kind {
        font-size: 0.6rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--kind);
        font-weight: 700;
    }

    .inspector-actions {
        display: flex;
        gap: 0.15rem;
    }

    /* The shared fields lay out as a wrapping row, same as in a list card. */
    .inspector-fields :global(.card-flags) {
        margin-left: 0;
    }

    .inspector-fields {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 0.35rem 0.45rem;
    }

    .icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.05);
        color: #e6ecf5;
        padding: 0.24rem;
        cursor: pointer;
    }

    .icon-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
</style>
