<script lang="ts">
    // Renders whichever in-app dialog is pending. Mounted once by the editor.
    //
    // Deliberately styled like the rest of the page (dark panel, blue accents,
    // Esc/backdrop to dismiss) — the whole reason these exist is that the native
    // dialogs looked nothing like the app and could not show anything richer
    // than a string.
    import { AlertTriangle, Check, X } from "@lucide/svelte";
    import {
        dialogs,
        filterSuggestions,
        namesCollide,
        settleDialog,
    } from "./dialogs.svelte";

    const current = $derived(dialogs.current);

    // Name-entry state. Keyed on the request id so a queued second dialog gets a
    // fresh field instead of inheriting what was typed into the first.
    let typedName = $state("");
    let seededForId = $state<number | null>(null);

    $effect(() => {
        const request = current;
        if (request && request.kind === "name" && seededForId !== request.id) {
            typedName = request.initial ?? "";
            seededForId = request.id;
        }
        if (!request) {
            seededForId = null;
        }
    });

    const suggestions = $derived.by(() => {
        if (!current || current.kind !== "name") return [];
        return filterSuggestions(current.existing ?? [], typedName);
    });

    const collision = $derived.by(() => {
        if (!current || current.kind !== "name") return null;
        return (
            (current.existing ?? []).find((entry) =>
                namesCollide(entry.name, typedName),
            ) ?? null
        );
    });

    const canSubmitName = $derived(typedName.trim().length > 0);

    function cancel() {
        if (!current) return;
        // A cancelled alert is still just "acknowledged".
        settleDialog(current, current.kind === "confirm" ? false : null);
    }

    function accept() {
        if (!current) return;
        if (current.kind === "name") {
            if (!canSubmitName) return;
            settleDialog(current, typedName.trim());
            return;
        }
        settleDialog(current, true);
    }

    /**
     * Autofocus so the dialog is keyboard-usable the moment it opens. Takes a
     * flag because exactly one element should win: the text field on a name
     * dialog, the primary button otherwise.
     */
    function focusOnMount(node: HTMLElement, shouldFocus: boolean) {
        if (!shouldFocus) return;
        // Give the browser a frame; focusing during insertion is unreliable.
        requestAnimationFrame(() => node.focus());
    }

    function paragraphs(body: string | undefined): string[] {
        if (!body) return [];
        return body.split(/\n{2,}/).map((part) => part.trim()).filter(Boolean);
    }
</script>

<svelte:window
    onkeydown={(event) => {
        if (!current) return;
        if (event.key === "Escape") {
            event.stopPropagation();
            cancel();
        }
    }}
/>

