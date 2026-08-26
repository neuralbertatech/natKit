// How a stream is named to a person (TEC-NATKIT-103).
//
// ⚠️ THE ID IS NEVER REPLACED, ONLY PREFIXED. A stream is identified everywhere
// that matters — topic names, recorded Parquet, log lines, the device command
// channel — by its number. Showing "Left Hand" alone would make every one of
// those unsearchable from the screen that named it, and would hide which of four
// identical boards is actually being addressed. So an alias always renders as
// `Left Hand (13793649671244)`.

/** Aliases by stream id, as the backend resolves them for this user. */
export type StreamAliases = Record<string, string>;

/**
 * Device-reported names, keyed by stream id.
 *
 * ⚠️ NOT the same thing as an alias. This is whatever the device puts on its own
 * samples, so it only exists while data is flowing and nobody chose it. It is a
 * better fallback than a bare number and a worse answer than a name a human
 * picked, which is exactly where it sits in the order below.
 */
export type StreamDeviceNames = Record<string, string>;

export interface StreamNameParts {
    /** The friendly part, or null when nothing but the id is known. */
    label: string | null;
    /** Always present. */
    streamId: string;
    /** Where `label` came from — for tests and for explaining it in the UI. */
    source: "alias" | "device" | "none";
}

export function streamNameParts(
    streamId: string | number | null | undefined,
    aliases: StreamAliases = {},
    deviceNames: StreamDeviceNames = {},
): StreamNameParts {
    const id = streamId === null || streamId === undefined ? "" : String(streamId);
    const alias = aliases[id];
    if (alias && alias.trim().length > 0) {
        return { label: alias.trim(), streamId: id, source: "alias" };
    }
    const device = deviceNames[id];
    // ⚠️ A device that reports its own id as its name adds nothing — rendering
    // "13793649671244 (13793649671244)" is worse than the bare number.
    if (device && device.trim().length > 0 && device.trim() !== id) {
        return { label: device.trim(), streamId: id, source: "device" };
    }
    return { label: null, streamId: id, source: "none" };
}

/**
 * The one string every surface should show: `Left Hand (13793649671244)`, or
 * just the id when nothing friendlier is known.
 */
export function streamDisplayName(
    streamId: string | number | null | undefined,
    aliases: StreamAliases = {},
    deviceNames: StreamDeviceNames = {},
): string {
    const parts = streamNameParts(streamId, aliases, deviceNames);
    if (!parts.streamId) return "";
    return parts.label ? `${parts.label} (${parts.streamId})` : parts.streamId;
}
