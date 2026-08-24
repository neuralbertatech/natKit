// A stream's clock fit, as a consumer of that stream should see it.
//
// The rig publishes each leaf's clock fit at ~1 Hz on
// `Log-<id>-Binary-NatKitNodeStatusV1` (TEC-NATKIT-33), but until now only the
// health panel read it. A viewer, transform or exporter reading
// `Data-<id>-Binary-…` had no path to it — different topic, different StreamType
// — which is the gap the #319 whiteboard meant by putting jitter "on the Stream"
// (TEC-NATKIT-7).
//
// ⚠️ The distinction this module exists to preserve: "this device has no clock
// fit" and "we have no idea whether this device has a clock fit" are different
// answers, and most streams are legitimately the second. A Muse headband or an
// EMG pill does not publish a node-status frame at all, so treating absence as a
// fault would put a warning on most nodes on most boards and train people to
// ignore it.

import type { DeviceHealthEntry, DeviceHealthMessage } from "./types";

export type ClockFitState =
    /** No status channel for this device — the common case, and not a fault. */
    | "unknown"
    /** Reporting, and the hub holds a usable fit. */
    | "ok"
    /** Reporting, and the hub does NOT hold a usable fit. */
    | "no_fit"
    /** It was reporting and has gone silent; the last fit is stale. */
    | "stale";

export interface ClockFit {
    state: ClockFitState;
    /** SyncQuality grade, when known. */
    quality: number | null;
    /** Fit residual in ns, when known. Saturates at 0xFFFFFFFF = 4.29 s. */
    residualRmsNs: number | null;
    /** Relative crystal rate in ppb, when known. */
    skewPpb: number | null;
    /** Beacons missed per second over the health window, when a rate exists. */
    beaconsMissedPerS: number | null;
    /** Milliseconds since the backend last heard from the device. */
    ageMs: number | null;
    /** One line a person can read, suitable for a title attribute. */
    summary: string;
    /**
     * The numbers ONLY, with no state phrase.
     *
     * Split out because a caller that renders its own state line — the source
     * inspector does, in colour, so it can be scanned — would otherwise print
     * "Clock fit held" immediately above "Clock fit held: residual 46 µs…".
     * Empty when there is nothing to add.
     */
    detail: string;
}

/** ⚠️ residual_rms_ns saturates at 0xFFFFFFFF, which is 4.29 SECONDS, not ms. */
export const RESIDUAL_SATURATED = 0xffffffff;

export const UNKNOWN_CLOCK_FIT: ClockFit = {
    state: "unknown",
    detail: "",
    quality: null,
    residualRmsNs: null,
    skewPpb: null,
    beaconsMissedPerS: null,
    ageMs: null,
    summary: "This device does not publish a clock fit.",
};

function nested(entry: DeviceHealthEntry, field: string): unknown {
    const sync = entry.fields?.sync;
    if (sync && typeof sync === "object") {
        return (sync as Record<string, unknown>)[field];
    }
    return undefined;
}

function num(value: unknown): number | null {
    return typeof value === "number" ? value : null;
}

function residualLabel(ns: number | null): string {
    if (ns === null) return "unknown residual";
    // Saturation is not a large-but-real residual; it means the window's samples
    // sit seconds off their own line, i.e. no usable fit (TEC-NATKIT-47).
    if (ns >= RESIDUAL_SATURATED) return "residual saturated (no usable fit)";
    if (ns >= 1000) return `residual ${(ns / 1000).toFixed(1)} µs`;
    return `residual ${ns} ns`;
}

/**
 * Read a stream's clock fit out of the latest device-health push.
 *
 * `streamId` is the stream's own id, which is the same id its status topic
 * carries — `Data-13793649670644-…` and `Log-13793649670644-…` are the same
 * device.
 */
export function clockFitForStream(
    health: DeviceHealthMessage | null,
    streamId: string | number | null | undefined,
): ClockFit {
    if (!health || streamId === null || streamId === undefined) {
        return UNKNOWN_CLOCK_FIT;
    }
    const wanted = String(streamId);
    const entry = health.devices.find((device) => device.device_id === wanted);
    if (!entry) {
        return UNKNOWN_CLOCK_FIT;
    }

    const quality = num(nested(entry, "quality"));
    const residualRmsNs = num(nested(entry, "residual_rms_ns"));
    const skewPpb = num(nested(entry, "skew_ppb"));
    const valid = nested(entry, "valid");
    const beaconsMissedPerS = num(entry.rates?.["sync.beacons_missed"]);

    const common = {
        quality,
        residualRmsNs,
        skewPpb,
        beaconsMissedPerS,
        ageMs: entry.age_ms,
    };

    // ⚠️ Quiet is checked BEFORE validity. A device that stopped reporting leaves
    // a last frame saying `valid: true` and it says so forever, so trusting the
    // flag first would render a dead leaf as a healthy clock.
    if (entry.quiet) {
        const seconds = Math.round(entry.age_ms / 1000);
        return {
            ...common,
            state: "stale",
            detail: `No status for ${seconds}s, so whatever the last fit said, it is no longer current.`,
            summary: `No status for ${seconds}s — the last fit is stale, whatever it said.`,
        };
    }

    // A hub publishes coherence, not a per-leaf fit, so `sync` is absent on it.
    // That is not a missing fit; it is a device of a different kind.
    if (valid === undefined) {
        return { ...UNKNOWN_CLOCK_FIT, ...common, state: "unknown" };
    }

    if (valid === true || valid === 1) {
        const parts = [residualLabel(residualRmsNs)];
        if (skewPpb !== null) parts.push(`skew ${skewPpb} ppb`);
        if (quality !== null) parts.push(`quality ${quality}`);
        if (beaconsMissedPerS !== null && beaconsMissedPerS > 0) {
            parts.push(`missing ${beaconsMissedPerS.toFixed(1)} beacons/s`);
        }
        return {
            ...common,
            state: "ok",
            detail: `${parts.join(", ")}.`,
            summary: `Clock fit held: ${parts.join(", ")}.`,
        };
    }

    return {
        ...common,
        state: "no_fit",
        detail:
            "This device's sample timestamps cannot be compared against another " +
            "device's until the hub holds a fit for it again.",
        summary:
            "The hub holds NO usable clock fit for this device — its samples' " +
            "timestamps cannot be compared against another device's.",
    };
}

/**
 * Short label for the badge.
 *
 * ⚠️ Kept SHORT deliberately. This sits in a node header 220px wide that also
 * carries the run state; "no clock fit" pushed that off the card edge. The dot's
 * colour and the title carry the rest, and the compact-node header is the wrong
 * place to explain anything.
 */
export function clockFitLabel(fit: ClockFit): string {
    switch (fit.state) {
        case "ok":
            // Nothing: a healthy clock is the case nobody needs telling about,
            // and the dot already says so.
            return "";
        case "no_fit":
            return "no fit";
        case "stale":
            return "stale";
        default:
            return "";
    }
}
