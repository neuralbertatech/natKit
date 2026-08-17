<script lang="ts">
    // The quick-setup surface (experiment-authoring-ux-rework, Phase 3).
    //
    // Asks only the questions that vary between sessions and generates the step
    // protocol from them, so a first experiment does not require learning cues,
    // class labels, rest classes, tutorial flags and repeat groups. The flagship
    // path is: drop images, press Record.
    //
    // Presentational + upload plumbing only: compiling the recipe into steps
    // lives in ../StreamViewer/quickSetup.ts, and persisting it lives in the
    // designer.
    import { Dices, Image as ImageIcon, Trash2, Upload, X } from "@lucide/svelte";
    import {
        labelFromFilename,
        quickSetupBlockedReason,
        recipeClasses,
        type QuickSetupCue,
        type QuickSetupRecipe,
        type QuickSetupTemplate,
    } from "../StreamViewer/quickSetup";

    interface Props {
        recipe: QuickSetupRecipe;
        readOnly: boolean;
        /** The protocol's filler class, shown so the rest label isn't a mystery. */
        restClass: string;
        /** Estimated schedule length of the generated protocol, in seconds. */
        estimatedS: number;
        onChange: (recipe: QuickSetupRecipe) => void;
        /** Leave quick setup and hand-edit the generated steps (detaches). */
        onCustomize: () => void;
    }

    let { recipe, readOnly, restClass, estimatedS, onChange, onCustomize }: Props =
        $props();

    let uploading = $state(0);
    let uploadError = $state<string | null>(null);
    let dragOver = $state(false);
    let fileInput = $state<HTMLInputElement | null>(null);

    const classes = $derived(recipeClasses(recipe));
    const blockedReason = $derived(quickSetupBlockedReason(recipe));

    function patch(next: Partial<QuickSetupRecipe>) {
        onChange({ ...recipe, ...next });
    }

    function patchCue(index: number, next: Partial<QuickSetupCue>) {
        onChange({
            ...recipe,
            cues: recipe.cues.map((cue, at) =>
                at === index ? { ...cue, ...next } : cue,
            ),
        });
    }

    function removeCue(index: number) {
        onChange({
            ...recipe,
            cues: recipe.cues.filter((_, at) => at !== index),
        });
    }

    function addBlankCue() {
        onChange({ ...recipe, cues: [...recipe.cues, { label: "" }] });
    }

    function rollSeed() {
        patch({ seed: 1 + Math.floor(Math.random() * 99999) });
    }

    // One upload per image, all in flight together; each becomes a class whose
    // label is guessed from the filename and stays editable.
    async function uploadImages(files: File[]) {
        const images = files.filter((file) => file.type.startsWith("image/"));
        if (images.length === 0) {
            uploadError = "Those files are not images.";
            return;
        }
        uploadError = null;
        uploading += images.length;
        const results = await Promise.all(
            images.map(async (file): Promise<QuickSetupCue | null> => {
                try {
                    const form = new FormData();
                    form.append("file", file);
                    const response = await fetch("/api/media", {
                        method: "POST",
                        body: form,
                    });
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        throw new Error(
                            payload?.message ?? `HTTP ${response.status}`,
                        );
                    }
                    const name: string = payload.original_name || file.name;
                    return {
                        label: labelFromFilename(name),
                        image_url: payload.url as string,
                        image_name: name,
                    };
                } catch (error) {
                    uploadError =
                        error instanceof Error ? error.message : "Upload failed.";
                    return null;
                } finally {
                    uploading -= 1;
                }
            }),
        );
        const added = results.filter((cue): cue is QuickSetupCue => cue !== null);
        if (added.length > 0) {
            onChange({ ...recipe, cues: [...recipe.cues, ...added] });
        }
    }

    function handleDrop(event: DragEvent) {
        event.preventDefault();
        dragOver = false;
        if (readOnly) return;
        const files = [...(event.dataTransfer?.files ?? [])];
        if (files.length > 0) void uploadImages(files);
    }

    /** Class names as one editable line — faster than a row per class. */
    const classLine = $derived(recipe.cues.map((cue) => cue.label).join(", "));

    function applyClassLine(raw: string) {
        const labels = raw
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);
        // Keep any media already attached to a label the author is re-typing.
        const byLabel = new Map(
            recipe.cues.map((cue) => [cue.label.trim(), cue] as const),
        );
        onChange({
            ...recipe,
            cues: labels.map((label) => byLabel.get(label) ?? { label }),
        });
    }

    function setTemplate(template: QuickSetupTemplate) {
        patch({ template });
    }

    function formatSeconds(totalS: number): string {
        const seconds = Math.round(totalS);
        if (seconds < 60) return `${seconds}s`;
        return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    }