{#if current}
    <div
        class="dialog-backdrop"
        role="presentation"
        onclick={(event) => {
            if (event.target === event.currentTarget) cancel();
        }}
    >
        <div
            class="dialog-panel"
            class:danger={current.kind !== "alert" && current.danger === true}
            role="dialog"
            aria-modal="true"
            aria-label={current.title}
        >
            <div class="dialog-head">
                {#if current.kind === "alert" || (current.kind === "confirm" && current.danger)}
                    <span
                        class="dialog-icon"
                        class:warn={current.kind === "alert"}
                        class:danger={current.kind !== "alert" && current.danger}
                    >
                        <AlertTriangle size={15} />
                    </span>
                {/if}
                <h3>{current.title}</h3>
                <button
                    type="button"
                    class="icon-btn dialog-close"
                    title="Close"
                    onclick={cancel}
                >
                    <X size={14} />
                </button>
            </div>

            {#each paragraphs(current.body) as paragraph}
                <p class="dialog-body">{paragraph}</p>
            {/each}

            {#if current.points && current.points.length > 0}
                <ul class="dialog-points">
                    {#each current.points as point}
                        <li>{point}</li>
                    {/each}
                </ul>
            {/if}

            {#if current.kind === "name"}
                <label class="dialog-field">
                    <span>{current.label}</span>
                    <input
                        use:focusOnMount={true}
                        value={typedName}
                        placeholder={current.placeholder ?? ""}
                        oninput={(event) =>
                            (typedName = (
                                event.currentTarget as HTMLInputElement
                            ).value)}
                        onkeydown={(event) => {
                            if (event.key === "Enter") {
                                event.preventDefault();
                                accept();
                            }
                        }}
                    />
                </label>

                {#if collision && current.existingMeansReuse}
                    <!-- Picking an existing entry is the intended action here, so
                         this confirms the match instead of warning about it. -->
                    <p class="dialog-reuse">
                        <span class="collision-icon">
                            <Check size={12} />
                        </span>
                        <span>
                            Matches the existing {current.noun ?? "record"}
                            <strong>{collision.name}</strong
                            >{collision.hint
                                ? ` (${collision.hint})`
                                : ""}.
                        </span>
                    </p>
                {:else if collision}
                    <!-- The text lives in one span: this is a flex row, so bare
                         text nodes would each become their own flex item and
                         stack into columns. -->
                    <p class="dialog-collision">
                        <span class="collision-icon">
                            <AlertTriangle size={12} />
                        </span>
                        <span>
                            Another {current.noun ?? "record"} is already named
                            <strong>{collision.name}</strong
                            >{collision.hint ? ` (${collision.hint})` : ""}. You
                            can still use this name, but they will be hard to
                            tell apart.
                        </span>
                    </p>
                {/if}

                {#if (current.existing ?? []).length > 0}
                    <div class="dialog-existing">
                        <p class="dialog-existing-head">
                            {typedName.trim()
                                ? `Existing ${current.noun ?? "record"}s matching “${typedName.trim()}”`
                                : `Existing ${current.noun ?? "record"}s`}
                            <span class="dialog-count">
                                {suggestions.length} of {(current.existing ?? [])
                                    .length}
                            </span>
                        </p>
                        {#if suggestions.length === 0}
                            <p class="dialog-none">
                                No overlap — that name is free.
                            </p>
                        {:else}
                            <ul class="dialog-suggestions">
                                {#each suggestions.slice(0, 8) as entry}
                                    <li
                                        class:exact={namesCollide(
                                            entry.name,
                                            typedName,
                                        )}
                                    >
                                        <span class="suggestion-name"
                                            >{entry.name}</span
                                        >
                                        {#if entry.hint}
                                            <span class="suggestion-hint"
                                                >{entry.hint}</span
                                            >
                                        {/if}
                                    </li>
                                {/each}
                                {#if suggestions.length > 8}
                                    <li class="suggestion-more">
                                        + {suggestions.length - 8} more
                                    </li>
                                {/if}
                            </ul>
                        {/if}
                    </div>
                {/if}
            {/if}

            <div class="dialog-actions">
                {#if current.kind !== "alert"}
                    <button type="button" class="btn secondary" onclick={cancel}>
                        {current.cancelLabel ?? "Cancel"}
                    </button>
                {/if}
                <button
                    type="button"
                    class="btn primary"
                    class:danger={current.kind !== "alert" &&
                        current.danger === true}
                    disabled={current.kind === "name" && !canSubmitName}
                    use:focusOnMount={current.kind !== "name"}
                    onclick={accept}
                >
                    {#if current.kind !== "name"}
                        <Check size={14} />
                    {/if}
                    {current.confirmLabel ??
                        (current.kind === "alert" ? "OK" : "Continue")}
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .dialog-backdrop {
        position: fixed;
        inset: 0;
        /* Above the designer overlay (60) and the composite internals. */
        z-index: 80;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        background: rgba(3, 6, 14, 0.66);
        color: #d6def4;
    }

    .dialog-panel {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
        width: min(92vw, 30rem);
        max-height: 82vh;
        overflow-y: auto;
        padding: 0.9rem 1rem 0.85rem;
        border-radius: 10px;
        background: rgba(8, 13, 26, 0.99);
        border: 1px solid rgba(110, 138, 255, 0.26);
        box-shadow: 0 28px 80px rgba(0, 0, 0, 0.55);
    }

    .dialog-panel.danger {
        border-color: rgba(248, 113, 113, 0.4);
    }

    .dialog-head {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    .dialog-head h3 {
        margin: 0;
        font-size: 0.92rem;
        line-height: 1.3;
        flex: 1;
    }

    .dialog-icon {
        display: inline-flex;
        color: #fbbf24;
    }

    .dialog-icon.danger {
        color: #f87171;
    }

    .dialog-close {
        flex: none;
    }

    .dialog-body {
        margin: 0;
        font-size: 0.78rem;
        line-height: 1.5;
        color: rgba(230, 236, 245, 0.78);
        white-space: pre-line;
    }

    /* No flex here: it strips the list-item display off the <li>s, so the
       bullet markers vanish. Same trap as .dialog-collision. */
    .dialog-points {
        margin: 0;
        padding-left: 1.15rem;
        list-style: disc;
        font-size: 0.75rem;
        line-height: 1.45;
        color: rgba(230, 236, 245, 0.72);
    }

    .dialog-points li + li {
        margin-top: 0.2rem;
    }

    .dialog-points li::marker {
        color: rgba(230, 236, 245, 0.4);
    }

    .dialog-field {
        display: flex;
        flex-direction: column;
        gap: 0.18rem;
        margin-top: 0.15rem;
    }

    .dialog-field > span {
        font-size: 0.62rem;
        letter-spacing: 0.02em;
        color: #7f91c8;
    }

    input {
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.16);
        background: rgba(12, 18, 28, 0.8);
        color: #e6ecf5;
        padding: 0.4rem 0.5rem;
        font-size: 0.82rem;
        width: 100%;
    }

    input:focus {
        outline: none;
        border-color: #4f7ef7;
    }

    .dialog-collision {
        display: flex;
        align-items: flex-start;
        gap: 0.3rem;
        margin: 0;
        font-size: 0.72rem;
        line-height: 1.45;
        color: #fbd88a;
    }

    /* Same shape as .dialog-collision, affirmative colour: a match is the goal
       when the dialog is a picker, so it must not read as the amber warning. */
    .dialog-reuse {
        display: flex;
        align-items: flex-start;
        gap: 0.3rem;
        margin: 0;
        font-size: 0.72rem;
        line-height: 1.45;
        color: #86e3a8;
    }

    .collision-icon {
        display: inline-flex;
        flex: none;
        padding-top: 0.12rem;
    }

    .dialog-existing {
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 0.45rem;
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .dialog-existing-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem;
        margin: 0;
        font-size: 0.65rem;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: rgba(230, 236, 245, 0.5);
    }

    .dialog-count {
        font-family: ui-monospace, SFMono-Regular, monospace;
        text-transform: none;
        letter-spacing: 0;
    }

    .dialog-none {
        margin: 0;
        font-size: 0.72rem;
        color: #9ce6b4;
    }

    .dialog-suggestions {
        margin: 0;
        padding: 0;
        list-style: none;
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        max-height: 9rem;
        overflow-y: auto;
    }

    .dialog-suggestions li {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem;
        font-size: 0.73rem;
        padding: 0.15rem 0.35rem;
        border-radius: 4px;
        background: rgba(12, 18, 28, 0.6);
        color: #b9c8f0;
    }

    .dialog-suggestions li.exact {
        background: rgba(251, 191, 36, 0.14);
        color: #fbd88a;
    }

    .suggestion-hint {
        font-size: 0.66rem;
        color: rgba(230, 236, 245, 0.45);
        overflow-wrap: anywhere;
        text-align: right;
    }

    .suggestion-more {
        background: none !important;
        color: rgba(230, 236, 245, 0.45) !important;
        font-size: 0.68rem;
    }

    .dialog-actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.4rem;
        margin-top: 0.3rem;
    }

    .btn {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
        font-size: 0.78rem;
        cursor: pointer;
        border: 1px solid transparent;
    }

    .btn.primary {
        border-color: rgba(120, 205, 255, 0.4);
        background: rgba(58, 150, 221, 0.28);
        color: #dceeff;
        font-weight: 600;
    }

    .btn.primary.danger {
        border-color: rgba(248, 113, 113, 0.45);
        background: rgba(153, 27, 27, 0.5);
        color: #fee2e2;
    }

    .btn.secondary {
        border-color: rgba(255, 255, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #e6ecf5;
    }

    .btn:disabled {
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
        padding: 0.22rem;
        cursor: pointer;
    }
</style>
