<script lang="ts">
    import type {
        EmgTransformResultMessage,
        EmgTransformSummary,
        TransformCapability,
        DataSchemaDescriptor,
        TransformKind,
    } from "./types";
    import { findCompatibleTransformInputMappingId } from "./schemaDescriptor";
    interface TransformSourceOption {
        streamId: string;
        schemaName: string;
        descriptor?: DataSchemaDescriptor;
    }

    interface CreateEmgTransformInput {
        requestId: string;
        sourceStreamId: string;
        outputIdentifier: string;
        transformKind: TransformKind;
        inputMappingId?: string;
        config: {
            cutoff_hz?: number;
            low_cutoff_hz?: number;
            high_cutoff_hz?: number;
            notch_hz?: number;
            notch_q?: number;
            iir_method?: "butterworth" | "biquad";
            butterworth_order?: number;
            biquad_q?: number;
            harmonic_count?: number;
            window_samples?: number;
            step_samples?: number;
        };
    }

    interface Props {
        emgStreams: TransformSourceOption[];
        createEmgTransform: (payload: CreateEmgTransformInput) => boolean;
        stopEmgTransform: (outputStreamId: string) => boolean;
        lastTransformResult: EmgTransformResultMessage | null;
        transformCapabilities: TransformCapability[];
        emgTransforms: EmgTransformSummary[];
        emgTransformWorkerId: string;
        emgTransformSlotCapacity: number;
        emgTransformActiveCount: number;
        emgTransformAvailableSlotCount: number;
        emgTransformUtilizationRatio: number;
        emgTransformLastHeartbeatUs: number;
        emgTransformWorkerStatus: "idle" | "live" | "stalled";
    }

    let {
        emgStreams,
        createEmgTransform,
        stopEmgTransform,
        lastTransformResult,
        transformCapabilities,
        emgTransforms,
        emgTransformWorkerId,
        emgTransformSlotCapacity,
        emgTransformActiveCount,
        emgTransformAvailableSlotCount,
        emgTransformUtilizationRatio,
        emgTransformLastHeartbeatUs,
        emgTransformWorkerStatus,
    }: Props = $props();

    let selectedStreamId = $state("");
    let transformKind = $state<TransformKind>(
        "rectify",
    );
    let outputIdentifier = $state("");
    let cutoffHz = $state(20);
    let lowCutoffHz = $state(20);
    let highCutoffHz = $state(450);
    let notchHz = $state(60);
    let notchQ = $state(30);
    let iirMethod = $state<"butterworth" | "biquad">("butterworth");
    let butterworthOrder = $state(2);
    let biquadQ = $state(0.7071);
    let harmonicCount = $state(0);
    let windowSamples = $state(32);
    let stepSamples = $state(16);
    let submitMessage = $state<string | null>(null);
    let activeCapability = $derived(
        transformCapabilities.find((capability) => capability.kind === transformKind) ??
            transformCapabilities[0] ??
            null,
    );

    $effect(() => {
        const availableIds = emgStreams.map((stream) => stream.streamId);
        if (availableIds.length === 0) {
            selectedStreamId = "";
            return;
        }
        if (!availableIds.includes(selectedStreamId)) {
            selectedStreamId = availableIds[0];
        }
    });

    $effect(() => {
        if (outputIdentifier !== "" || selectedStreamId === "") {
            return;
        }
        outputIdentifier = `${selectedStreamId}-${defaultOutputSuffix(transformKind)}`;
    });

    $effect(() => {
        if (transformCapabilities.length === 0) {
            return;
        }
        if (!transformCapabilities.some((capability) => capability.kind === transformKind)) {
            transformKind = transformCapabilities[0].kind;
        }
    });

    $effect(() => {
        const capability =
            transformCapabilities.find((item) => item.kind === transformKind) ?? null;
        if (!capability) {
            return;
        }
        const cutoffField = capability.config_fields.find(
            (field) => field.id === "cutoff_hz",
        );
        const lowCutoffField = capability.config_fields.find(
            (field) => field.id === "low_cutoff_hz",
        );
        const highCutoffField = capability.config_fields.find(
            (field) => field.id === "high_cutoff_hz",
        );
        const notchField = capability.config_fields.find(
            (field) => field.id === "notch_hz",
        );
        const notchQField = capability.config_fields.find(
            (field) => field.id === "notch_q",
        );
        const iirMethodField = capability.config_fields.find(
            (field) => field.id === "iir_method",
        );
        const butterworthOrderField = capability.config_fields.find(
            (field) => field.id === "butterworth_order",
        );
        const biquadQField = capability.config_fields.find(
            (field) => field.id === "biquad_q",
        );
        const harmonicCountField = capability.config_fields.find(
            (field) => field.id === "harmonic_count",
        );
        const windowSamplesField = capability.config_fields.find(
            (field) => field.id === "window_samples",
        );
        const stepSamplesField = capability.config_fields.find(
            (field) => field.id === "step_samples",
        );
        if (cutoffField?.default_value !== undefined) {
            cutoffHz = cutoffField.default_value;
        }
        if (lowCutoffField?.default_value !== undefined) {
            lowCutoffHz = lowCutoffField.default_value;
        }
        if (highCutoffField?.default_value !== undefined) {
            highCutoffHz = highCutoffField.default_value;
        }
        if (notchField?.default_value !== undefined) {
            notchHz = notchField.default_value;
        }
        if (notchQField?.default_value !== undefined) {
            notchQ = notchQField.default_value;
        }
        if (
            iirMethodField?.default_option === "butterworth" ||
            iirMethodField?.default_option === "biquad"
        ) {
            iirMethod = iirMethodField.default_option;
        }
        if (butterworthOrderField?.default_value !== undefined) {
            butterworthOrder = butterworthOrderField.default_value;
        }
        if (biquadQField?.default_value !== undefined) {
            biquadQ = biquadQField.default_value;
        }
        if (harmonicCountField?.default_value !== undefined) {
            harmonicCount = harmonicCountField.default_value;
        }
        if (windowSamplesField?.default_value !== undefined) {
            windowSamples = windowSamplesField.default_value;
        }
        if (stepSamplesField?.default_value !== undefined) {
            stepSamples = stepSamplesField.default_value;
        }
    });

    function defaultOutputSuffix(kind: TransformKind): string {
        if (kind === "rectify") {
            return "rect";
        }
        if (kind === "lowpass_envelope") {
            return "env";
        }
        if (kind === "bandpass_iir") {
            return "bp";
        }
        if (kind === "notch_iir") {
            return "notch";
        }
        if (kind === "rms_window") {
            return "rms";
        }
        if (kind === "sliding_window") {
            return "win";
        }
        return "hp";
    }

    function sanitizeIdentifier(value: string): string {
        return value
            .replace(/[^A-Za-z0-9_-]/g, "-")
            .replace(/--+/g, "-")
            .replace(/^-+/, "")
            .slice(0, 64);
    }

    function handleTransformKindChange(kind: TransformKind) {
        transformKind = kind;
        if (selectedStreamId !== "") {
            outputIdentifier = sanitizeIdentifier(
                `${selectedStreamId}-${defaultOutputSuffix(kind)}`,
            );
        }
    }

    function handleCreateTransform() {
        if (selectedStreamId === "") {
            submitMessage = "Choose a compatible source stream first.";
            return;
        }

        const requestId = `emg-transform:${Date.now()}`;
        const sent = createEmgTransform({
            requestId,
            sourceStreamId: selectedStreamId,
            outputIdentifier: sanitizeIdentifier(outputIdentifier),
            transformKind,
            inputMappingId: findCompatibleTransformInputMappingId(
                emgStreams.find((stream) => stream.streamId === selectedStreamId)
                    ?.descriptor,
                activeCapability ?? undefined,
            ),
            config: {
                ...(transformKind === "lowpass_envelope"
                    ? {
                          cutoff_hz: cutoffHz,
                      }
                    : {}),
                ...(transformKind === "bandpass_iir"
                    ? {
                          low_cutoff_hz: lowCutoffHz,
                          high_cutoff_hz: highCutoffHz,
                          iir_method: iirMethod,
                          butterworth_order: butterworthOrder,
                          biquad_q: biquadQ,
                      }
                    : {}),
                ...(transformKind === "notch_iir"
                    ? {
                          notch_hz: notchHz,
                          notch_q: notchQ,
                          harmonic_count: harmonicCount,
                      }
                    : {}),
                ...(transformKind === "rms_window"
                    ? {
                          window_samples: windowSamples,
                      }
                    : {}),
                ...(transformKind === "sliding_window"
                    ? {
                          window_samples: windowSamples,
                          step_samples: stepSamples,
                      }
                    : {}),
                ...(transformKind === "highpass_iir"
                    ? {
                          cutoff_hz: cutoffHz,
                          iir_method: iirMethod,
                          butterworth_order: butterworthOrder,
                          biquad_q: biquadQ,
                      }
                    : {}),
            },
        });
        if (sent) {
            submitMessage = "Creating transform stream...";
        }
    }

    function handleStopTransform(outputStreamId: string) {
        if (stopEmgTransform(outputStreamId)) {
            submitMessage = `Stopping transform ${outputStreamId}...`;
        }
    }

    function formatPercent(value: number): string {
        return `${Math.round(value * 100)}%`;
    }

    function formatLastSeen(timestampUs: number): string {
        if (!timestampUs) {
            return "no frames yet";
        }
        const ageSeconds = Math.max(
            0,
            Math.round(Date.now() / 1000 - timestampUs / 1_000_000),
        );
        if (ageSeconds < 2) {
            return "just now";
        }
        if (ageSeconds < 60) {
            return `${ageSeconds}s ago`;
        }
        const ageMinutes = Math.round(ageSeconds / 60);
        return `${ageMinutes}m ago`;
    }

    function runtimeStatus(
        transform: EmgTransformSummary,
    ): "warming" | "live" | "stalled" {
        if (!transform.last_frame_at_us) {
            return "warming";
        }
        const ageSeconds = Math.max(
            0,
            Math.round(Date.now() / 1000 - transform.last_frame_at_us / 1_000_000),
        );
        return ageSeconds >= 3 ? "stalled" : "live";
    }

    function formatStartedAt(timestampUs: number): string {
        if (!timestampUs) {
            return "-";
        }
        return new Date(timestampUs / 1000).toLocaleTimeString();
    }

    function formatWorkerHeartbeat(timestampUs: number): string {
        if (!timestampUs) {
            return "-";
        }
        return formatLastSeen(timestampUs);
    }
