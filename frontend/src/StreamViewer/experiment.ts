import type { BufferedEmgSample, StreamInfo } from "./types";

export const EMG_GESTURE_OPTIONS = [
    "rest",
    "fist",
    "open",
    "pinch",
    "point",
    "thumbs_up",
] as const;

export type EmgCuePhase = "lead_in" | "hold" | "rest" | "tail_rest";

export interface EmgExperimentConfig {
    gestures: string[];
    repetitions: number;
    holdS: number;
    restS: number;
    leadInS: number;
    tailRestS: number;
    seed: number;
}

export interface EmgCueEvent {
    cue_id: number;
    rep_index: number;
    phase: EmgCuePhase;
    gesture: string;
    prompt: string;
    start_offset_ms: number;
    end_offset_ms: number;
}

export interface EmgStreamOption {
    streamId: string;
    info: StreamInfo;
    subscribed: boolean;
    live: boolean;
    lastReceivedAtMs: number | null;
    latestSample: BufferedEmgSample | null;
}

export interface EmgRecordedFrame {
    stream_id: string;
    received_at_ms: number;
    received_at_utc: string;
    elapsed_ms: number;
    cue_id: number | null;
    cue_phase: EmgCuePhase | null;
    cue_gesture: string | null;
    cue_prompt: string | null;
    frame: BufferedEmgSample;
}

export interface SessionMetadataRecordPayload {
    schema_version: string;
    session_id: string;
    purpose: string;
    participant_id: string;
    protocol_id: string;
    device_ids: string[];
    tags: string[];
    notes: string;
    created_at_us: number;
    updated_at_us: number;
}

export interface MarkerEventPayload {
    schema_version: string;
    session_id: string;
    marker_type: string;
    marker_id: string;
    event: string;
    label: string;
    emitted_at_us: number;
    attributes: Record<string, unknown>;
}

export interface SessionPublishBundleInput {
    requestId: string;
    sessionId: string;
    metaRecords: SessionMetadataRecordPayload[];
    markerEvents: MarkerEventPayload[];
}

export function buildCueMarkerPayloads(args: {
    sessionId: string;
    cues: EmgCueEvent[];
    sessionStartedAtUs: number;
}): MarkerEventPayload[] {
    return args.cues.flatMap((cue) => [
        {
            schema_version: "marker.event.v1",
            session_id: args.sessionId,
            marker_type: "cue",
            marker_id: `cue:${cue.cue_id}`,
            event: "start",
            label: cue.prompt,
            emitted_at_us: args.sessionStartedAtUs + cue.start_offset_ms * 1000,
            attributes: {
                cue_id: cue.cue_id,
                rep_index: cue.rep_index,
                phase: cue.phase,
                gesture: cue.gesture,
                prompt: cue.prompt,
            },
        },
        {
            schema_version: "marker.event.v1",
            session_id: args.sessionId,
            marker_type: "cue",
            marker_id: `cue:${cue.cue_id}`,
            event: "end",
            label: cue.prompt,
            emitted_at_us: args.sessionStartedAtUs + cue.end_offset_ms * 1000,
            attributes: {
                cue_id: cue.cue_id,
                rep_index: cue.rep_index,
                phase: cue.phase,
                gesture: cue.gesture,
                prompt: cue.prompt,
            },
        },
    ]);
}

