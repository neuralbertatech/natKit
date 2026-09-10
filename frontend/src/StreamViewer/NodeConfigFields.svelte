<script lang="ts">
    // Shared, catalog-driven config-field renderer (Phase 1 of the
    // visual-programming rework). Renders a node/transform's typed config_fields
    // (number | enum | string) into a form, writing changes back through
    // `onChange`. Both the stream-graph node inspector and the legacy
    // StreamViewer transform form render from this — neither hardcodes fields
    // per transform kind, so a new transform advertised by the backend catalog
    // is configurable with no frontend change.
    import type { TransformCapabilityConfigField } from "./types";
    import { configOptionLabel } from "../VisualProgramming/streamGraph";

    interface Props {
        fields: TransformCapabilityConfigField[];
        // Values may be absent: a node dropped on the canvas has no config yet
        // and each field falls back to its own advertised default.
        config: Record<string, number | string | boolean | undefined>;
        onChange: (
            field: TransformCapabilityConfigField,
            rawValue: string,
        ) => void;
        disabled?: boolean;
    }

    let { fields, config, onChange, disabled = false }: Props = $props();
</script>

<div class="config-grid">
    {#each fields as field}
        <label>
            <span>{field.label}</span>
            {#if field.type === "enum"}
                <select
                    {disabled}
                    value={String(
                        config[field.id] ?? field.default_option ?? "",
                    )}
                    onchange={(event) =>
                        onChange(
                            field,
                            (event.currentTarget as HTMLSelectElement).value,
                        )}
                >
                    {#each field.options ?? [] as option}
                        <!-- The wire value stays terse because the backend
                             parses it; the label says what the option DOES,
                             which matters most where picking wrong is silently
                             wrong rather than an error. -->
                        <option value={option}
                            >{configOptionLabel(field, option)}</option
                        >
                    {/each}
                </select>
            {:else if field.type === "string"}
                <input
                    type="text"
                    {disabled}
                    value={String(config[field.id] ?? "")}
                    oninput={(event) =>
                        onChange(
                            field,
                            (event.currentTarget as HTMLInputElement).value,
                        )}
                />
            {:else}
                <input
                    type="number"
                    {disabled}
                    min={field.min}
                    step={field.step ?? 1}
                    value={String(
                        config[field.id] ?? field.default_value ?? "",
                    )}
                    oninput={(event) =>
                        onChange(
                            field,
                            (event.currentTarget as HTMLInputElement).value,
                        )}
                />
            {/if}
        </label>
    {/each}
</div>

<style>
    .config-grid {
        display: grid;
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
    select {
        background: rgba(7, 11, 23, 0.96);
        border: 1px solid rgba(114, 142, 255, 0.14);
        border-radius: 6px;
        color: inherit;
        padding: 0.62rem 0.72rem;
    }

    input:disabled,
    select:disabled {
        opacity: 0.5;
    }
</style>