</script>

<section class="transform-panel">
    <div class="panel-head">
        <div>
            <h3>Transforms</h3>
            <p>Create a derived numeric channel stream from a compatible source.</p>
        </div>
        <div class="scheduler-summary">
            <span>{emgTransformWorkerId}</span>
            <strong>{emgTransformActiveCount} / {emgTransformSlotCapacity} slots active</strong>
            <span>{emgTransformAvailableSlotCount} slots available</span>
            <span>Utilization {formatPercent(emgTransformUtilizationRatio)}</span>
            <span class="runtime-pill" data-status={emgTransformWorkerStatus}>
                {emgTransformWorkerStatus}
            </span>
            <span>Heartbeat {formatWorkerHeartbeat(emgTransformLastHeartbeatUs)}</span>
        </div>
    </div>

    {#if transformCapabilities.length === 0}
        <p class="empty-state">
            Transform capabilities are not available yet.
        </p>
    {:else if emgStreams.length === 0}
        <p class="empty-state">
            No compatible source streams are available yet.
        </p>
    {:else}
        <div class="form-grid">
            <label class="field">
                <span>Source stream</span>
                <select bind:value={selectedStreamId}>
                    {#each emgStreams as stream}
                        <option value={stream.streamId}>
                            Stream {stream.streamId} · {stream.schemaName}
                        </option>
                    {/each}
                </select>
            </label>

            <label class="field">
                <span>Transform</span>
                <select
                    bind:value={transformKind}
                    onchange={(event) =>
                        handleTransformKindChange(
                            event.currentTarget.value as
                                TransformKind,
                        )}
                >
                    {#each transformCapabilities as capability}
                        <option value={capability.kind}>
                            {capability.label}
                        </option>
                    {/each}
                </select>
            </label>

            <label class="field field-wide">
                <span>Output identifier</span>
                <input
                    type="text"
                    bind:value={outputIdentifier}
                    oninput={() =>
                        (outputIdentifier = sanitizeIdentifier(outputIdentifier))}
                    placeholder="source-123-env"
                />
            </label>

            <label class="field">
                <span>Band-pass low (Hz)</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={lowCutoffHz}
                    disabled={transformKind !== "bandpass_iir"}
                />
            </label>

            <label class="field">
                <span>Band-pass high (Hz)</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={highCutoffHz}
                    disabled={transformKind !== "bandpass_iir"}
                />
            </label>

            <label class="field">
                <span>Cutoff (Hz)</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={cutoffHz}
                    disabled={
                        transformKind !== "highpass_iir" &&
                        transformKind !== "lowpass_envelope"
                    }
                />
            </label>

            <label class="field">
                <span>Base notch (Hz)</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={notchHz}
                    disabled={transformKind !== "notch_iir"}
                />
            </label>

            <label class="field">
                <span>Notch Q</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={notchQ}
                    disabled={transformKind !== "notch_iir"}
                />
            </label>

            <label class="field">
                <span>Extra harmonics</span>
                <input
                    type="number"
                    min="0"
                    step="1"
                    bind:value={harmonicCount}
                    disabled={transformKind !== "notch_iir"}
                />
            </label>

            <label class="field">
                <span>Window samples</span>
                <input
                    type="number"
                    min="1"
                    step="1"
                    bind:value={windowSamples}
                    disabled={
                        transformKind !== "rms_window" &&
                        transformKind !== "sliding_window"
                    }
                />
            </label>

            <label class="field">
                <span>Step samples</span>
                <input
                    type="number"
                    min="1"
                    step="1"
                    bind:value={stepSamples}
                    disabled={transformKind !== "sliding_window"}
                />
            </label>

            <label class="field">
                <span>IIR method</span>
                <select
                    bind:value={iirMethod}
                    disabled={
                        transformKind !== "highpass_iir" &&
                        transformKind !== "bandpass_iir"
                    }
                >
                    <option value="butterworth">Butterworth</option>
                    <option value="biquad">Biquad</option>
                </select>
            </label>

            <label class="field">
                <span>Butterworth order</span>
                <input
                    type="number"
                    min="1"
                    max="8"
                    step="1"
                    bind:value={butterworthOrder}
                    disabled={
                        (transformKind !== "highpass_iir" &&
                            transformKind !== "bandpass_iir") ||
                        iirMethod !== "butterworth"
                    }
                />
            </label>

            <label class="field">
                <span>Biquad Q</span>
                <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    bind:value={biquadQ}
                    disabled={
                        (transformKind !== "highpass_iir" &&
                            transformKind !== "bandpass_iir") ||
                        iirMethod !== "biquad"
                    }
                />
            </label>
        </div>

        {#if activeCapability}
            <p class="empty-state">{activeCapability.description}</p>
        {/if}

        <div class="actions">
            <button class="create-btn" onclick={handleCreateTransform}>
                Create transform stream
            </button>
            {#if submitMessage}
                <span class="inline-status">{submitMessage}</span>
            {/if}
        </div>

        {#if lastTransformResult}
            <div class="result-card">
                <div class="result-row">
                    <span class="result-label">Output stream</span>
                    <code>{lastTransformResult.output_stream_id}</code>
                </div>
                <div class="result-row">
                    <span class="result-label">Worker slot</span>
                    <code>{lastTransformResult.thread_slot_id}</code>
                </div>
                <div class="result-row">
                    <span class="result-label">Topic</span>
                    <code>{lastTransformResult.topic}</code>
                </div>
                <div class="result-row">
                    <span class="result-label">Status</span>
                    <span>
                        {lastTransformResult.already_exists
                            ? "Already running"
                            : "Created"}
                    </span>
                </div>
            </div>
        {/if}

        <div class="active-transforms">
            <div class="active-head">
                <h4>Active transforms</h4>
                <span>{emgTransforms.length} running</span>
            </div>
            {#if emgTransforms.length === 0}
                <p class="empty-state">No transform workers are active.</p>
            {:else}
                <div class="transform-list">
                    {#each emgTransforms as transform}
                        <div class="transform-row">
                            <div>
                                <div class="transform-title">
                                    <strong>{transform.output_identifier}</strong>
                                    <code>{transform.thread_slot_id}</code>
                                    <span
                                        class="runtime-pill"
                                        data-status={runtimeStatus(transform)}
                                    >
                                        {runtimeStatus(transform)}
                                    </span>
                                </div>
                                <p>
                                    Source {transform.source_stream_id} -> output {transform.output_stream_id}
                                </p>
                                <p>{transform.transform_kind} · {transform.topic}</p>
                                <p>
                                    Frames {transform.frames_processed} · started {formatStartedAt(transform.started_at_us)} · last frame {formatLastSeen(transform.last_frame_at_us)}
                                </p>
                            </div>
                            <button
                                class="stop-btn"
                                onclick={() =>
                                    handleStopTransform(transform.output_stream_id)}
                            >
                                Stop
                            </button>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
</section>

<style>
    .transform-panel {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        padding: 1.25rem;
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }

    .panel-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: start;
    }

    .panel-head h3 {
        margin: 0 0 0.35rem;
        font-size: 1.1rem;
        color: #1a1a2e;
    }

    .panel-head p,
    .empty-state {
        margin: 0;
        color: #4b5563;
    }

    .scheduler-summary {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        align-items: end;
        font-size: 0.85rem;
        color: #4b5563;
    }

    .scheduler-summary strong {
        color: #111827;
        font-size: 0.95rem;
    }

    .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.9rem;
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }

    .field-wide {
        grid-column: 1 / -1;
    }

    .field span {
        font-size: 0.9rem;
        font-weight: 600;
        color: #374151;
    }

    .field input,
    .field select {
        min-height: 40px;
        padding: 0.65rem 0.75rem;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        background: #fff;
        color: #111827;
    }

    .field input:disabled,
    .field select:disabled {
        background: #f3f4f6;
        color: #6b7280;
    }

    .actions {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .create-btn {
        min-height: 40px;
        padding: 0.7rem 1rem;
        border: none;
        border-radius: 8px;
        background: #2563eb;
        color: white;
        font-weight: 600;
        cursor: pointer;
    }

    .create-btn:hover {
        background: #1d4ed8;
    }

    .inline-status {
        color: #4b5563;
        font-size: 0.95rem;
    }

    .result-card {
        display: grid;
        gap: 0.6rem;
        padding: 0.9rem 1rem;
        border-radius: 8px;
        background: #f8fafc;
        border: 1px solid #dbe4f0;
    }

    .result-row {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        align-items: baseline;
    }

    .result-label {
        min-width: 110px;
        font-weight: 600;
        color: #374151;
    }

    .active-transforms {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        border-top: 1px solid #e5e7eb;
        padding-top: 1rem;
    }

    .active-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
    }

    .active-head h4 {
        margin: 0;
        font-size: 1rem;
        color: #111827;
    }

    .active-head span {
        color: #4b5563;
        font-size: 0.9rem;
    }

    .transform-list {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .transform-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: start;
        padding: 0.9rem 1rem;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        background: #fcfcfd;
    }

    .transform-row p {
        margin: 0.25rem 0 0;
        color: #4b5563;
        font-size: 0.9rem;
        word-break: break-word;
    }

    .transform-title {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        align-items: center;
    }

    .transform-title code {
        font-size: 0.8rem;
        padding: 0.15rem 0.4rem;
        border-radius: 999px;
        background: #ecfdf3;
        color: #047857;
    }

    .runtime-pill {
        font-size: 0.78rem;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        text-transform: uppercase;
        background: #f3f4f6;
        color: #4b5563;
    }

    .runtime-pill[data-status="live"] {
        background: #dcfce7;
        color: #166534;
    }

    .runtime-pill[data-status="warming"] {
        background: #dbeafe;
        color: #1d4ed8;
    }

    .runtime-pill[data-status="stalled"] {
        background: #fef3c7;
        color: #b45309;
    }

    .stop-btn {
        min-height: 40px;
        padding: 0.65rem 0.9rem;
        border-radius: 8px;
        border: 1px solid #fecdd3;
        background: #fff1f2;
        color: #b42318;
        cursor: pointer;
    }

    @media (max-width: 720px) {
        .panel-head,
        .transform-row,
        .active-head {
            flex-direction: column;
            align-items: stretch;
        }

        .scheduler-summary {
            align-items: start;
        }
    }
</style>