function mulberry32(seed: number): () => number {
    let value = seed >>> 0;
    return () => {
        value += 0x6d2b79f5;
        let t = value;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function shuffle<T>(items: T[], seed: number): T[] {
    const next = [...items];
    const rand = mulberry32(seed);
    for (let index = next.length - 1; index > 0; index -= 1) {
        const swapIndex = Math.floor(rand() * (index + 1));
        [next[index], next[swapIndex]] = [next[swapIndex], next[index]];
    }
    return next;
}

export function buildCueSchedule(
    config: EmgExperimentConfig,
): EmgCueEvent[] {
    const gestures = config.gestures.filter(Boolean);
    if (gestures.length === 0) {
        return [];
    }

    let currentOffsetMs = 0;
    let cueId = 0;
    const schedule: EmgCueEvent[] = [];

    if (config.leadInS > 0) {
        schedule.push({
            cue_id: cueId,
            rep_index: -1,
            phase: "lead_in",
            gesture: "rest",
            prompt: "Prepare",
            start_offset_ms: currentOffsetMs,
            end_offset_ms: currentOffsetMs + config.leadInS * 1000,
        });
        cueId += 1;
        currentOffsetMs += config.leadInS * 1000;
    }

    for (let repIndex = 0; repIndex < config.repetitions; repIndex += 1) {
        const order = shuffle(gestures, config.seed + repIndex);
        for (const gesture of order) {
            schedule.push({
                cue_id: cueId,
                rep_index: repIndex,
                phase: "hold",
                gesture,
                prompt: gesture,
                start_offset_ms: currentOffsetMs,
                end_offset_ms: currentOffsetMs + config.holdS * 1000,
            });
            cueId += 1;
            currentOffsetMs += config.holdS * 1000;

            if (config.restS > 0) {
                schedule.push({
                    cue_id: cueId,
                    rep_index: repIndex,
                    phase: "rest",
                    gesture: "rest",
                    prompt: "Rest",
                    start_offset_ms: currentOffsetMs,
                    end_offset_ms: currentOffsetMs + config.restS * 1000,
                });
                cueId += 1;
                currentOffsetMs += config.restS * 1000;
            }
        }
    }

    if (config.tailRestS > 0) {
        schedule.push({
            cue_id: cueId,
            rep_index: config.repetitions,
            phase: "tail_rest",
            gesture: "rest",
            prompt: "Done",
            start_offset_ms: currentOffsetMs,
            end_offset_ms: currentOffsetMs + config.tailRestS * 1000,
        });
    }

    return schedule;
}

export function activeCueAtElapsedMs(
    schedule: EmgCueEvent[],
    elapsedMs: number,
): EmgCueEvent | null {
    for (const cue of schedule) {
        if (
            elapsedMs >= cue.start_offset_ms &&
            elapsedMs < cue.end_offset_ms
        ) {
            return cue;
        }
    }
    return null;
}

export function nextCueAfterElapsedMs(
    schedule: EmgCueEvent[],
    elapsedMs: number,
): EmgCueEvent | null {
    for (const cue of schedule) {
        if (cue.start_offset_ms > elapsedMs) {
            return cue;
        }
    }
    return null;
}

export function scheduleDurationMs(schedule: EmgCueEvent[]): number {
    return schedule.reduce(
        (maxEndMs, cue) => Math.max(maxEndMs, cue.end_offset_ms),
        0,
    );
}

export function buildDefaultSessionId(prefix: string = "emg-web"): string {
    const timestamp = new Date()
        .toISOString()
        .replace(/[:.]/g, "-")
        .slice(0, 19);
    return `${prefix}-${timestamp}`;
}

export function formatDurationMs(ms: number): string {
    const clampedMs = Math.max(0, Math.floor(ms));
    const totalSeconds = Math.floor(clampedMs / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function buildSessionMetadataRecordPayload(args: {
    sessionId: string;
    purpose?: string;
    participantId?: string;
    protocolId?: string;
    deviceIds?: string[];
    tags?: string[];
    notes?: string;
    createdAtUs: number;
    updatedAtUs?: number;
}): SessionMetadataRecordPayload {
    return {
        schema_version: "session.metadata.record.v1",
        session_id: args.sessionId,
        purpose: args.purpose ?? "training",
        participant_id: args.participantId ?? "",
        protocol_id: args.protocolId ?? "",
        device_ids: [...(args.deviceIds ?? [])],
        tags: [...(args.tags ?? [])],
        notes: args.notes ?? "",
        created_at_us: args.createdAtUs,
        updated_at_us: args.updatedAtUs ?? args.createdAtUs,
    };
}

export function buildSessionLifecycleMarkerPayload(args: {
    sessionId: string;
    purpose?: string;
    participantId?: string;
    protocolId?: string;
    deviceIds?: string[];
    tags?: string[];
    notes?: string;
    event: "start" | "end";
    emittedAtUs: number;
}): MarkerEventPayload {
    return {
        schema_version: "marker.event.v1",
        session_id: args.sessionId,
        marker_type: "session",
        marker_id: `session:${args.sessionId}`,
        event: args.event,
        label: args.purpose ?? "training",
        emitted_at_us: args.emittedAtUs,
        attributes: {
            purpose: args.purpose ?? "training",
            participant_id: args.participantId ?? "",
            protocol_id: args.protocolId ?? "",
            device_ids: [...(args.deviceIds ?? [])],
            tags: [...(args.tags ?? [])],
            notes: args.notes ?? "",
        },
    };
}
