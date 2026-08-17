<script lang="ts">
    // The Experiment Designer (experiment-authoring-ux-rework, Phase 2).
    //
    // Protocol authoring used to live in the 320px experiment side panel, which
    // is an operator surface — good for Record/Stop and history, hopeless for
    // editing a 30-step protocol. This overlay is the authoring surface: the
    // step editor with room to breathe, a compiled-timeline strip that reacts to
    // every edit, and the built-in templates. The panel keeps a status card and
    // opens this via "Edit protocol".
    //
    // Everything here reads and writes the same StepProtocol the panel, runner
    // and recorder use — this is a bigger window onto the same object, not a
    // second model.
    import {
        ChevronDown,
        ChevronRight,
        ChevronUp,
        Copy,
        Dices,
        GripVertical,
        Sparkles,
        List,
        Network,
        Image as ImageIcon,
        Volume2,
        Plus,
        Trash2,
        X,
    } from "@lucide/svelte";
    import type { Experiment, SessionProtocol } from "../StreamViewer/types";
    import { adlStepProtocol, ADL_PROTOCOL_ID } from "../AdlExperiment/tasks";
    import QuickSetupCard from "./QuickSetupCard.svelte";
    import StepFields from "./StepFields.svelte";
    import ProtocolCanvas from "./ProtocolCanvas.svelte";
    import { askConfirm } from "./dialogs.svelte";
    import {
        compileQuickSetupSteps,
        defaultQuickSetupRecipe,
        isQuickSetupRecipe,
        type QuickSetupRecipe,
        type QuickSetupTemplate,
    } from "../StreamViewer/quickSetup";
    import {
        compileStepProtocol,
        isStepProtocol,
        newStepId,
        protocolClasses,
        scheduleForProtocol,
        stepProtocolDurationMs,
        stepsFromLegacyProtocol,
        type ExperimentStep,
        type ExperimentStepKind,
        type InterleavedRest,
        type RepeatStep,
        type StepProtocol,
    } from "../StreamViewer/experimentSteps";

    interface Props {
        // The experiment being authored; the designer only renders when bound.
        bound: Experiment;
        readOnly: boolean;
        onPatch: (patch: Partial<Experiment>) => void;
        onPatchProtocol: (patch: Partial<SessionProtocol>) => void;
        onClose: () => void;
        /** Which step view to open on; the portal on a markers node uses canvas. */
        initialView?: "list" | "canvas";
    }

    let {
        bound,
        readOnly,
        onPatch,
        onPatchProtocol,
        onClose,
        initialView = "list",
    }: Props = $props();

    const stepProtocol = $derived(
        bound && isStepProtocol(bound.protocol)
            ? (bound.protocol as StepProtocol)
            : null,
    );

    // --- Compiled timeline -------------------------------------------------
    // Both protocol shapes compile to the same schedule, so the strip and the
    // header chips work before and after "Convert to editable steps".
    const CLASS_PALETTE = [
        "#34d399",
        "#60a5fa",
        "#f472b6",
        "#fbbf24",
        "#a78bfa",
        "#2dd4bf",
        "#fb923c",
        "#e879f9",
    ];

    const timeline = $derived.by(() => {
        if (!bound.protocol) return null;
        const schedule = scheduleForProtocol(bound.protocol);
        if (schedule.length === 0) return null;
        const totalMs = Math.max(1, stepProtocolDurationMs(schedule));
        const classes: string[] = [];
        for (const cue of schedule) {
            if (cue.phase === "hold" && !classes.includes(cue.gesture)) {
                classes.push(cue.gesture);
            }
        }
        const colorFor = (gesture: string) =>
            CLASS_PALETTE[
                Math.max(0, classes.indexOf(gesture)) % CLASS_PALETTE.length
            ];
        const segments = schedule.map((cue) => {
            const durationMs = cue.end_offset_ms - cue.start_offset_ms;
            const color =
                cue.phase === "hold"
                    ? colorFor(cue.gesture)
                    : cue.phase === "instruction" || cue.phase === "lead_in"
                      ? "rgba(96, 165, 250, 0.35)"
                      : cue.wait_for_input
                        ? "#fbbf24"
                        : "rgba(100, 116, 139, 0.35)";
            return {
                leftPct: (cue.start_offset_ms / totalMs) * 100,
                widthPct: (durationMs / totalMs) * 100,
                wait: cue.wait_for_input === true,
                tutorial: cue.tutorial === true,
                hold: cue.phase === "hold",
                color,
                label: cue.phase === "hold" ? cue.gesture : "",
                title: `${cue.prompt} · ${cue.phase}${
                    cue.wait_for_input
                        ? " · holds for input"
                        : ` · ${(durationMs / 1000).toFixed(1)}s`
                }${cue.tutorial ? " · tutorial" : ""}`,
            };
        });
        return {
            totalMs,
            classes,
            colorFor,
            segments,
            holdCues: schedule.filter((c) => c.phase === "hold").length,
            waits: schedule.filter((c) => c.wait_for_input).length,
            // Cues only, to match holdCues — counting tutorial rests here made
            // a 3-class practice pass report "6 practice".
            tutorialCues: schedule.filter(
                (c) => c.tutorial && c.phase === "hold",
            ).length,
        };
    });

    function formatSeconds(ms: number): string {
        const totalS = Math.round(ms / 1000);
        if (totalS < 60) return `${totalS}s`;
        return `${Math.floor(totalS / 60)}m ${totalS % 60}s`;
    }

    // --- Quick setup --------------------------------------------------------
    // A recipe that generated these steps, if one did. While it is attached the
    // card replaces the step list; editing steps by hand detaches it.
    const quickSetup = $derived(
        stepProtocol && isQuickSetupRecipe(stepProtocol.quick_setup)
            ? stepProtocol.quick_setup
            : null,
    );

    /** Estimated length of what the recipe currently generates. */
    const quickSetupEstimateS = $derived.by(() => {
        if (!quickSetup || !stepProtocol) return 0;
        const schedule = compileStepProtocol({
            ...stepProtocol,
            steps: compileQuickSetupSteps(quickSetup),
        });
        return Math.round(stepProtocolDurationMs(schedule) / 1000);
    });

    /** Write a recipe and the steps it generates together, in one patch. */
    function applyRecipe(recipe: QuickSetupRecipe) {
        onPatchProtocol({
            steps: compileQuickSetupSteps(recipe),
            quick_setup: recipe,
        } as unknown as Partial<SessionProtocol>);
    }

    async function startQuickSetup(template: QuickSetupTemplate) {
        const existing = stepProtocol?.steps?.length ?? 0;
        if (existing > 0) {
            const confirmed = await askConfirm({
                title: "Start from quick setup?",
                body:
                    `This experiment already has ${existing} step` +
                    `${existing === 1 ? "" : "s"}. Quick setup generates a new ` +
                    "protocol, so those steps will be replaced.",
                points: [
                    template === "image_cues"
                        ? "You will add one image per class, and the timing."
                        : "You will type the class names, and the timing.",
                    "You can switch back to editing steps by hand at any time.",
                ],
                confirmLabel: "Replace with quick setup",
                danger: true,
            });
            if (!confirmed) return;
        }
        applyRecipe(defaultQuickSetupRecipe(template));
    }

    /**
     * Leave quick setup, keeping the generated steps as ordinary editable ones.
     * Deliberately one-way and confirmed: the recipe cannot be reattached,
     * because regenerating it later would silently destroy hand edits.
     */
    async function customizeFromQuickSetup() {
        const confirmed = await askConfirm({
            title: "Convert to editable steps?",
            body:
                "Your steps stay exactly as they are — this only swaps the " +
                "quick-setup card for the full step editor.",
            points: [
                "The quick-setup card goes away and cannot be reattached.",
                "That is deliberate: regenerating it later would overwrite the " +
                    "edits you are about to make.",
            ],
            confirmLabel: "Convert to steps",
        });
        if (!confirmed) return;
        detachQuickSetup(stepProtocol?.steps ?? []);
    }

    /** Persist steps with the recipe dropped. */
    function detachQuickSetup(steps: ExperimentStep[]) {
        onPatchProtocol({
            steps,
            quick_setup: undefined,
        } as unknown as Partial<SessionProtocol>);
    }

    // --- Step editing (the same tree operations the panel used to own) ------
    // Every hand edit to the step tree funnels through here, which makes this
    // the one place that has to detach the recipe — the same choke-point
    // argument that gates read-only mode in the editor.
    function commitSteps(steps: ExperimentStep[]) {
        if (quickSetup) {
            detachQuickSetup(steps);
            return;
        }
        onPatchProtocol({ steps } as Partial<SessionProtocol>);
    }

    // Steps are edited as a plain tree; a repeat group is the only container,
    // and `parentId` addresses "inside that group" so one set of handlers
    // covers both levels.
    function mapSteps(
        steps: ExperimentStep[],
        parentId: string | null,
        change: (list: ExperimentStep[]) => ExperimentStep[],
    ): ExperimentStep[] {
        if (parentId === null) return change(steps);
        return steps.map((step) =>
            step.kind === "repeat" && step.id === parentId
                ? { ...step, steps: change(step.steps) }
                : step,
        );
    }

    function patchStep(
        parentId: string | null,
        stepId: string,
        patch: Record<string, unknown>,
    ) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) =>
                list.map((step) =>
                    step.id === stepId
                        ? ({ ...step, ...patch } as ExperimentStep)
                        : step,
                ),
            ),
        );
    }

    function removeStep(parentId: string | null, stepId: string) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) =>
                list.filter((step) => step.id !== stepId),
            ),
        );
    }

    function moveStep(parentId: string | null, stepId: string, delta: number) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) => {
                const index = list.findIndex((step) => step.id === stepId);
                const target = index + delta;
                if (index < 0 || target < 0 || target >= list.length) return list;
                const next = [...list];
                [next[index], next[target]] = [next[target], next[index]];
                return next;
            }),
        );
    }

    // What each kind is called in the type selector. The standalone `wait`
    // kind is retired from the palette — an instruction with "Wait for input"
    // covers it — but existing protocols still carry wait steps, so the
    // selector keeps the option whenever the step already is one.
    const STEP_KIND_LABELS: Record<ExperimentStepKind, string> = {
        instruction: "Instruction",
        cue: "Cue (recorded class)",
        rest: "Rest",
        wait: "Wait for input",
        repeat: "Repeat group",
    };

    const KIND_COLORS: Record<ExperimentStepKind, string> = {
        instruction: "#60a5fa",
        cue: "#34d399",
        rest: "#64748b",
        wait: "#fbbf24",
        repeat: "#a78bfa",
    };

    // The add-step palette: what each kind is FOR, not just its name.
    const STEP_ADD_BUTTONS: {
        kind: ExperimentStepKind;
        label: string;
        hint: string;
    }[] = [
        {
            kind: "instruction",
            label: "Instruction",
            hint: "Show text for a fixed time — or hold until Continue with the wait-for-input toggle",
        },
        {
            kind: "cue",
            label: "Cue",
            hint: "The recorded class — the data a classifier learns from",
        },
        {
            kind: "rest",
            label: "Rest",
            hint: "A break between cues, labelled with the rest class",
        },
        {
            kind: "repeat",
            label: "Repeat group",
            hint: "Run a set of steps N times, optionally shuffled per pass (seeded)",
        },
    ];

    function blankStep(kind: ExperimentStepKind): ExperimentStep {
        const id = newStepId(kind);
        if (kind === "cue")
            return { id, kind, label: "gesture", text: "Do the thing", duration_s: 2 };
        if (kind === "rest") return { id, kind, text: "Rest", duration_s: 2 };
        if (kind === "wait")
            return { id, kind, text: "Ready to continue?", continue_label: "Continue" };
        if (kind === "repeat")
            return {
                id,
                kind,
                times: 3,
                shuffle: true,
                seed: 1,
                // Interleaved by default: a cued block almost always wants a
                // rest between cues, and it is one toggle to turn off.
                interleave_rest: { duration_s: 2 },
                steps: [],
            };
        return { id, kind: "instruction", text: "Explain the task", duration_s: 5 };
    }

    function addStep(parentId: string | null, kind: ExperimentStepKind) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) => [
                ...list,
                blankStep(kind),
            ]),
        );
    }

    // Swap a step wholesale (patchStep merges, which would let fields of the old
    // kind linger on the new one).
    function replaceStep(
        parentId: string | null,
        stepId: string,
        next: ExperimentStep,
    ) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) =>
                list.map((step) => (step.id === stepId ? next : step)),
            ),
        );
    }

    // Change a step's kind while keeping what the author already typed wherever
    // it still means something.
    function retypeStep(
        step: ExperimentStep,
        kind: ExperimentStepKind,
    ): ExperimentStep {
        if (step.kind === kind) return step;
        const next = {
            ...blankStep(kind),
            id: step.id,
            tutorial: step.tutorial,
        } as ExperimentStep;
        if (step.kind !== "repeat" && next.kind !== "repeat") {
            if (step.text) next.text = step.text;
            if (step.image_url) {
                next.image_url = step.image_url;
                next.image_name = step.image_name;
            }
            if (step.audio_url) {
                next.audio_url = step.audio_url;
                next.audio_name = step.audio_name;
            }
            if ("duration_s" in step && "duration_s" in next) {
                next.duration_s = step.duration_s;
                next.jitter_s = step.jitter_s;
            }
        }
        // A legacy wait step converts to the instruction that replaced it,
        // behaviour intact: hold until the button is pressed.
        if (step.kind === "wait" && next.kind === "instruction") {
            next.wait_for_input = true;
            next.continue_label = step.continue_label;
        }
        return next;
    }

    /** A fresh seed a person can read back and share; never 0. */
    function rollSeed(): number {
        return 1 + Math.floor(Math.random() * 99999);
    }

    function cloneStepDeep(step: ExperimentStep): ExperimentStep {
        if (step.kind === "repeat") {
            return {
                ...step,
                id: newStepId(step.kind),
                steps: step.steps.map(cloneStepDeep),
            };
        }
        return { ...step, id: newStepId(step.kind) };
    }

    /** Insert a copy right after the original — build one cue/rest pair, stamp it. */
    function duplicateStep(parentId: string | null, stepId: string) {
        if (!stepProtocol) return;
        commitSteps(
            mapSteps(stepProtocol.steps, parentId, (list) => {
                const index = list.findIndex((step) => step.id === stepId);
                if (index < 0) return list;
                const next = [...list];
                next.splice(index + 1, 0, cloneStepDeep(list[index]));
                return next;
            }),
        );
    }

    // --- List / canvas view -------------------------------------------------
    // A toggle, not a replacement: the list is the canonical, keyboard-complete
    // surface, and the canvas is a second way of looking at the same protocol.
    // The prop is the DEFAULT, not the value: opening from a markers node lands
    // on the canvas, and toggling from there overrides it for this session of
    // the overlay. Reading the prop inside a derived (rather than seeding
    // $state with it) keeps it live and avoids a captures-initial-value trap.
    let stepViewOverride = $state<"list" | "canvas" | null>(null);
    const stepView = $derived(stepViewOverride ?? initialView);

    // --- Collapsible repeat groups ------------------------------------------
    // A ×3 group of 10 steps is 30s of scrolling; collapsed it is one line.
    let collapsedGroups = $state<Set<string>>(new Set());

    function toggleCollapsed(groupId: string) {
        const next = new Set(collapsedGroups);
        if (next.has(groupId)) {
            next.delete(groupId);
        } else {
            next.add(groupId);
        }
        collapsedGroups = next;
    }

    function groupSummary(step: RepeatStep): string {
        const perPassS = step.steps.reduce(
            (total, child) =>
                total +
                (child.kind === "repeat"
                    ? 0
                    : "duration_s" in child
                      ? (child.duration_s ?? 0)
                      : 0),
            0,
        );
        // Interleaved rests are compiled in, not rows, so the summary has to
        // account for them or a collapsed group under-reports its length.
        const restS = step.interleave_rest?.duration_s ?? 0;
        const interleavedS = restS > 0 ? restS * step.steps.length : 0;
        const count = step.steps.length;
        return (
            `${count} step${count === 1 ? "" : "s"}` +
            (interleavedS > 0 ? " + rests" : "") +
            ` · ~${Math.round(
                (perPassS + interleavedS) * Math.max(0, step.times ?? 0),
            )}s total`
        );
    }

    /** Turn the interleave setting on with sane defaults, or off entirely. */
    function toggleInterleaveRest(
        parentId: string | null,
        step: RepeatStep,
        enabled: boolean,
    ) {
        patchStep(parentId, step.id, {
            interleave_rest: enabled
                ? (step.interleave_rest ?? { duration_s: 2 })
                : undefined,
        });
    }

    function patchInterleaveRest(
        parentId: string | null,
        step: RepeatStep,
        patch: Partial<InterleavedRest>,
    ) {
        const current = step.interleave_rest ?? { duration_s: 2 };
        patchStep(parentId, step.id, {
            interleave_rest: { ...current, ...patch },
        });
    }

    // --- Drag to reorder -----------------------------------------------------
    // HTML5 drag & drop off the grip handle. The arrow buttons stay as the
    // keyboard/accessible path. Repeat groups can only live at the top level
    // (the step tree is one container deep by design), so a dragged group
    // refuses to drop inside another group.
    let dragging = $state<{
        parentId: string | null;
        stepId: string;
        kind: ExperimentStepKind;
    } | null>(null);
    let dropTarget = $state<{
        parentId: string | null;
        // null = append into `parentId`'s group body.
        stepId: string | null;
        position: "before" | "after" | "into";
    } | null>(null);

    function handleDragStart(
        event: DragEvent,
        parentId: string | null,
        step: ExperimentStep,
    ) {
        if (readOnly) {
            event.preventDefault();
            return;
        }
        dragging = { parentId, stepId: step.id, kind: step.kind };
        event.dataTransfer?.setData("text/plain", step.id);
        if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
        // Drag the whole card's image, not just the grip.
        const card = (event.currentTarget as HTMLElement).closest(".step-card");
        if (card && event.dataTransfer) {
            event.dataTransfer.setDragImage(card as HTMLElement, 24, 18);
        }
    }

    function handleDragEnd() {
        dragging = null;
        dropTarget = null;
    }

    function handleCardDragOver(
        event: DragEvent,
        parentId: string | null,
        step: ExperimentStep,
    ) {
        if (!dragging || dragging.stepId === step.id) return;
        // A repeat group can only live at the top level, so refuse to target a
        // position inside another group with one.
        if (dragging.kind === "repeat" && parentId !== null) return;
        event.preventDefault();
        event.stopPropagation();
        const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
        const position =
            event.clientY - rect.top < rect.height / 2 ? "before" : "after";
        dropTarget = { parentId, stepId: step.id, position };
    }

    function handleGroupBodyDragOver(event: DragEvent, group: RepeatStep) {
        if (!dragging || dragging.kind === "repeat") return;
        if (dragging.stepId === group.id) return;
        event.preventDefault();
        // Without this the event bubbles to the group's own card handler, which
        // overwrites "into the group" with "after the group card" — silently
        // turning every drop-into back into a no-op reorder. (Cards inside the
        // group already stop propagation themselves, so a finer position wins.)
        event.stopPropagation();
        dropTarget = { parentId: group.id, stepId: null, position: "into" };
    }

    function handleDrop(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        if (!stepProtocol || !dragging || !dropTarget) {
            handleDragEnd();
            return;
        }
        const draggedId = dragging.stepId;
        const target = dropTarget;

        // 1. Remove the dragged step from wherever it is.
        let moved: ExperimentStep | null = null;
        const without = (list: ExperimentStep[]) =>
            list.filter((step) => {
                if (step.id === draggedId) {
                    moved = step;
                    return false;
                }
                return true;
            });
        let next =
            dragging.parentId === null
                ? without(stepProtocol.steps)
                : stepProtocol.steps.map((step) =>
                      step.kind === "repeat" && step.id === dragging?.parentId
                          ? { ...step, steps: without(step.steps) }
                          : step,
                  );
        if (!moved) {
            handleDragEnd();
            return;
        }
        const movedStep: ExperimentStep = moved;

        // 2. Insert it at the drop position (indices computed after removal, so
        // dropping next to itself is a no-op rather than an off-by-one).
        const insert = (list: ExperimentStep[]) => {
            if (target.stepId === null) return [...list, movedStep];
            const index = list.findIndex((step) => step.id === target.stepId);
            if (index < 0) return [...list, movedStep];
            const at = target.position === "after" ? index + 1 : index;
            const out = [...list];
            out.splice(at, 0, movedStep);
            return out;
        };
        next =
            target.parentId === null
                ? insert(next)
                : next.map((step) =>
                      step.kind === "repeat" && step.id === target.parentId
                          ? { ...step, steps: insert(step.steps) }
                          : step,
                  );
        commitSteps(next);
        handleDragEnd();
    }

    // --- Media uploads -------------------------------------------------------
    let uploading = $state<Record<string, "image" | "audio" | null>>({});
    let uploadError = $state<string | null>(null);

    async function uploadMedia(
        parentId: string | null,
        step: ExperimentStep,
        slot: "image" | "audio",
        file: File,
    ) {
        uploadError = null;
        uploading = { ...uploading, [step.id]: slot };
        try {
            const form = new FormData();
            form.append("file", file);
            const response = await fetch("/api/media", {
                method: "POST",
                body: form,
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload?.message ?? `HTTP ${response.status}`);
            }
            patchStep(parentId, step.id, {
                [slot === "image" ? "image_url" : "audio_url"]: payload.url,
                [slot === "image" ? "image_name" : "audio_name"]:
                    payload.original_name || file.name,
            });
        } catch (error) {
            uploadError =
                error instanceof Error ? error.message : "Upload failed.";
        } finally {
            uploading = { ...uploading, [step.id]: null };
        }
    }

    function clearMedia(
        parentId: string | null,
        step: ExperimentStep,
        slot: "image" | "audio",
    ) {
        patchStep(parentId, step.id, {
            [slot === "image" ? "image_url" : "audio_url"]: undefined,
            [slot === "image" ? "image_name" : "audio_name"]: undefined,
        });
    }

    function mediaLabel(step: ExperimentStep, slot: "image" | "audio") {
        const named = step as unknown as Record<string, string | undefined>;
        const name = named[slot === "image" ? "image_name" : "audio_name"];
        if (name) return name;
        const url = named[slot === "image" ? "image_url" : "audio_url"];
        return url ? "attached" : "";
    }

    // --- Built-in protocols --------------------------------------------------
    const builtInProtocols = $derived([
        (() => {
            const protocol = adlStepProtocol();
            const schedule = compileStepProtocol(protocol);
            return {
                id: ADL_PROTOCOL_ID,
                label: "ADL tasks",
                description:
                    "Activities of daily living: mime each everyday task in " +
                    "turn, with a get-ready prompt and a rest between. Ported " +
                    "from the hard-coded ADL Experiment page.",
                protocol,
                cues: schedule.filter((c) => c.phase === "hold").length,
                durationS: Math.round(stepProtocolDurationMs(schedule) / 1000),
            };
        })(),
    ]);

    async function applyBuiltInProtocol(
        builtIn: (typeof builtInProtocols)[number],
    ) {
        const existing = stepProtocol?.steps?.length ?? 0;
        if (existing > 0) {
            const confirmed = await askConfirm({
                title: `Load the ${builtIn.label} protocol?`,
                body:
                    `This replaces the ${existing} step` +
                    `${existing === 1 ? "" : "s"} in this experiment with ` +
                    `${builtIn.cues} task${builtIn.cues === 1 ? "" : "s"} ` +
                    `(~${Math.round(builtIn.durationS / 60)} min). You can edit ` +
                    "it afterwards like any other protocol.",
                confirmLabel: `Load ${builtIn.label}`,
                danger: true,
            });
            if (!confirmed) return;
        }
        onPatchProtocol(builtIn.protocol as unknown as Partial<SessionProtocol>);
    }

    function convertToSteps() {
        if (!bound?.protocol) return;
        const converted = stepsFromLegacyProtocol(bound.protocol as never);
        onPatchProtocol(converted as unknown as Partial<SessionProtocol>);
    }

    function parseClassList(raw: string): string[] {
        return raw
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
    }

    function focusOnOpen(node: HTMLElement) {
        node.focus();
    }
