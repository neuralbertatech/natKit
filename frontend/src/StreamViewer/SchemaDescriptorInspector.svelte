<script lang="ts">
    import {
        formatSchemaValue,
        getDescriptorLeafOptions,
        getValueAtSchemaPath,
        type DescriptorLeafOption,
    } from "./schemaDescriptor";
    import type { DataSchemaDescriptor } from "./types";

    interface Props {
        descriptor: DataSchemaDescriptor;
        recordValue?: unknown;
    }

    let { descriptor, recordValue = undefined }: Props = $props();

    let leafOptions = $derived(
        getDescriptorLeafOptions(descriptor, recordValue).filter(
            (option, index, allOptions) =>
                allOptions.findIndex(
                    (candidate) => candidate.path === option.path,
                ) === index,
        ),
    );

    let selectedPath = $state("");

    $effect(() => {
        if (leafOptions.length === 0) {
            selectedPath = "";
            return;
        }
        if (!leafOptions.some((option) => option.path === selectedPath)) {
            selectedPath = leafOptions[0].path;
        }
    });

    function getOptionValue(option: DescriptorLeafOption): string {
        return formatSchemaValue(getValueAtSchemaPath(recordValue, option.path));
    }
</script>

<section class="descriptor-panel">
    <div class="descriptor-head">
        <div>
            <h4>Schema Inspector</h4>
            <p>
                {descriptor.schema_name} · descriptor v{descriptor.descriptor_version}
            </p>
        </div>
        <span class="descriptor-count">{leafOptions.length} fields</span>
    </div>

    {#if leafOptions.length > 0}
        <label class="picker-row">
            <span class="picker-label">Field</span>
            <select bind:value={selectedPath}>
                {#each leafOptions as option}
                    <option value={option.path}>{option.label}</option>
                {/each}
            </select>
        </label>

        {#if selectedPath}
            {@const selectedField =
                leafOptions.find((option) => option.path === selectedPath)}
            <div class="selected-field">
                <div class="selected-meta">
                    <span class="selected-path">{selectedPath}</span>
                    {#if selectedField?.unit}
                        <span class="selected-unit">{selectedField.unit}</span>
                    {/if}
                </div>
                <div class="selected-value">
                    {formatSchemaValue(
                        getValueAtSchemaPath(recordValue, selectedPath),
                    )}
                </div>
                {#if selectedField?.description}
                    <p class="selected-description">
                        {selectedField.description}
                    </p>
                {/if}
            </div>
        {/if}

        <div class="field-list">
            {#each leafOptions as option}
                <button
                    type="button"
                    class:selected={selectedPath === option.path}
                    onclick={() => {
                        selectedPath = option.path;
                    }}
                >
                    <span class="field-label">{option.label}</span>
                    <span class="field-value">{getOptionValue(option)}</span>
                </button>
            {/each}
        </div>
    {:else}
        <p class="empty-state">No descriptor fields available.</p>
    {/if}
</section>

<style>
    .descriptor-panel {
        display: grid;
        gap: 0.75rem;
        padding: 0.9rem;
        border: 1px solid #dbe3ee;
        border-radius: 8px;
        background: #f8fbff;
    }

    .descriptor-head {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        align-items: flex-start;
    }

    .descriptor-head h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #0f172a;
    }

    .descriptor-head p {
        margin: 0.2rem 0 0;
        font-size: 0.78rem;
        color: #475569;
    }

    .descriptor-count {
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        background: #dbeafe;
        color: #1d4ed8;
        font-size: 0.72rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .picker-row {
        display: grid;
        gap: 0.35rem;
    }

    .picker-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
    }

    .picker-row select {
        width: 100%;
        min-height: 2.25rem;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        background: #fff;
        color: #0f172a;
        padding: 0.45rem 0.6rem;
    }

    .selected-field {
        display: grid;
        gap: 0.35rem;
        padding: 0.75rem;
        border-radius: 6px;
        background: #fff;
        border: 1px solid #dbe3ee;
    }

    .selected-meta {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-wrap: wrap;
    }

    .selected-path,
    .field-value {
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .selected-path {
        font-size: 0.78rem;
        color: #475569;
    }

    .selected-unit {
        font-size: 0.72rem;
        color: #0f766e;
        font-weight: 600;
        text-transform: uppercase;
    }

    .selected-value {
        font-size: 1rem;
        font-weight: 600;
        color: #0f172a;
        word-break: break-word;
    }

    .selected-description {
        margin: 0;
        font-size: 0.8rem;
        color: #475569;
    }

    .field-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.5rem;
    }

    .field-list button {
        display: grid;
        gap: 0.2rem;
        padding: 0.65rem 0.75rem;
        border: 1px solid #dbe3ee;
        border-radius: 6px;
        background: #fff;
        color: #0f172a;
        text-align: left;
        cursor: pointer;
    }

    .field-list button.selected {
        border-color: #3b82f6;
        box-shadow: inset 0 0 0 1px #3b82f6;
        background: #eff6ff;
    }

    .field-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: #334155;
    }

    .field-value {
        font-size: 0.78rem;
        color: #0f172a;
        word-break: break-word;
    }

    .empty-state {
        margin: 0;
        color: #64748b;
        font-size: 0.85rem;
    }
</style>
