<script lang="ts">
    import { onDestroy } from "svelte";
    import type { BufferedEmgSample, PublishResultMessage } from "./types";
    import {
        EMG_GESTURE_OPTIONS,
        activeCueAtElapsedMs,
        buildCueSchedule,
        buildCueMarkerPayloads,
        buildDefaultSessionId,
        buildSessionLifecycleMarkerPayload,
        buildSessionMetadataRecordPayload,
        formatDurationMs,
        nextCueAfterElapsedMs,
        scheduleDurationMs,
        type EmgRecordedFrame,
        type EmgStreamOption,
        type SessionPublishBundleInput,
    } from "./experiment";

    interface Props {
        emgStreams: EmgStreamOption[];
        emgBuffers: Map<string, BufferedEmgSample[]>;
        ensureStreamSubscribed: (streamId: string) => void;
        publishSessionBundle: (payload: SessionPublishBundleInput) => boolean;
        lastPublishResult: PublishResultMessage | null;
    }

    type RunState = "idle" | "running" | "completed" | "aborted";

    let {
        emgStreams,
        emgBuffers,
        ensureStreamSubscribed,
        publishSessionBundle,
        lastPublishResult,
    }: Props = $props();

    let selectedStreamId = $state("");
    let sessionId = $state(buildDefaultSessionId());
    let subject = $state("");
    let arm = $state("right");
    let notes = $state("");
    let selectedGestures = $state<string[]>([...EMG_GESTURE_OPTIONS]);
    let repetitions = $state(3);
    let holdS = $state(3);
    let restS = $state(2);
    let leadInS = $state(3);
    let tailRestS = $state(2);
    let seed = $state(Math.floor(Date.now() % 100000));

    let runState = $state<RunState>("idle");
    let elapsedMs = $state(0);
    let sessionStartedAtEpochMs = $state<number | null>(null);
    let sessionCompletedAtEpochMs = $state<number | null>(null);
    let frameCount = $state(0);
    let sampleCount = $state(0);
    let gestureSummaryMap = $state<
        Map<string, { frames: number; samples: number; phase: string | null }>
    >(new Map());
    let lastProcessedFrameKey = $state<string | null>(null);

    let sessionStartedAtPerfMs: number | null = null;
    let animationFrameId: number | null = null;
    let recordedFrames: EmgRecordedFrame[] = [];
    let lastPublishRequestId = $state<string | null>(null);
    let publishState = $state<"idle" | "pending" | "sent" | "error">("idle");
    let publishMessage = $state<string | null>(null);

    let cueSchedule = $derived(
        buildCueSchedule({
            gestures: selectedGestures,
            repetitions,
            holdS,
            restS,
            leadInS,
            tailRestS,
            seed,
        }),
    );
    let totalDurationMs = $derived(scheduleDurationMs(cueSchedule));
    let selectedStream = $derived(
        emgStreams.find((stream) => stream.streamId === selectedStreamId) ?? null,
    );
    let selectedFrames = $derived(
        selectedStreamId ? (emgBuffers.get(selectedStreamId) ?? []) : [],
    );
    let currentCue = $derived(
        runState === "running"
            ? activeCueAtElapsedMs(cueSchedule, elapsedMs)
            : null,
    );
    let nextCue = $derived(nextCueAfterElapsedMs(cueSchedule, elapsedMs));
    let progressPct = $derived(
        totalDurationMs > 0
            ? Math.min(100, (elapsedMs / totalDurationMs) * 100)
            : 0,
    );
    let canStart = $derived(
        runState !== "running" &&
            selectedStreamId !== "" &&
            cueSchedule.length > 0,
    );
    let gestureSummary: {
        gesture: string;
        frames: number;
        samples: number;
        phase: string | null;
    }[] = $derived.by(() => {
        return Array.from(gestureSummaryMap.entries())
            .map(([gesture, value]) => ({
                gesture,
                frames: value.frames,
                samples: value.samples,
                phase: value.phase,
            }))
            .sort((left, right) => left.gesture.localeCompare(right.gesture));
    });

    $effect(() => {
        const availableIds = emgStreams.map((stream) => stream.streamId);
        if (availableIds.length === 0) {
            if (runState !== "running") {
                selectedStreamId = "";
            }
            return;
        }
        if (!availableIds.includes(selectedStreamId)) {
            selectedStreamId =
                emgStreams.find((stream) => stream.subscribed)?.streamId ??
                availableIds[0];
        }
    });

    $effect(() => {
        if (
            runState !== "running" ||
            selectedStreamId === "" ||
            sessionStartedAtEpochMs === null
        ) {
            return;
        }

        const unseenFrames = framesAfterKey(selectedFrames, lastProcessedFrameKey);
        if (unseenFrames.length === 0) {
            return;
        }

        const nextSummary = new Map(gestureSummaryMap);

        for (const frame of unseenFrames) {
            const key = buildFrameKey(frame);
            const frameElapsedMs = Math.max(
                0,
                frame.received_at_ms - sessionStartedAtEpochMs,
            );
            const cue = activeCueAtElapsedMs(cueSchedule, frameElapsedMs);
            const recordedFrame: EmgRecordedFrame = {
                stream_id: selectedStreamId,
                received_at_ms: frame.received_at_ms,
                received_at_utc: new Date(frame.received_at_ms).toISOString(),
                elapsed_ms: frameElapsedMs,
                cue_id: cue?.cue_id ?? null,
                cue_phase: cue?.phase ?? null,
                cue_gesture: cue?.gesture ?? null,
                cue_prompt: cue?.prompt ?? null,
                frame,
            };
            recordedFrames.push(recordedFrame);

            const summaryKey = recordedFrame.cue_gesture ?? "unlabeled";
            const previousSummary = nextSummary.get(summaryKey) ?? {
                frames: 0,
                samples: 0,
                phase: recordedFrame.cue_phase,
            };
            nextSummary.set(summaryKey, {
                frames: previousSummary.frames + 1,
                samples:
                    previousSummary.samples + recordedFrame.frame.samples_per_channel,
                phase: previousSummary.phase ?? recordedFrame.cue_phase,
            });
            frameCount += 1;
            sampleCount += recordedFrame.frame.samples_per_channel;
            lastProcessedFrameKey = key;
        }

        gestureSummaryMap = nextSummary;
    });

    $effect(() => {
        if (
            lastPublishResult === null ||
            lastPublishRequestId === null ||
            lastPublishResult.request_id !== lastPublishRequestId ||
            lastPublishResult.session_id !== sessionId
        ) {
            return;
        }

        publishState = "sent";
        publishMessage = `Kafka publish confirmed: ${lastPublishResult.published_meta_records} meta, ${lastPublishResult.published_marker_events} markers.`;
    });

    onDestroy(() => {
        stopTimer();
    });

    function buildFrameKey(frame: BufferedEmgSample): string {
        return `${frame.seq_no}:${frame.device_ts_us}:${frame.received_at_ms}`;
    }

    function framesAfterKey(
        frames: BufferedEmgSample[],
        lastKey: string | null,
    ): BufferedEmgSample[] {
        if (frames.length === 0) {
            return [];
        }
        if (lastKey === null) {
            return frames;
        }
        const lastIndex = frames.findIndex(
            (frame) => buildFrameKey(frame) === lastKey,
        );
        if (lastIndex === -1) {
            const tail = frames.at(-1);
            if (tail && buildFrameKey(tail) === lastKey) {
                return [];
            }
            return frames;
        }
        return frames.slice(lastIndex + 1);
    }

    function stopTimer() {
        if (animationFrameId !== null) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
    }

    function buildCurrentDeviceContext() {
        const deviceId =
            selectedStream?.latestSample?.device_id ??
            recordedFrames[0]?.frame.device_id ??
            null;
        return {
            deviceId,
            deviceIds: deviceId ? [deviceId] : [],
            tags: [arm, runState].filter(Boolean),
        };
    }

    function buildSessionMetadataRecordForTimes(
        createdAtUs: number,
        updatedAtUs: number,
    ) {
        const { deviceIds, tags } = buildCurrentDeviceContext();
        return buildSessionMetadataRecordPayload({
            sessionId,
            purpose: "training",
            participantId: subject,
            protocolId: "emg-gesture-cues-v1",
            deviceIds,
            tags,
            notes,
            createdAtUs,
            updatedAtUs,
        });
    }

    function buildPublishRequestId(kind: string): string {
        return `${sessionId}:${kind}:${Date.now()}`;
    }

    function sendSessionBundleToKafka(payload: SessionPublishBundleInput): boolean {
        lastPublishRequestId = payload.requestId;
        publishState = "pending";
        publishMessage = "Publishing session metadata and markers to Kafka...";
        const sent = publishSessionBundle(payload);
        if (!sent) {
            publishState = "error";
            publishMessage = "Kafka publish failed: backend WebSocket is not connected.";
            return false;
        }
        return true;
    }

    function publishSessionStart(createdAtUs: number) {
        const { deviceIds, tags } = buildCurrentDeviceContext();
        sendSessionBundleToKafka({
            requestId: buildPublishRequestId("start"),
            sessionId,
            metaRecords: [
                buildSessionMetadataRecordForTimes(createdAtUs, createdAtUs),
            ],
            markerEvents: [
                buildSessionLifecycleMarkerPayload({
                    sessionId,
                    purpose: "training",
                    participantId: subject,
                    protocolId: "emg-gesture-cues-v1",
                    deviceIds,
                    tags,
                    notes,
                    event: "start",
                    emittedAtUs: createdAtUs,
                }),
            ],
        });
    }

    function buildActualCueMarkers(
        sessionStartedAtUs: number,
        sessionEndedAtUs: number,
    ) {
        return buildCueMarkerPayloads({
            sessionId,
            cues: cueSchedule,
            sessionStartedAtUs,
        }).filter((marker) => marker.emitted_at_us <= sessionEndedAtUs);
    }

    function publishSessionCompletion(
        sessionStartedAtUs: number,
        sessionEndedAtUs: number,
    ) {
        const { deviceIds, tags } = buildCurrentDeviceContext();
        sendSessionBundleToKafka({
            requestId: buildPublishRequestId("complete"),
            sessionId,
            metaRecords: [
                buildSessionMetadataRecordForTimes(
                    sessionStartedAtUs,
                    sessionEndedAtUs,
                ),
            ],
            markerEvents: [
                ...buildActualCueMarkers(sessionStartedAtUs, sessionEndedAtUs),
                buildSessionLifecycleMarkerPayload({
                    sessionId,
                    purpose: "training",
                    participantId: subject,
                    protocolId: "emg-gesture-cues-v1",
                    deviceIds,
                    tags,
                    notes,
                    event: "end",
                    emittedAtUs: sessionEndedAtUs,
                }),
            ],
        });
    }

    function finishRun(nextState: RunState) {
        if (sessionStartedAtEpochMs === null) {
            return;
        }
        stopTimer();
        const completedAtEpochMs = Date.now();
        const completedElapsedMs =
            sessionStartedAtPerfMs !== null
                ? performance.now() - sessionStartedAtPerfMs
                : elapsedMs;
        sessionCompletedAtEpochMs = completedAtEpochMs;
        elapsedMs = Math.min(
            Math.max(0, completedElapsedMs),
            totalDurationMs,
        );
        sessionStartedAtPerfMs = null;
        runState = nextState;
        publishSessionCompletion(
            sessionStartedAtEpochMs * 1000,
            completedAtEpochMs * 1000,
        );
    }

    function tick() {
        if (sessionStartedAtPerfMs === null) {
            return;
        }
        const nextElapsedMs = performance.now() - sessionStartedAtPerfMs;
        elapsedMs = nextElapsedMs;
        if (nextElapsedMs >= totalDurationMs) {
            finishRun("completed");
            return;
        }
        animationFrameId = requestAnimationFrame(tick);
    }

    function startRun() {
        if (!canStart) {
            return;
        }
        ensureStreamSubscribed(selectedStreamId);
        lastProcessedFrameKey = selectedFrames.at(-1)
            ? buildFrameKey(selectedFrames[selectedFrames.length - 1])
            : null;
        recordedFrames = [];
        frameCount = 0;
        sampleCount = 0;
        gestureSummaryMap = new Map();
        elapsedMs = 0;
        const startedAtEpochMs = Date.now();
        sessionStartedAtEpochMs = startedAtEpochMs;
        sessionStartedAtPerfMs = performance.now();
        sessionCompletedAtEpochMs = null;
        runState = "running";
        stopTimer();
        animationFrameId = requestAnimationFrame(tick);
        publishSessionStart(startedAtEpochMs * 1000);
    }

    function abortRun() {
        if (runState !== "running") {
            return;
        }
        finishRun("aborted");
    }

    function resetRun() {
        stopTimer();
        runState = "idle";
        elapsedMs = 0;
        sessionStartedAtEpochMs = null;
        sessionStartedAtPerfMs = null;
        sessionCompletedAtEpochMs = null;
        recordedFrames = [];
        frameCount = 0;
        sampleCount = 0;
        gestureSummaryMap = new Map();
        lastProcessedFrameKey = null;
        sessionId = buildDefaultSessionId();
        seed = Math.floor(Date.now() % 100000);
        lastPublishRequestId = null;
        publishState = "idle";
        publishMessage = null;
    }

    function toggleGesture(gesture: string, checked: boolean) {
        if (checked) {
            if (!selectedGestures.includes(gesture)) {
                selectedGestures = [...selectedGestures, gesture];
            }
            return;
        }
        selectedGestures = selectedGestures.filter((item) => item !== gesture);
    }

    function downloadText(
        filename: string,
        contents: string,
        mimeType: string,
    ) {
        const blob = new Blob([contents], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    function buildCueExportPayload() {
        if (sessionStartedAtEpochMs === null) {
            return null;
        }
        const startedAtUs = sessionStartedAtEpochMs * 1000;
        return {
            session_id: sessionId,
            stream_id: selectedStreamId,
            device_id:
                selectedStream?.latestSample?.device_id ??
                recordedFrames[0]?.frame.device_id ??
                null,
            started_at_utc: new Date(sessionStartedAtEpochMs).toISOString(),
            events: cueSchedule.map((cue) => ({
                ...cue,
                start_ts_us: startedAtUs + cue.start_offset_ms * 1000,
                end_ts_us: startedAtUs + cue.end_offset_ms * 1000,
            })),
        };
    }

    function buildTrainingRows() {
        return recordedFrames.map((record) => {
            const row: Record<string, unknown> = {
                schema_version: record.frame.schema_version,
                device_id: record.frame.device_id,
                stream_id: record.stream_id,
                seq_no: record.frame.seq_no,
                device_ts_us: record.frame.device_ts_us,
                sample_rate_hz: record.frame.sample_rate_hz,
                n_channels: record.frame.n_channels,
                samples_per_channel: record.frame.samples_per_channel,
                channel_labels: record.frame.channel_labels,
                received_at_ms: record.received_at_ms,
                received_at_utc: record.received_at_utc,
                elapsed_ms: record.elapsed_ms,
                cue_id: record.cue_id,
                cue_phase: record.cue_phase,
                cue_gesture: record.cue_gesture,
                cue_prompt: record.cue_prompt,
            };
            record.frame.payload.forEach((channel, index) => {
                row[`channel_${index}`] = channel;
            });
            return row;
        });
    }

    function buildSessionExportPayload() {
        const createdAtUs =
            sessionStartedAtEpochMs !== null ? sessionStartedAtEpochMs * 1000 : 0;
        const updatedAtUs =
            sessionCompletedAtEpochMs !== null
                ? sessionCompletedAtEpochMs * 1000
                : createdAtUs;
        const { deviceId, deviceIds, tags } = buildCurrentDeviceContext();
        const sessionMetadataRecord = buildSessionMetadataRecordForTimes(
            createdAtUs,
            updatedAtUs,
        );
        const lifecycleMarkers = createdAtUs
            ? [
                  buildSessionLifecycleMarkerPayload({
                      sessionId,
                      purpose: "training",
                      participantId: subject,
                      protocolId: "emg-gesture-cues-v1",
                      deviceIds,
                      tags,
                      notes,
                      event: "start",
                      emittedAtUs: createdAtUs,
                  }),
                  ...(sessionCompletedAtEpochMs !== null
                      ? [
                            buildSessionLifecycleMarkerPayload({
                                sessionId,
                                purpose: "training",
                                participantId: subject,
                                protocolId: "emg-gesture-cues-v1",
                                deviceIds,
                                tags,
                                notes,
                                event: "end",
                                emittedAtUs: sessionCompletedAtEpochMs * 1000,
                            }),
                        ]
                      : []),
              ]
            : [];
        const cueMarkers =
            createdAtUs && updatedAtUs
                ? buildActualCueMarkers(createdAtUs, updatedAtUs)
                : [];
        return {
            metadata: {
                session_id: sessionId,
                stream_id: selectedStreamId,
                device_id: deviceId,
                subject: subject || null,
                arm,
                notes: notes || null,
                seed,
                run_state: runState,
                started_at_utc:
                    sessionStartedAtEpochMs !== null
                        ? new Date(sessionStartedAtEpochMs).toISOString()
                        : null,
                completed_at_utc:
                    sessionCompletedAtEpochMs !== null
                        ? new Date(sessionCompletedAtEpochMs).toISOString()
                        : null,
                sample_rate_hz:
                    selectedStream?.latestSample?.sample_rate_hz ??
                    recordedFrames[0]?.frame.sample_rate_hz ??
                    null,
                channel_map:
                    selectedStream?.latestSample?.channel_labels ??
                    recordedFrames[0]?.frame.channel_labels ??
                    [],
                selected_gestures: [...selectedGestures],
                repetitions,
                hold_s: holdS,
                rest_s: restS,
                lead_in_s: leadInS,
                tail_rest_s: tailRestS,
                frame_count: frameCount,
                sample_count: sampleCount,
            },
            meta_records: [sessionMetadataRecord],
            marker_events: [...lifecycleMarkers, ...cueMarkers],
            cues: buildCueExportPayload(),
            frames: recordedFrames.map((record) => ({
                ...record.frame,
                stream_id: record.stream_id,
                received_at_ms: record.received_at_ms,
                received_at_utc: record.received_at_utc,
                elapsed_ms: record.elapsed_ms,
                cue_id: record.cue_id,
                cue_phase: record.cue_phase,
                cue_gesture: record.cue_gesture,
                cue_prompt: record.cue_prompt,
            })),
        };
    }

    function downloadSessionJson() {
        if (frameCount === 0) {
            return;
        }
        downloadText(
            `${sessionId}__browser-capture.json`,
            JSON.stringify(buildSessionExportPayload(), null, 2) + "\n",
            "application/json",
        );
    }

    function downloadCueJson() {
        const payload = buildCueExportPayload();
        if (!payload) {
            return;
        }
        downloadText(
            `${sessionId}__browser-capture.cues.json`,
            JSON.stringify(payload, null, 2) + "\n",
            "application/json",
        );
    }

    function downloadTrainingJsonl() {
        if (frameCount === 0) {
            return;
        }
        const lines = buildTrainingRows().map((row) => JSON.stringify(row));
        downloadText(
            `${sessionId}__browser-capture.frames.jsonl`,
            `${lines.join("\n")}\n`,
            "application/x-ndjson",
        );
    }
</script>

<div class="experiment-shell">
    <div class="experiment-header">
        <div>
            <h3>EMG Experiment</h3>
            <p>
                Guided cue capture for labeled EMG frames using the live stream
                already connected to this viewer.
            </p>
        </div>
        <span class="run-state {runState}">
            {runState === "running"
                ? "Recording"
                : runState === "completed"
                  ? "Complete"
                  : runState === "aborted"
                    ? "Aborted"
                    : "Ready"}
        </span>
    </div>

    {#if emgStreams.length === 0}
        <div class="empty-state">
            No EMG streams are available yet. Bring up a device or bridge, then
            refresh the stream list.
        </div>
    {:else}
        <div class="experiment-grid">
            <section class="control-panel">
                <div class="section-head">
                    <h4>Session Setup</h4>
                    <p>Choose one EMG stream and the cue schedule to record.</p>
                </div>

                <div class="field-grid">
                    <label class="field">
                        <span>Stream</span>
                        <select
                            bind:value={selectedStreamId}
                            disabled={runState === "running"}
                        >
                            {#each emgStreams as stream}
                                <option value={stream.streamId}>
                                    Stream {stream.streamId}
                                    {stream.subscribed ? " · subscribed" : ""}
                                    {stream.live ? " · live" : ""}
                                </option>
                            {/each}
                        </select>
                    </label>

                    <label class="field">
                        <span>Session ID</span>
                        <input
                            class="input-control"
                            bind:value={sessionId}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Subject</span>
                        <input
                            class="input-control"
                            bind:value={subject}
                            placeholder="optional"
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Arm</span>
                        <select bind:value={arm} disabled={runState === "running"}>
                            <option value="right">Right</option>
                            <option value="left">Left</option>
                            <option value="both">Both</option>
                        </select>
                    </label>

                    <label class="field">
                        <span>Repetitions</span>
                        <input
                            class="input-control"
                            type="number"
                            min="1"
                            step="1"
                            bind:value={repetitions}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Hold (s)</span>
                        <input
                            class="input-control"
                            type="number"
                            min="1"
                            step="1"
                            bind:value={holdS}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Rest (s)</span>
                        <input
                            class="input-control"
                            type="number"
                            min="0"
                            step="1"
                            bind:value={restS}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Lead-in (s)</span>
                        <input
                            class="input-control"
                            type="number"
                            min="0"
                            step="1"
                            bind:value={leadInS}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Tail Rest (s)</span>
                        <input
                            class="input-control"
                            type="number"
                            min="0"
                            step="1"
                            bind:value={tailRestS}
                            disabled={runState === "running"}
                        />
                    </label>

                    <label class="field">
                        <span>Seed</span>
                        <input
                            class="input-control"
                            type="number"
                            step="1"
                            bind:value={seed}
                            disabled={runState === "running"}
                        />
                    </label>
                </div>

                <label class="field">
                    <span>Notes</span>
                    <textarea
                        bind:value={notes}
                        rows="3"
                        placeholder="electrode placement, fatigue, setup issues"
                        disabled={runState === "running"}
                    ></textarea>
                </label>

                <div class="gesture-section">
                    <div class="section-head compact">
                        <h4>Gestures</h4>
                        <p>These hold prompts become class labels in the export.</p>
                    </div>
                    <div class="gesture-grid">
                        {#each EMG_GESTURE_OPTIONS as gesture}
                            <label class="gesture-option">
                                <input
                                    type="checkbox"
                                    checked={selectedGestures.includes(gesture)}
                                    onchange={(event) =>
                                        toggleGesture(
                                            gesture,
                                            (event.currentTarget as HTMLInputElement)
                                                .checked,
                                        )}
                                    disabled={runState === "running"}
                                />
                                <span>{gesture}</span>
                            </label>
                        {/each}
                    </div>
                </div>

                <div class="selected-stream-meta">
                    <div>
                        <span class="meta-label">Status</span>
                        <span class:live={selectedStream?.live}>
                            {selectedStream?.live ? "Live" : "Waiting"}
                        </span>
                    </div>
                    <div>
                        <span class="meta-label">Sample Rate</span>
                        <span>
                            {selectedStream?.latestSample?.sample_rate_hz ?? "?"}
                            Hz
                        </span>
                    </div>
                    <div>
                        <span class="meta-label">Channels</span>
                        <span>
                            {selectedStream?.latestSample?.channel_labels.join(", ") ??
                                "unknown"}
                        </span>
                    </div>
                </div>

                <div class="action-row">
                    <button
                        class="action-button primary"
                        onclick={startRun}
                        disabled={!canStart}
                    >
                        Start Session
                    </button>
                    <button
                        class="action-button"
                        onclick={abortRun}
                        disabled={runState !== "running"}
                    >
                        Stop Early
                    </button>
                    <button
                        class="action-button"
                        onclick={resetRun}
                        disabled={runState === "running"}
                    >
                        Reset
                    </button>
                </div>

                <div class="export-row">
                    <button
                        class="action-button"
                        onclick={downloadSessionJson}
                        disabled={frameCount === 0}
                    >
                        Session JSON
                    </button>
                    <button
                        class="action-button"
                        onclick={downloadCueJson}
                        disabled={sessionStartedAtEpochMs === null}
                    >
                        Cue JSON
                    </button>
                    <button
                        class="action-button"
                        onclick={downloadTrainingJsonl}
                        disabled={frameCount === 0}
                    >
                        Training JSONL
                    </button>
                </div>

                {#if publishMessage}
                    <div class="publish-status {publishState}">
                        {publishMessage}
                    </div>
                {/if}
            </section>

            <section class="cue-panel">
                <div class="cue-surface">
                    <div class="cue-meta">
                        <span>{formatDurationMs(elapsedMs)}</span>
                        <span>{formatDurationMs(totalDurationMs)}</span>
                    </div>
                    <div class="progress-track">
                        <div
                            class="progress-fill"
                            style={`width: ${progressPct}%`}
                        ></div>
                    </div>

                    <div class="cue-main">
                        <span class="cue-phase">
                            {currentCue?.phase ??
                                (runState === "completed"
                                    ? "complete"
                                    : runState === "aborted"
                                      ? "aborted"
                                      : "idle")}
                        </span>
                        <h2>
                            {currentCue?.prompt ??
                                (runState === "completed"
                                    ? "Done"
                                    : runState === "aborted"
                                      ? "Stopped"
                                      : "Ready")}
                        </h2>
                        <p>
                            {#if currentCue}
                                Hold <strong>{currentCue.gesture}</strong> until
                                the timer advances.
                            {:else if runState === "idle"}
                                Start the session when the user is ready and the
                                live signal looks plausible.
                            {:else}
                                Export the captured frames for training or
                                offline conversion.
                            {/if}
                        </p>
                    </div>

                    <div class="cue-summary">
                        <div>
                            <span class="metric-label">Frames</span>
                            <strong>{frameCount}</strong>
                        </div>
                        <div>
                            <span class="metric-label">Samples</span>
                            <strong>{sampleCount}</strong>
                        </div>
                        <div>
                            <span class="metric-label">Next Cue</span>
                            <strong>{nextCue?.prompt ?? "None"}</strong>
                        </div>
                    </div>
                </div>

                <div class="timeline-panel">
                    <div class="section-head compact">
                        <h4>Schedule</h4>
                        <p>
                            {cueSchedule.length} cues across
                            {repetitions} repetition{repetitions === 1 ? "" : "s"}.
                        </p>
                    </div>
                    <div class="timeline-list">
                        {#each cueSchedule as cue}
                            <div
                                class="timeline-item"
                                class:active={
                                    currentCue !== null &&
                                    currentCue.cue_id === cue.cue_id
                                }
                            >
                                <span class="timeline-time">
                                    {formatDurationMs(cue.start_offset_ms)}
                                </span>
                                <div>
                                    <strong>{cue.prompt}</strong>
                                    <p>
                                        {cue.phase} · rep
                                        {cue.rep_index >= 0
                                            ? cue.rep_index + 1
                                            : "prep"}
                                    </p>
                                </div>
                            </div>
                        {/each}
                    </div>
                </div>

                <div class="timeline-panel">
                    <div class="section-head compact">
                        <h4>Capture Summary</h4>
                        <p>What the current browser session has recorded so far.</p>
                    </div>
                    {#if gestureSummary.length === 0}
                        <p class="summary-empty">
                            No labeled frames captured yet.
                        </p>
                    {:else}
                        <table class="summary-table">
                            <thead>
                                <tr>
                                    <th>Label</th>
                                    <th>Frames</th>
                                    <th>Samples</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each gestureSummary as row}
                                    <tr>
                                        <td>{row.gesture}</td>
                                        <td>{row.frames}</td>
                                        <td>{row.samples}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    {/if}
                </div>
            </section>
        </div>
    {/if}
</div>

<style>
    .experiment-shell {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .experiment-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
    }

    .experiment-header h3 {
        margin: 0;
        font-size: 1.15rem;
        color: #1a1a2e;
    }

    .experiment-header p {
        margin: 0.35rem 0 0;
        color: #5b6472;
        font-size: 0.92rem;
    }

    .run-state {
        padding: 0.4rem 0.75rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        white-space: nowrap;
    }

    .run-state.idle {
        background: #e2e8f0;
        color: #334155;
    }

    .run-state.running {
        background: #dcfce7;
        color: #166534;
    }

    .run-state.completed {
        background: #dbeafe;
        color: #1d4ed8;
    }

    .run-state.aborted {
        background: #fee2e2;
        color: #b91c1c;
    }

    .empty-state {
        padding: 1rem;
        border: 1px dashed #cbd5e1;
        border-radius: 8px;
        background: #fff;
        color: #475569;
    }

    .experiment-grid {
        display: grid;
        grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
        gap: 1rem;
        align-items: start;
    }

    .control-panel,
    .cue-panel {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .control-panel,
    .cue-surface,
    .timeline-panel {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
    }

    .section-head {
        margin-bottom: 0.85rem;
    }

    .section-head.compact {
        margin-bottom: 0.75rem;
    }

    .section-head h4 {
        margin: 0;
        font-size: 0.96rem;
        color: #0f172a;
    }

    .section-head p {
        margin: 0.3rem 0 0;
        color: #64748b;
        font-size: 0.84rem;
    }

    .field-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
    }

    .field span {
        font-size: 0.8rem;
        font-weight: 600;
        color: #334155;
    }

    .field select,
    .input-control,
    .field textarea {
        width: 100%;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 0.65rem 0.75rem;
        font: inherit;
        background: #fff;
        color: #0f172a;
        resize: vertical;
        min-height: 2.5rem;
    }

    .field select:disabled,
    .input-control:disabled,
    .field textarea:disabled {
        background: #f8fafc;
        color: #64748b;
    }

    .gesture-section {
        padding-top: 0.25rem;
    }

    .gesture-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.5rem;
    }

    .gesture-option {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        color: #0f172a;
    }

    .selected-stream-meta {
        display: grid;
        gap: 0.5rem;
        padding: 0.85rem 0;
        border-top: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
    }

    .selected-stream-meta > div {
        display: grid;
        grid-template-columns: 84px minmax(0, 1fr);
        gap: 0.5rem;
        font-size: 0.84rem;
        color: #334155;
    }

    .meta-label {
        color: #64748b;
        font-weight: 600;
    }

    .live {
        color: #15803d;
        font-weight: 600;
    }

    .action-row,
    .export-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }

    .action-button {
        border: 1px solid #cbd5e1;
        background: #fff;
        color: #0f172a;
        border-radius: 6px;
        padding: 0.65rem 0.95rem;
        font: inherit;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
    }

    .action-button.primary {
        background: #0f172a;
        border-color: #0f172a;
        color: #fff;
    }

    .action-button:disabled {
        cursor: not-allowed;
        opacity: 0.5;
    }

    .publish-status {
        border-radius: 6px;
        padding: 0.75rem 0.85rem;
        font-size: 0.84rem;
        border: 1px solid #cbd5e1;
        color: #334155;
        background: #f8fafc;
    }

    .publish-status.pending {
        border-color: #bfdbfe;
        background: #eff6ff;
        color: #1d4ed8;
    }

    .publish-status.sent {
        border-color: #bbf7d0;
        background: #f0fdf4;
        color: #166534;
    }

    .publish-status.error {
        border-color: #fecaca;
        background: #fef2f2;
        color: #b91c1c;
    }

    .cue-surface {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .cue-meta {
        display: flex;
        justify-content: space-between;
        font-size: 0.84rem;
        color: #64748b;
    }

    .progress-track {
        height: 8px;
        border-radius: 999px;
        background: #e2e8f0;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background: #2563eb;
    }

    .cue-main {
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.5rem;
        border-radius: 8px;
        background: #0f172a;
        color: #f8fafc;
        padding: 1.5rem;
    }

    .cue-phase {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #93c5fd;
        font-weight: 700;
    }

    .cue-main h2 {
        margin: 0;
        font-size: clamp(2rem, 4vw, 3.5rem);
        line-height: 1;
        letter-spacing: 0;
    }

    .cue-main p {
        margin: 0;
        max-width: 38rem;
        color: #cbd5e1;
        font-size: 0.95rem;
    }

    .cue-summary {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .cue-summary > div {
        padding: 0.85rem;
        border-radius: 8px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
    }

    .metric-label {
        display: block;
        font-size: 0.78rem;
        color: #64748b;
        margin-bottom: 0.35rem;
    }

    .timeline-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        max-height: 260px;
        overflow-y: auto;
    }

    .timeline-item {
        display: grid;
        grid-template-columns: 64px minmax(0, 1fr);
        gap: 0.75rem;
        padding: 0.65rem 0.75rem;
        border-radius: 6px;
        background: #f8fafc;
        border: 1px solid transparent;
    }

    .timeline-item.active {
        border-color: #60a5fa;
        background: #eff6ff;
    }

    .timeline-time {
        font-family: monospace;
        color: #475569;
        font-size: 0.84rem;
        padding-top: 0.1rem;
    }

    .timeline-item strong {
        display: block;
        font-size: 0.9rem;
        color: #0f172a;
    }

    .timeline-item p {
        margin: 0.2rem 0 0;
        color: #64748b;
        font-size: 0.78rem;
    }

    .summary-empty {
        margin: 0;
        color: #64748b;
        font-size: 0.88rem;
    }

    .summary-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.88rem;
    }

    .summary-table th,
    .summary-table td {
        padding: 0.6rem 0.4rem;
        text-align: left;
        border-bottom: 1px solid #e2e8f0;
    }

    .summary-table th {
        color: #475569;
        font-size: 0.78rem;
        text-transform: uppercase;
    }

    @media (max-width: 1100px) {
        .experiment-grid {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 720px) {
        .field-grid,
        .gesture-grid,
        .cue-summary {
            grid-template-columns: 1fr;
        }

        .experiment-header {
            flex-direction: column;
        }

        .cue-main {
            min-height: 140px;
            padding: 1rem;
        }
    }
</style>