</script>

<svelte:window
    onkeydown={(event) => {
        if (event.key === "Escape") onClose();
    }}
/>

<div
    class="designer-overlay"
    role="presentation"
    onclick={(event) => {
        // Only a click on the backdrop itself dismisses; clicks inside the
        // panel bubble up here and are ignored.
        if (event.target === event.currentTarget) onClose();
    }}
>
    <div
        class="designer-panel"
        role="dialog"
        tabindex="-1"
        aria-label={`${bound.label || bound.experiment_id} protocol designer`}
        use:focusOnOpen
    >
        <div class="designer-header">
            <div class="header-identity">
                <p class="eyebrow">Experiment designer</p>
                <div class="header-fields">
                    <label class="field name-field">
                        <span>Experiment name</span>
                        <input
                            value={bound.label}
                            disabled={readOnly}
                            oninput={(event) =>
                                onPatch({
                                    label: (event.currentTarget as HTMLInputElement)
                                        .value,
                                })}
                        />
                    </label>
                    {#if bound.protocol}
                        <label class="field name-field">
                            <span>Protocol name</span>
                            <input
                                value={bound.protocol.label}
                                disabled={readOnly}
                                oninput={(event) =>
                                    onPatchProtocol({
                                        label: (
                                            event.currentTarget as HTMLInputElement
                                        ).value,
                                    })}
                            />
                        </label>
                    {/if}
                    {#if stepProtocol}
                        <label
                            class="field num-field"
                            title="Base seed for randomized timing (± jitter on steps). The same seed compiles the same schedule — reroll for a new variation."
                        >
                            <span>Timing seed</span>
                            <input
                                type="number"
                                min="1"
                                disabled={readOnly}
                                value={stepProtocol.seed ?? 1}
                                oninput={(event) =>
                                    onPatchProtocol({
                                        seed: Number(
                                            (
                                                event.currentTarget as HTMLInputElement
                                            ).value,
                                        ),
                                    })}
                            />
                        </label>
                        <button
                            type="button"
                            class="icon-btn dice-btn"
                            disabled={readOnly}
                            title="Reroll the timing seed"
                            onclick={() => onPatchProtocol({ seed: rollSeed() })}
                        >
                            <Dices size={13} />
                        </button>
                    {/if}
                </div>
            </div>
            <div class="header-side">
                {#if timeline}
                    <div class="summary-chips">
                        <span class="chip">
                            {timeline.holdCues} cues · ~{formatSeconds(
                                timeline.totalMs,
                            )}
                        </span>
                        {#if timeline.waits > 0}
                            <span class="chip wait">
                                {timeline.waits} wait{timeline.waits > 1 ? "s" : ""}
                            </span>
                        {/if}
                        {#if timeline.tutorialCues > 0}
                            <span class="chip tutorial">
                                {timeline.tutorialCues} practice (not trained on)
                            </span>
                        {/if}
                    </div>
                {/if}
                <button
                    type="button"
                    class="icon-btn"
                    title="Close the designer (Esc)"
                    onclick={onClose}
                >
                    <X size={16} />
                </button>
            </div>
        </div>

        <div class="designer-body">
            {#if !bound.protocol}
                <p class="muted-text">
                    This experiment has no protocol yet — it may predate protocol
                    storage. Load a built-in below to start.
                </p>
            {:else if !stepProtocol}
                {@const protocol = bound.protocol}
                <!-- The fixed classes x repetitions form. A step protocol
                     replaces it, so only one shape is editable at a time. -->
                <p class="hint-text">
                    This is a fixed-shape protocol: every class is held for the
                    same time, repeated the same number of rounds. Convert it to
                    editable steps for instructions, practice blocks and
                    per-step control — the timeline stays identical.
                </p>
                <div class="legacy-grid">
                    <label class="field grow">
                        <span>Classes (comma-separated labels)</span>
                        <input
                            value={protocol.classes.join(", ")}
                            disabled={readOnly}
                            oninput={(event) =>
                                onPatchProtocol({
                                    classes: parseClassList(
                                        (event.currentTarget as HTMLInputElement)
                                            .value,
                                    ),
                                })}
                        />
                    </label>
                    <label class="field">
                        <span>Rest / idle class</span>
                        <input
                            value={protocol.rest_class}
                            disabled={readOnly}
                            oninput={(event) =>
                                onPatchProtocol({
                                    rest_class: (
                                        event.currentTarget as HTMLInputElement
                                    ).value,
                                })}
                        />
                    </label>
                    {#each [["Repetitions", "repetitions", 1, 1], ["Hold (s)", "hold_s", 0, 0.5], ["Rest (s)", "rest_s", 0, 0.5], ["Lead-in (s)", "lead_in_s", 0, 0.5], ["Tail rest (s)", "tail_rest_s", 0, 0.5], ["Shuffle seed", "seed", 1, 1]] as [label, key, min, stepBy]}
                        <label class="field num-field">
                            <span>{label}</span>
                            <input
                                type="number"
                                {min}
                                step={stepBy}
                                disabled={readOnly}
                                value={(protocol as unknown as Record<string, number>)[
                                    key as string
                                ]}
                                oninput={(event) =>
                                    onPatchProtocol({
                                        [key as string]: Number(
                                            (event.currentTarget as HTMLInputElement)
                                                .value,
                                        ),
                                    } as Partial<SessionProtocol>)}
                            />
                        </label>
                    {/each}
                </div>
                <button
                    type="button"
                    class="action-btn"
                    disabled={readOnly}
                    onclick={convertToSteps}
                    title="Rewrite this protocol as editable steps — the timeline is unchanged"
                >
                    Convert to editable steps
                </button>
            {:else if quickSetup}
                <QuickSetupCard
                    recipe={quickSetup}
                    {readOnly}
                    restClass={stepProtocol?.rest_class || "rest"}
                    estimatedS={quickSetupEstimateS}
                    onChange={applyRecipe}
                    onCustomize={customizeFromQuickSetup}
                />
            {:else}
                <div class="quick-setup-entry">
                    <span class="hint-text">
                        Want the short version? Quick setup asks a few questions
                        &mdash; drop in one image per class, set the timing &mdash;
                        and generates the protocol for you.
                    </span>
                    <div class="quick-setup-entry-actions">
                        <button
                            type="button"
                            class="action-btn secondary"
                            disabled={readOnly}
                            title="Generate a protocol from images, one class per image"
                            onclick={() => startQuickSetup("image_cues")}
                        >
                            <Sparkles size={13} />
                            Quick setup from images
                        </button>
                        <button
                            type="button"
                            class="action-btn secondary"
                            disabled={readOnly}
                            title="Generate a protocol from a list of class names"
                            onclick={() => startQuickSetup("gesture_list")}
                        >
                            <Sparkles size={13} />
                            From class names
                        </button>
                    </div>
                </div>
                <div class="view-switch-row">
                    <p class="hint-text">
                        Each step is shown to the participant in order. A
                        <strong>cue</strong> records its class label; an
                        instruction with <strong>wait for input</strong> holds
                        the session until someone presses the button; anything
                        marked <strong>tutorial</strong> is recorded but kept
                        out of training.{stepView === "list"
                            ? " Drag the grip to reorder."
                            : ""}
                    </p>
                    <div class="view-switch" role="tablist" aria-label="Step view">
                        <button
                            type="button"
                            role="tab"
                            aria-selected={stepView === "list"}
                            class="view-tab"
                            class:active={stepView === "list"}
                            title="Edit every field inline, in order"
                            onclick={() => (stepViewOverride = "list")}
                        >
                            <List size={12} />
                            List
                        </button>
                        <button
                            type="button"
                            role="tab"
                            aria-selected={stepView === "canvas"}
                            class="view-tab"
                            class:active={stepView === "canvas"}
                            title="See the shape of the protocol; zoom into repeat groups"
                            onclick={() => (stepViewOverride = "canvas")}
                        >
                            <Network size={12} />
                            Canvas
                        </button>
                    </div>
                </div>

                {#snippet stepRow(
                    step: ExperimentStep,
                    parentId: string | null,
                )}
                    <div
                        class={`step-card kind-${step.kind}`}
                        class:tutorial={step.tutorial}
                        class:drop-before={dropTarget?.stepId === step.id &&
                            dropTarget.position === "before"}
                        class:drop-after={dropTarget?.stepId === step.id &&
                            dropTarget.position === "after"}
                        class:dragging={dragging?.stepId === step.id}
                        role="listitem"
                        ondragover={(event) =>
                            handleCardDragOver(event, parentId, step)}
                        ondrop={handleDrop}
                    >
                        <div class="card-main">
                            <button
                                type="button"
                                class="drag-handle"
                                draggable={!readOnly}
                                title="Drag to reorder"
                                aria-label="Drag to reorder"
                                ondragstart={(event) =>
                                    handleDragStart(event, parentId, step)}
                                ondragend={handleDragEnd}
                            >
                                <GripVertical size={14} />
                            </button>

                            {#if step.kind === "repeat"}
                                <button
                                    type="button"
                                    class="icon-btn collapse-btn"
                                    title={collapsedGroups.has(step.id)
                                        ? "Expand this group"
                                        : "Collapse this group"}
                                    onclick={() => toggleCollapsed(step.id)}
                                >
                                    {#if collapsedGroups.has(step.id)}
                                        <ChevronRight size={13} />
                                    {:else}
                                        <ChevronDown size={13} />
                                    {/if}
                                </button>
                            {/if}

                            <StepFields
                                {step}
                                {readOnly}
                                restClass={stepProtocol?.rest_class || "rest"}
                                collapsed={collapsedGroups.has(step.id)}
                                uploadingSlot={uploading[step.id] ?? null}
                                groupSummaryText={step.kind === "repeat"
                                    ? groupSummary(step)
                                    : ""}
                                {retypeStep}
                                {rollSeed}
                                stepKindLabels={STEP_KIND_LABELS}
                                {mediaLabel}
                                onPatch={(patch) =>
                                    patchStep(parentId, step.id, patch)}
                                onReplace={(next) =>
                                    replaceStep(parentId, step.id, next)}
                                onPatchInterleave={(patch) =>
                                    step.kind === "repeat" &&
                                    patchInterleaveRest(parentId, step, patch)}
                                onToggleInterleave={(enabled) =>
                                    step.kind === "repeat" &&
                                    toggleInterleaveRest(parentId, step, enabled)}
                                onUploadMedia={(slot, file) =>
                                    uploadMedia(parentId, step, slot, file)}
                                onClearMedia={(slot) =>
                                    clearMedia(parentId, step, slot)}
                            />

                            <div class="step-actions">
                                <button
                                    type="button"
                                    class="icon-btn"
                                    disabled={readOnly}
                                    title="Duplicate this step"
                                    onclick={() => duplicateStep(parentId, step.id)}
                                >
                                    <Copy size={12} />
                                </button>
                                <button
                                    type="button"
                                    class="icon-btn"
                                    disabled={readOnly}
                                    title="Move up"
                                    onclick={() => moveStep(parentId, step.id, -1)}
                                >
                                    <ChevronUp size={12} />
                                </button>
                                <button
                                    type="button"
                                    class="icon-btn"
                                    disabled={readOnly}
                                    title="Move down"
                                    onclick={() => moveStep(parentId, step.id, 1)}
                                >
                                    <ChevronDown size={12} />
                                </button>
                                <button
                                    type="button"
                                    class="icon-btn"
                                    disabled={readOnly}
                                    title="Remove this step"
                                    onclick={() => removeStep(parentId, step.id)}
                                >
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        </div>

                        {#if step.kind !== "repeat"}
                            <div class="step-media">
                                {#each [["image", "Image", "image/*"], ["audio", "Sound", "audio/*"]] as [slot, label, accept]}
                                    {@const attached = mediaLabel(
                                        step,
                                        slot as "image" | "audio",
                                    )}
                                    <div class="media-slot">
                                        {#if slot === "image"}
                                            <ImageIcon size={11} />
                                        {:else}
                                            <Volume2 size={11} />
                                        {/if}
                                        {#if attached}
                                            <span class="media-name" title={attached}
                                                >{attached}</span
                                            >
                                            <button
                                                type="button"
                                                class="icon-btn"
                                                disabled={readOnly}
                                                title={`Remove this ${label.toLowerCase()}`}
                                                onclick={() =>
                                                    clearMedia(
                                                        parentId,
                                                        step,
                                                        slot as "image" | "audio",
                                                    )}
                                            >
                                                <Trash2 size={11} />
                                            </button>
                                        {:else}
                                            <label class="media-pick">
                                                {uploading[step.id] === slot
                                                    ? "Uploading…"
                                                    : `Add ${label.toLowerCase()}`}
                                                <input
                                                    type="file"
                                                    accept={accept}
                                                    disabled={readOnly ||
                                                        uploading[step.id] != null}
                                                    onchange={(event) => {
                                                        const input =
                                                            event.currentTarget as HTMLInputElement;
                                                        const file =
                                                            input.files?.[0];
                                                        if (file) {
                                                            void uploadMedia(
                                                                parentId,
                                                                step,
                                                                slot as
                                                                    | "image"
                                                                    | "audio",
                                                                file,
                                                            );
                                                        }
                                                        input.value = "";
                                                    }}
                                                />
                                            </label>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {/if}

                        {#if step.kind === "repeat" && !collapsedGroups.has(step.id)}
                            <div
                                class="group-children"
                                class:drop-into={dropTarget?.parentId ===
                                    step.id && dropTarget.stepId === null}
                                role="list"
                                ondragover={(event) =>
                                    handleGroupBodyDragOver(event, step)}
                                ondrop={handleDrop}
                            >
                                {#each step.steps as child (child.id)}
                                    {@render stepRow(child, step.id)}
                                {/each}
                                {#if step.steps.length === 0}
                                    <p class="hint-text">
                                        Empty group — add or drag steps in.
                                    </p>
                                {/if}
                                <div class="step-add nested">
                                    {#each STEP_ADD_BUTTONS.filter((entry) => entry.kind !== "repeat") as entry}
                                        <button
                                            type="button"
                                            class="add-step-btn"
                                            disabled={readOnly}
                                            title={entry.hint}
                                            onclick={() =>
                                                addStep(step.id, entry.kind)}
                                        >
                                            <Plus size={11} />
                                            <span
                                                class="kind-dot"
                                                style={`background:${KIND_COLORS[entry.kind]}`}
                                            ></span>
                                            {entry.label}
                                        </button>
                                    {/each}
                                </div>
                            </div>
                        {/if}
                    </div>
                {/snippet}

                {#if stepView === "canvas"}
                    <ProtocolCanvas
                        protocol={stepProtocol}
                        {readOnly}
                        {uploading}
                        stepKindLabels={STEP_KIND_LABELS}
                        kindColors={KIND_COLORS}
                        {retypeStep}
                        {rollSeed}
                        {mediaLabel}
                        {groupSummary}
                        onPatchStep={patchStep}
                        onReplaceStep={replaceStep}
                        onPatchInterleave={patchInterleaveRest}
                        onToggleInterleave={toggleInterleaveRest}
                        onUploadMedia={(parentId, step, slot, file) =>
                            void uploadMedia(parentId, step, slot, file)}
                        onClearMedia={clearMedia}
                        onAddStep={addStep}
                        onRemoveStep={removeStep}
                        onMoveStep={moveStep}
                    />
                    {#if uploadError}
                        <p class="hint-text upload-error">{uploadError}</p>
                    {/if}
                {:else}
                    <div class="step-list" role="list">
                        {#each stepProtocol.steps as step (step.id)}
                            {@render stepRow(step, null)}
                        {/each}
                        {#if stepProtocol.steps.length === 0}
                            <p class="hint-text">No steps yet — add one below.</p>
                        {/if}
                    </div>
                    {#if uploadError}
                        <p class="hint-text upload-error">{uploadError}</p>
                    {/if}
                    <div class="step-add">
                        {#each STEP_ADD_BUTTONS as entry}
                            <button
                                type="button"
                                class="add-step-btn"
                                disabled={readOnly}
                                title={entry.hint}
                                onclick={() => addStep(null, entry.kind)}
                            >
                                <Plus size={11} />
                                <span
                                    class="kind-dot"
                                    style={`background:${KIND_COLORS[entry.kind]}`}
                                ></span>
                                {entry.label}
                            </button>
                        {/each}
                    </div>
                {/if}
            {/if}

            <div class="builtin-section">
                <p class="eyebrow">Built-in protocols</p>
                <p class="hint-text">
                    Loading one replaces this experiment's protocol; edit it
                    afterwards like any other.
                </p>
                {#each builtInProtocols as builtIn}
                    <div class="builtin-protocol">
                        <div class="builtin-protocol-main">
                            <strong>{builtIn.label}</strong>
                            <span class="hint-text"
                                >{builtIn.cues} tasks · ~{Math.round(
                                    builtIn.durationS / 60,
                                )} min</span
                            >
                        </div>
                        <button
                            type="button"
                            class="action-btn secondary"
                            disabled={readOnly}
                            title={builtIn.description}
                            onclick={() => applyBuiltInProtocol(builtIn)}
                        >
                            Load
                        </button>
                    </div>
                {/each}
            </div>
        </div>

        {#if timeline}
            <!-- The compiled schedule, always in view: edit a duration above and
                 watch the strip change. Cues are colored per class; instructions
                 and rests are muted; a wait is a tick (it has no length until
                 someone releases it); tutorial spans are hatched. -->
            <div class="designer-timeline">
                <div class="timeline-track">
                    {#each timeline.segments as segment}
                        {#if segment.wait}
                            <div
                                class="timeline-wait"
                                style={`left:${segment.leftPct}%`}
                                title={segment.title}
                            ></div>
                        {:else}
                            <div
                                class="timeline-segment"
                                class:hatched={segment.tutorial}
                                style={`left:${segment.leftPct}%; width:${segment.widthPct}%; background:${segment.color}`}
                                title={segment.title}
                            >
                                {#if segment.hold && segment.widthPct > 4}
                                    <span>{segment.label}</span>
                                {/if}
                            </div>
                        {/if}
                    {/each}
                </div>
                <div class="timeline-legend">
                    <span class="legend-total">
                        0 – {formatSeconds(timeline.totalMs)}
                        {#if timeline.waits > 0}
                            <em>+ {timeline.waits} wait{timeline.waits > 1
                                    ? "s"
                                    : ""} of unknown length</em>
                        {/if}
                    </span>
                    <div class="legend-classes">
                        {#each timeline.classes as cls}
                            <span class="legend-item">
                                <span
                                    class="legend-dot"
                                    style={`background:${timeline.colorFor(cls)}`}
                                ></span>
                                {cls}
                            </span>
                        {/each}
                    </div>
                </div>
            </div>
        {/if}
    </div>
</div>

<style>
    .designer-overlay {
        position: fixed;
        inset: 0;
        z-index: 60;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(3, 6, 14, 0.72);
        padding: 2rem;
        /* Sibling of .graph-editor, not a descendant — set our own text color
           so we don't fall back to the browser default. */
        color: #d6def4;
    }

    .designer-panel {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        width: min(94vw, 1180px);
        height: min(90vh, 860px);
        padding: 1rem 1.1rem;
        border-radius: 10px;
        background: rgba(8, 13, 26, 0.98);
        border: 1px solid rgba(110, 138, 255, 0.24);
        box-shadow: 0 30px 90px rgba(0, 0, 0, 0.5);
    }

    .designer-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
    }

    .header-identity {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 0;
    }

    .header-fields {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
    }

    .header-side {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
    }

    .summary-chips {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 0.3rem;
        max-width: 32rem;
    }

    .chip {
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.05);
        padding: 0.15rem 0.55rem;
        font-size: 0.68rem;
        color: #b9c8f0;
        white-space: nowrap;
    }

    .chip.wait {
        border-color: rgba(251, 191, 36, 0.4);
        color: #fbd88a;
    }

    .chip.tutorial {
        border-color: rgba(167, 139, 250, 0.4);
        color: #cbbcff;
    }

    .eyebrow {
        margin: 0;
        font-size: 0.65rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(230, 236, 245, 0.55);
    }

    .designer-body {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding-right: 0.3rem;
    }

    input {
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(12, 18, 28, 0.75);
        color: #e6ecf5;
        padding: 0.35rem 0.45rem;
        font-size: 0.78rem;
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
    }

    .field > span {
        font-size: 0.6rem;
        letter-spacing: 0.02em;
        color: #7f91c8;
        white-space: nowrap;
    }

    .field.grow {
        flex: 1 1 10rem;
        min-width: 8rem;
    }

    .field.label-field {
        flex: 0 1 11rem;
        min-width: 7rem;
    }

    .field.num-field {
        width: 5rem;
    }

    .field.kind-field {
        width: 10.5rem;
    }

    .field.name-field {
        width: 14rem;
    }

    .hint-text {
        margin: 0;
        font-size: 0.7rem;
        line-height: 1.45;
        color: #7f91c8;
    }

    .muted-text {
        margin: 0;
        font-size: 0.72rem;
        line-height: 1.4;
        color: rgba(230, 236, 245, 0.6);
    }

    .legacy-grid {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 0.5rem;
    }

    /* --- Step cards --- */
    .step-list {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
    }

    .step-card {
        border: 1px solid #24304f;
        border-left-width: 3px;
        border-radius: 6px;
        padding: 0.35rem 0.5rem 0.4rem;
        background: #101830;
    }

    .step-card.kind-instruction {
        border-left-color: #60a5fa;
    }
    .step-card.kind-cue {
        border-left-color: #34d399;
    }
    .step-card.kind-rest {
        border-left-color: #64748b;
    }
    .step-card.kind-wait {
        border-left-color: #fbbf24;
    }
    .step-card.kind-repeat {
        border-left-color: #a78bfa;
    }

    .step-card.tutorial {
        border-color: #4a3d6b;
        border-left-width: 3px;
        background: #17142b;
    }

    .step-card.dragging {
        opacity: 0.4;
    }

    /* Where the dragged card would land. */
    .step-card.drop-before {
        box-shadow: 0 -2px 0 0 #4f7ef7;
    }

    .step-card.drop-after {
        box-shadow: 0 2px 0 0 #4f7ef7;
    }

    .card-main {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 0.35rem 0.45rem;
    }

    .drag-handle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        align-self: center;
        border: none;
        background: none;
        color: #566592;
        padding: 0.1rem;
        cursor: grab;
    }

    .drag-handle:active {
        cursor: grabbing;
    }

    .collapse-btn {
        align-self: center;
    }

    .group-summary {
        align-self: center;
        font-size: 0.68rem;
        color: #9fb0d8;
    }

    .card-flags {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        align-self: center;
        margin-left: 0.2rem;
    }

    .step-actions {
        display: flex;
        gap: 0.1rem;
        margin-left: auto;
        align-self: center;
    }

    .step-kind {
        font-size: 0.7rem;
        padding: 0.28rem 0.25rem;
    }

    .group-children {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        margin: 0.35rem 0 0 1.4rem;
        padding: 0.35rem 0.4rem;
        border-left: 2px solid rgba(167, 139, 250, 0.3);
        border-radius: 0 6px 6px 0;
    }

    .group-children.drop-into {
        background: rgba(79, 126, 247, 0.08);
        outline: 1px dashed #4f7ef7;
    }

    .step-media {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin-top: 0.3rem;
        padding-left: 1.6rem;
    }

    .media-slot {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.64rem;
        color: #7f91c8;
        border: 1px solid #24304f;
        border-radius: 999px;
        padding: 0.1rem 0.4rem;
    }

    .media-name {
        max-width: 10rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: #b9c8f0;
    }

    .media-pick {
        cursor: pointer;
        text-decoration: underline dotted;
    }

    .media-pick input[type="file"] {
        display: none;
    }

    .upload-error {
        color: #f87171;
    }

    .step-add {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        margin-top: 0.1rem;
    }

    .step-add.nested {
        margin-top: 0.1rem;
    }

    .add-step-btn {
        display: flex;
        align-items: center;
        gap: 0.15rem;
        font-size: 0.64rem;
        padding: 0.18rem 0.35rem;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #16203c;
        color: #b9c8f0;
        cursor: pointer;
    }

    .add-step-btn:hover:not(:disabled) {
        border-color: #4f7ef7;
        color: #e4ecff;
    }

    .add-step-btn:disabled {
        opacity: 0.45;
        cursor: default;
    }

    /* The quick-setup on-ramp, shown when no recipe is attached. */
    .quick-setup-entry {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.9rem;
        border: 1px solid #24304f;
        border-radius: 8px;
        background: rgba(79, 126, 247, 0.06);
        padding: 0.5rem 0.6rem;
    }

    .quick-setup-entry-actions {
        display: flex;
        gap: 0.3rem;
        flex: none;
    }

    .view-switch-row {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
    }

    .view-switch {
        display: flex;
        gap: 0.2rem;
        flex: none;
    }

    .view-tab {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #101830;
        color: #b9c8f0;
        font-size: 0.68rem;
        padding: 0.2rem 0.6rem;
        cursor: pointer;
    }

    .view-tab.active {
        border-color: #4f7ef7;
        background: rgba(79, 126, 247, 0.18);
        color: #e4ecff;
    }

    .kind-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        flex: none;
    }

    /* Sits beside a labelled field in a flex row — align with its input. */
    .dice-btn {
        align-self: flex-end;
    }

    /* --- Built-ins --- */
    .builtin-section {
        margin-top: 0.6rem;
        padding-top: 0.6rem;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .builtin-protocol {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        border: 1px solid #24304f;
        border-radius: 6px;
        padding: 0.35rem 0.45rem;
    }

    .builtin-protocol-main {
        display: flex;
        flex-direction: column;
        gap: 0.05rem;
    }

    /* --- Timeline strip --- */
    .designer-timeline {
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        padding-top: 0.55rem;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .timeline-track {
        position: relative;
        height: 26px;
        border-radius: 6px;
        background: rgba(12, 18, 28, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.08);
        overflow: hidden;
    }

    .timeline-segment {
        position: absolute;
        top: 0;
        bottom: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        font-size: 0.6rem;
        color: rgba(6, 10, 18, 0.9);
        font-weight: 700;
        white-space: nowrap;
    }

    .timeline-segment.hatched {
        background-image: repeating-linear-gradient(
            135deg,
            rgba(10, 15, 30, 0.35) 0 4px,
            transparent 4px 8px
        );
    }

    /* A wait has no length until someone releases it — a tick, not a span. */
    .timeline-wait {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 3px;
        margin-left: -1px;
        background: #fbbf24;
        z-index: 2;
    }

    .timeline-legend {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.8rem;
        font-size: 0.66rem;
        color: #7f91c8;
    }

    .legend-total em {
        font-style: normal;
        color: #fbd88a;
    }

    .legend-classes {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 0.2rem 0.7rem;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 0.28rem;
        color: #b9c8f0;
    }

    .legend-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
    }

    /* --- Shared buttons --- */
    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        align-self: flex-start;
        border-radius: 6px;
        border: 1px solid rgba(120, 205, 255, 0.35);
        background: rgba(58, 150, 221, 0.22);
        color: #dceeff;
        padding: 0.4rem 0.65rem;
        font-size: 0.78rem;
        cursor: pointer;
    }

    .action-btn.secondary {
        border-color: rgba(255, 255, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #e6ecf5;
    }

    .action-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(255, 255, 255, 0.05);
        color: #e6ecf5;
        padding: 0.28rem;
        cursor: pointer;
    }

    .icon-btn:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }
</style>
