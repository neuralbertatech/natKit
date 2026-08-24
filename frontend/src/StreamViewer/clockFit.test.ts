import { describe, expect, it } from "vitest";
import type { DeviceHealthEntry, DeviceHealthMessage } from "./types";
import {
    clockFitForStream,
    clockFitLabel,
    RESIDUAL_SATURATED,
    UNKNOWN_CLOCK_FIT,
} from "./clockFit";

function health(devices: Partial<DeviceHealthEntry>[]): DeviceHealthMessage {
    return {
        type: "device_health",
        wall_ms: 1000,
        quiet_after_ms: 3000,
        topics_tailed: devices.length,
        devices: devices.map((d) => ({
            device_id: "1",
            role: "leaf",
            age_ms: 0,
            quiet: false,
            fields: {},
            rate_status: "available",
            rates: null,
            ...d,
        })) as DeviceHealthEntry[],
    };
}

const leaf = (over: Record<string, unknown> = {}, rest: Partial<DeviceHealthEntry> = {}) =>
    health([
        {
            device_id: "13793649670644",
            fields: {
                mac: "0c:8b:95:96:b9:f4",
                sync: { valid: true, quality: 2, residual_rms_ns: 45767, skew_ppb: 43265, ...over },
            },
            ...rest,
        },
    ]);


const leafFit = (over: Record<string, unknown> = {}, rest: Partial<DeviceHealthEntry> = {}) =>
    health([
        {
            device_id: "1",
            fields: {
                sync: { valid: true, quality: 2, residual_rms_ns: 45767, skew_ppb: 43265, ...over },
            },
            ...rest,
        },
    ]);

describe("clockFitForStream", () => {
    // ⚠️ Most streams legitimately have no status channel. A warning on every one
    // of them would train people to ignore the warning.
    it("is unknown, not a fault, when the device does not publish status", () => {
        const fit = clockFitForStream(leaf(), "999");
        expect(fit.state).toBe("unknown");
        expect(clockFitLabel(fit)).toBe("");
    });

    it("is unknown when nothing has been pushed at all", () => {
        expect(clockFitForStream(null, "13793649670644").state).toBe("unknown");
    });

    it("reads the fit for a matching stream id", () => {
        const fit = clockFitForStream(leaf(), "13793649670644");
        expect(fit.state).toBe("ok");
        expect(fit.quality).toBe(2);
        expect(fit.skewPpb).toBe(43265);
        expect(fit.summary).toContain("45.8 µs");
        expect(fit.summary).toContain("43265 ppb");
    });

    it("matches a numeric stream id against the string device id", () => {
        expect(clockFitForStream(leaf(), 13793649670644).state).toBe("ok");
    });

    it("reports no fit when the hub does not hold one", () => {
        const fit = clockFitForStream(leaf({ valid: false }), "13793649670644");
        expect(fit.state).toBe("no_fit");
        expect(fit.summary).toContain("NO usable clock fit");
    });

    // ⚠️ The trap: a silent device's last frame says valid:true forever, so
    // validity must not be trusted ahead of freshness.
    it("calls a silent device stale even though its last frame said valid", () => {
        const fit = clockFitForStream(
            leaf({ valid: true }, { quiet: true, age_ms: 42000 }),
            "13793649670644",
        );
        expect(fit.state).toBe("stale");
        expect(fit.summary).toContain("42s");
        // The last-known numbers are still carried — they are the evidence.
        expect(fit.quality).toBe(2);
    });

    // ⚠️ Saturation is 4.29 SECONDS, not a large-but-real residual: it means the
    // window's samples sit seconds off their own line (TEC-NATKIT-47).
    it("says a saturated residual is no usable fit rather than printing 4.29 s", () => {
        const fit = clockFitForStream(
            leaf({ residual_rms_ns: RESIDUAL_SATURATED }),
            "13793649670644",
        );
        expect(fit.summary).toContain("saturated");
        expect(fit.summary).not.toContain("4294967295");
    });

    it("scales a sub-microsecond residual in ns", () => {
        expect(
            clockFitForStream(leaf({ residual_rms_ns: 850 }), "13793649670644").summary,
        ).toContain("850 ns");
    });

    // The hub publishes coherence, not a per-leaf fit, so it has no `sync` object.
    // That is a device of a different kind, not a missing fit.
    it("does not call the hub broken for having no per-leaf fit", () => {
        const hub = health([
            { device_id: "203376942053180", role: "hub", fields: { nodes_known: 4 } },
        ]);
        const fit = clockFitForStream(hub, "203376942053180");
        expect(fit.state).toBe("unknown");
    });

    it("carries the beacon-loss rate when there is one, and omits it at zero", () => {
        const withLoss = clockFitForStream(
            health([
                {
                    device_id: "1",
                    fields: { sync: { valid: true, quality: 2, residual_rms_ns: 1000 } },
                    rates: { "sync.beacons_missed": 2.5 },
                },
            ]),
            "1",
        );
        expect(withLoss.beaconsMissedPerS).toBe(2.5);
        expect(withLoss.summary).toContain("2.5 beacons/s");

        const clean = clockFitForStream(
            health([
                {
                    device_id: "1",
                    fields: { sync: { valid: true, quality: 2, residual_rms_ns: 1000 } },
                    rates: { "sync.beacons_missed": 0 },
                },
            ]),
            "1",
        );
        expect(clean.summary).not.toContain("beacons/s");
    });
});