</script>

<div class="quick-setup">
    <div class="qs-header">
        <div>
            <p class="eyebrow">Quick setup</p>
            <p class="hint-text">
                Answer a few questions and the protocol is generated for you.
                Everything here stays editable, and you can drop into the full
                step editor whenever you need to.
            </p>
        </div>
        <button
            type="button"
            class="action-btn secondary"
            disabled={readOnly}
            title="Convert this recipe into editable steps. The recipe is detached, so it will not overwrite your edits later."
            onclick={onCustomize}
        >
            Customize steps…
        </button>
    </div>

    <div class="template-tabs" role="tablist">
        {#each [["image_cues", "Images"], ["gesture_list", "Class names"]] as [value, label]}
            <button
                type="button"
                role="tab"
                aria-selected={recipe.template === value}
                class="template-tab"
                class:active={recipe.template === value}
                disabled={readOnly}
                onclick={() => setTemplate(value as QuickSetupTemplate)}
            >
                {label}
            </button>
        {/each}
    </div>

    {#if recipe.template === "image_cues"}
        <!-- The flagship path: one image per class, label guessed from the
             filename so the common case needs no typing. -->
        <div
            class="drop-zone"
            class:drag-over={dragOver}
            role="button"
            tabindex="0"
            aria-label="Add cue images"
            ondragover={(event) => {
                event.preventDefault();
                dragOver = true;
            }}
            ondragleave={() => (dragOver = false)}
            ondrop={handleDrop}
            onclick={() => !readOnly && fileInput?.click()}
            onkeydown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    if (!readOnly) fileInput?.click();
                }
            }}
        >
            <Upload size={18} />
            <span>
                {uploading > 0
                    ? `Uploading ${uploading} image${uploading > 1 ? "s" : ""}…`
                    : "Drop images here, or click to choose"}
            </span>
            <span class="hint-text">One image per class</span>
            <input
                bind:this={fileInput}
                type="file"
                accept="image/*"
                multiple
                disabled={readOnly}
                onchange={(event) => {
                    const input = event.currentTarget as HTMLInputElement;
                    const files = [...(input.files ?? [])];
                    if (files.length > 0) void uploadImages(files);
                    input.value = "";
                }}
            />
        </div>

        {#if recipe.cues.length > 0}
            <div class="cue-grid">
                {#each recipe.cues as cue, index (cue.image_url ?? index)}
                    <div class="cue-tile">
                        {#if cue.image_url}
                            <img src={cue.image_url} alt={cue.label || "cue"} />
                        {:else}
                            <div class="cue-tile-placeholder">
                                <ImageIcon size={16} />
                            </div>
                        {/if}
                        <label class="field">
                            <span>Class label</span>
                            <input
                                value={cue.label}
                                placeholder="e.g. fist"
                                disabled={readOnly}
                                oninput={(event) =>
                                    patchCue(index, {
                                        label: (
                                            event.currentTarget as HTMLInputElement
                                        ).value,
                                    })}
                            />
                        </label>
                        <button
                            type="button"
                            class="icon-btn tile-remove"
                            disabled={readOnly}
                            title="Remove this cue"
                            onclick={() => removeCue(index)}
                        >
                            <X size={12} />
                        </button>
                    </div>
                {/each}
            </div>
        {/if}
    {:else}
        <label class="field">
            <span>Classes (comma-separated)</span>
            <input
                value={classLine}
                placeholder="e.g. fist, open, pinch"
                disabled={readOnly}
                onchange={(event) =>
                    applyClassLine((event.currentTarget as HTMLInputElement).value)}
            />
        </label>
        {#if recipe.cues.length > 0}
            <div class="class-rows">
                {#each recipe.cues as cue, index (index)}
                    <div class="class-row">
                        <label class="field grow">
                            <span>Shown to participant</span>
                            <input
                                value={cue.text ?? ""}
                                placeholder={cue.label}
                                disabled={readOnly}
                                oninput={(event) =>
                                    patchCue(index, {
                                        text:
                                            (
                                                event.currentTarget as HTMLInputElement
                                            ).value || undefined,
                                    })}
                            />
                        </label>
                        <span class="class-chip">{cue.label}</span>
                        <button
                            type="button"
                            class="icon-btn"
                            disabled={readOnly}
                            title="Remove this class"
                            onclick={() => removeCue(index)}
                        >
                            <Trash2 size={12} />
                        </button>
                    </div>
                {/each}
            </div>
        {/if}
        <button
            type="button"
            class="add-btn"
            disabled={readOnly}
            onclick={addBlankCue}
        >
            Add a class
        </button>
    {/if}

    {#if uploadError}
        <p class="hint-text upload-error">{uploadError}</p>
    {/if}

    <div class="knobs">
        {#each [["Rounds", "repetitions", 1, 1], ["Hold (s)", "hold_s", 0, 0.5], ["Rest (s)", "rest_s", 0, 0.5], ["± Rest jitter (s)", "rest_jitter_s", 0, 0.5], ["Get ready (s)", "lead_in_s", 0, 0.5]] as [label, key, min, stepBy]}
            <label
                class="field num-field"
                title={key === "rest_jitter_s"
                    ? "Randomize each rest ± this much, from the protocol's timing seed, so cue onsets can't be anticipated"
                    : undefined}
            >
                <span>{label}</span>
                <input
                    type="number"
                    {min}
                    step={stepBy}
                    disabled={readOnly}
                    value={(recipe as unknown as Record<string, number | undefined>)[
                        key as string
                    ] ?? 0}
                    oninput={(event) => {
                        const value = Number(
                            (event.currentTarget as HTMLInputElement).value,
                        );
                        patch({
                            [key as string]:
                                key === "rest_jitter_s" && value <= 0
                                    ? undefined
                                    : value,
                        } as Partial<QuickSetupRecipe>);
                    }}
                />
            </label>
        {/each}
    </div>

    <div class="toggles">
        <label
            class="field check"
            title="Shuffle the class order on every round, from a stored seed so the run is reproducible"
        >
            <input
                type="checkbox"
                disabled={readOnly}
                checked={recipe.shuffle}
                onchange={(event) =>
                    patch({
                        shuffle: (event.currentTarget as HTMLInputElement).checked,
                    })}
            />
            <span>Shuffle each round</span>
        </label>
        {#if recipe.shuffle}
            <label class="field num-field" title="Shuffle seed">
                <span>Seed</span>
                <input
                    type="number"
                    min="1"
                    disabled={readOnly}
                    value={recipe.seed ?? 1}
                    oninput={(event) =>
                        patch({
                            seed: Number(
                                (event.currentTarget as HTMLInputElement).value,
                            ),
                        })}
                />
            </label>
            <button
                type="button"
                class="icon-btn dice-btn"
                disabled={readOnly}
                title="Reroll the shuffle seed"
                onclick={rollSeed}
            >
                <Dices size={12} />
            </button>
        {/if}
        <label
            class="field check"
            title="One practice pass through the classes first — recorded and flagged, but excluded from training"
        >
            <input
                type="checkbox"
                disabled={readOnly}
                checked={recipe.practice_pass}
                onchange={(event) =>
                    patch({
                        practice_pass: (event.currentTarget as HTMLInputElement)
                            .checked,
                    })}
            />
            <span>Practice pass first</span>
        </label>
        <label
            class="field check"
            title="Hold before the real recording until someone presses the button"
        >
            <input
                type="checkbox"
                disabled={readOnly}
                checked={recipe.wait_for_ready}
                onchange={(event) =>
                    patch({
                        wait_for_ready: (event.currentTarget as HTMLInputElement)
                            .checked,
                    })}
            />
            <span>Wait for “ready”</span>
        </label>
    </div>

    <div class="qs-summary">
        {#if blockedReason}
            <span class="blocked">{blockedReason}</span>
        {:else}
            <span>
                <strong>{classes.length}</strong>
                class{classes.length === 1 ? "" : "es"} ·
                <strong>{recipe.repetitions}</strong>
                round{recipe.repetitions === 1 ? "" : "s"} ·
                <strong>{classes.length * recipe.repetitions}</strong> recorded cues
                · ≈ <strong>{formatSeconds(estimatedS)}</strong>
            </span>
            <span class="hint-text">
                Rests are labelled <code>{restClass}</code>{recipe.practice_pass
                    ? " · practice is recorded but not trained on"
                    : ""}
            </span>
        {/if}
    </div>
</div>

<style>
    .quick-setup {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
    }

    .qs-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
    }

    .eyebrow {
        margin: 0;
        font-size: 0.65rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(230, 236, 245, 0.55);
    }

    .hint-text {
        margin: 0;
        font-size: 0.68rem;
        line-height: 1.45;
        color: #7f91c8;
    }

    .template-tabs {
        display: flex;
        gap: 0.25rem;
    }

    .template-tab {
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #101830;
        color: #b9c8f0;
        font-size: 0.7rem;
        padding: 0.22rem 0.7rem;
        cursor: pointer;
    }

    .template-tab.active {
        border-color: #4f7ef7;
        background: rgba(79, 126, 247, 0.18);
        color: #e4ecff;
    }

    .drop-zone {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.2rem;
        padding: 1.1rem;
        border: 1px dashed #33436e;
        border-radius: 8px;
        background: rgba(12, 18, 28, 0.5);
        color: #b9c8f0;
        font-size: 0.75rem;
        cursor: pointer;
    }

    .drop-zone.drag-over {
        border-color: #4f7ef7;
        background: rgba(79, 126, 247, 0.1);
    }

    .drop-zone input[type="file"] {
        display: none;
    }

    .cue-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
        gap: 0.4rem;
    }

    .cue-tile {
        position: relative;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        border: 1px solid #24304f;
        border-radius: 8px;
        background: #101830;
        padding: 0.35rem;
    }

    .cue-tile img,
    .cue-tile-placeholder {
        width: 100%;
        height: 5.5rem;
        border-radius: 6px;
        object-fit: contain;
        background: #0a0f1e;
    }

    .cue-tile-placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #566592;
    }

    .tile-remove {
        position: absolute;
        top: 0.3rem;
        right: 0.3rem;
        background: rgba(8, 13, 26, 0.85);
    }

    .class-rows {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
    }

    .class-row {
        display: flex;
        align-items: flex-end;
        gap: 0.4rem;
    }

    .class-chip {
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: rgba(52, 211, 153, 0.16);
        color: #86efac;
        font-size: 0.7rem;
        white-space: nowrap;
    }

    .add-btn {
        align-self: flex-start;
        border: 1px solid #24304f;
        border-radius: 999px;
        background: #16203c;
        color: #b9c8f0;
        font-size: 0.68rem;
        padding: 0.2rem 0.6rem;
        cursor: pointer;
    }

    .knobs,
    .toggles {
        display: flex;
        flex-wrap: wrap;
        align-items: flex-end;
        gap: 0.35rem 0.7rem;
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
    }

    .field > span {
        font-size: 0.6rem;
        color: #7f91c8;
        white-space: nowrap;
    }

    .field.grow {
        flex: 1 1 8rem;
    }

    .field.num-field {
        width: 6.2rem;
    }

    .field.check {
        flex-direction: row;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.66rem;
        color: #7f91c8;
        cursor: pointer;
        white-space: nowrap;
    }

    .field.check > span {
        font-size: 0.66rem;
    }

    .field.check input[type="checkbox"] {
        width: auto;
        margin: 0;
    }

    input {
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: rgba(12, 18, 28, 0.75);
        color: #e6ecf5;
        padding: 0.3rem 0.4rem;
        font-size: 0.75rem;
    }

    .dice-btn {
        align-self: flex-end;
    }

    .qs-summary {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 0.45rem;
        font-size: 0.72rem;
        color: #b9c8f0;
    }

    .qs-summary .blocked {
        color: #ffcf85;
    }

    code {
        font-family: ui-monospace, SFMono-Regular, monospace;
        font-size: 0.68rem;
    }

    .upload-error {
        color: #f87171;
    }

    .action-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 6px;
        border: 1px solid rgba(120, 205, 255, 0.35);
        background: rgba(58, 150, 221, 0.22);
        color: #dceeff;
        padding: 0.35rem 0.6rem;
        font-size: 0.74rem;
        cursor: pointer;
        white-space: nowrap;
    }

    .action-btn.secondary {
        border-color: rgba(255, 255, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #e6ecf5;
    }

    .action-btn:disabled,
    .add-btn:disabled,
    .template-tab:disabled {
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
        padding: 0.24rem;
        cursor: pointer;
    }
</style>