describe("clockFitLabel", () => {
    // ⚠️ These sit in a 220px node header that also carries the run state. Long
    // labels pushed it off the card edge, so the length is a constraint, not a
    // preference.
    it("is short, and empty for the healthy case", () => {
        expect(clockFitLabel({ ...UNKNOWN_CLOCK_FIT, state: "ok" })).toBe("");
        expect(clockFitLabel({ ...UNKNOWN_CLOCK_FIT, state: "unknown" })).toBe("");
        for (const state of ["no_fit", "stale"] as const) {
            const label = clockFitLabel({ ...UNKNOWN_CLOCK_FIT, state });
            expect(label.length).toBeGreaterThan(0);
            expect(label.length).toBeLessThanOrEqual(7);
        }
    });
});

describe("summary and detail", () => {
    // ⚠️ A caller that renders its own state line must not also print the state
    // in the detail — the inspector did, giving "Clock fit held" directly above
    // "Clock fit held: residual 46 µs…".
    it("keeps the state phrase out of the detail", () => {
        for (const fit of [
            clockFitForStream(leafFit({ valid: true }), "1"),
            clockFitForStream(leafFit({ valid: false }), "1"),
            clockFitForStream(leafFit({ valid: true }, { quiet: true, age_ms: 9000 }), "1"),
        ]) {
            expect(fit.summary.length).toBeGreaterThan(0);
            expect(fit.detail).not.toMatch(/^Clock fit held/);
            expect(fit.detail.length).toBeGreaterThan(0);
        }
    });

    it("has an empty detail when nothing is known", () => {
        expect(UNKNOWN_CLOCK_FIT.detail).toBe("");
    });
});

describe("a hub republishing a leaf it cannot hear", () => {
    // ⚠️ Observed on the rig: the hub composes each leaf's status frame from its
    // registry entry, so a leaf that falls off keeps having frames published about
    // it, once a second, forever — arriving fresh with every counter frozen.
    // `age_ms` is ~0, so quoting it would say "no status for 0s".
    const stale = health([
        {
            device_id: "1",
            age_ms: 0,
            unheard_ms: 41000,
            quiet: true,
            quiet_reason: "device_not_heard",
            fields: { sync: { valid: true, quality: 2, residual_rms_ns: 45767 } },
        },
    ]);

    it("says how long since the DEVICE was heard, not since the frame arrived", () => {
        const fit = clockFitForStream(stale, "1");
        expect(fit.state).toBe("stale");
        expect(fit.summary).toContain("41s");
        expect(fit.summary).not.toContain("0s");
        expect(fit.summary).toMatch(/republishing a stale entry/i);
    });

    it("still refuses to call the fit good, whatever the last frame said", () => {
        expect(clockFitForStream(stale, "1").state).not.toBe("ok");
    });
});
