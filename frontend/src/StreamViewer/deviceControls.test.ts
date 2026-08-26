import { describe, expect, it } from "vitest";
import {
    answerCarriesGroupState,
    controlLabel,
    parseToggleStates,
    resolveControls,
    writeArgsFor,
    type DeviceControl,
    type DeviceControlsEntry,
} from "./deviceControls";

const btn = (id: string, label?: string): DeviceControl => ({
    id, kind: "button", write: id, label,
});
const tog = (id: string, field: string, label?: string): DeviceControl => ({
    id, kind: "toggle", write: "set_reports", read: "get_reports",
    group: "reports", field, type: "bool", label,
});
const inp = (id: string): DeviceControl => ({
    id, kind: "input", write: "set_tx_power", read: "get_tx_power",
    field: "quarter_dbm", type: "int16", min: 8, max: 80, label: "Transmit power",
});

const entry = (over: Partial<DeviceControlsEntry> = {}): DeviceControlsEntry => ({
    device_id: "13793649671244",
    controls: [btn("identify", "Identify"), tog("reports.accel", "accel", "Accelerometer"),
               tog("reports.gyro", "gyro", "Gyroscope"), inp("tx_power")],
    has_advertisement: true,
    reachable: true,
    since_heartbeat_ms: 400,
    ...over,
});

describe("resolveControls", () => {
    it("splits an advertisement into buttons, grouped toggles and inputs", () => {
        const r = resolveControls(entry());
        expect(r.availability).toBe("live");
        expect(r.reason).toBeNull();
        expect(r.buttons.map((c) => c.id)).toEqual(["identify"]);
        expect(r.inputs.map((c) => c.id)).toEqual(["tx_power"]);
        expect(r.toggleGroups).toHaveLength(1);
        expect(r.toggleGroups[0].group).toBe("reports");
        expect(r.toggleGroups[0].read).toBe("get_reports");
        expect(r.toggleGroups[0].toggles.map((c) => c.id)).toEqual([
            "reports.accel", "reports.gyro",
        ]);
    });

    // ⚠️ THE BUG THIS WHOLE FEATURE EXISTS TO FIX. A device that never advertised
    // gets NO controls — not a default set of IMU toggles it may not have.
    it("offers nothing for a device that has never advertised", () => {
        const r = resolveControls(entry({ has_advertisement: false, controls: [] }));
        expect(r.availability).toBe("unadvertised");
        expect(r.buttons).toEqual([]);
        expect(r.toggleGroups).toEqual([]);
        expect(r.reason).toMatch(/predate/);
    });

    it("says nothing at all for a null entry", () => {
        expect(resolveControls(null).availability).toBe("unadvertised");
        expect(resolveControls(undefined).buttons).toEqual([]);
    });

    // ⚠️ "Advertised nothing" is NOT "never advertised" — different words.
    it("distinguishes a device that advertised an empty set", () => {
        const r = resolveControls(entry({ controls: [] }));
        expect(r.availability).toBe("none");
        expect(r.reason).toMatch(/advertises no controls/);
        expect(r.reason).not.toMatch(/predate/);
    });

    // ⚠️ Still returned, so the inspector can grey them WITH a reason. Hiding
    // them would be indistinguishable from a board that never had them, and the
    // operator would lose the one clue about which end of the rig to check.
    it("keeps the controls when the device is unreachable, with a reason", () => {
        const r = resolveControls(entry({ reachable: false }));
        expect(r.availability).toBe("unreachable");
        expect(r.buttons).toHaveLength(1);
        expect(r.toggleGroups[0].toggles).toHaveLength(2);
        expect(r.reason).toMatch(/power or radio rather than firmware/);
    });

    it("keeps the device's ordering rather than sorting", () => {
        const r = resolveControls(entry({
            controls: [tog("reports.rotation", "rotation"), tog("reports.accel", "accel")],
        }));
        expect(r.toggleGroups[0].toggles.map((c) => c.field)).toEqual([
            "rotation", "accel",
        ]);
    });

    it("gives an ungrouped toggle a group of its own", () => {
        const lone: DeviceControl = { id: "solo", kind: "toggle", write: "set_solo", field: "on" };
        const r = resolveControls(entry({ controls: [lone] }));
        expect(r.toggleGroups).toHaveLength(1);
        expect(r.toggleGroups[0].group).toBe("solo");
    });
});

describe("controlLabel", () => {
    it("prefers the resolved label", () => {
        expect(controlLabel(btn("identify", "Identify"))).toBe("Identify");
    });

    // ⚠️ An id nobody described renders as its RAW ID. Inventing a label would
    // hide that a library is missing; hiding the control would look like broken
    // hardware.
    it("falls back to the raw id when no library described it", () => {
        expect(controlLabel(btn("acme.valve"))).toBe("acme.valve");
    });
});

describe("parseToggleStates", () => {
    const toggles = [tog("reports.accel", "accel"), tog("reports.gyro", "gyro")];

    it("reads the device's own answer format", () => {
        expect(parseToggleStates(toggles, "accel=1 gyro=0")).toEqual({
            accel: true, gyro: false,
        });
    });

    it("returns null when any toggle is missing, never a partial map", () => {
        expect(parseToggleStates(toggles, "accel=1")).toBeNull();
        expect(parseToggleStates(toggles, "unrecognised command")).toBeNull();
    });

    it("will not match a key inside a longer word", () => {
        expect(parseToggleStates([tog("reports.mag", "mag")], "xmag=1")).toBeNull();
    });

    it("keys on the wire field, not the control id", () => {
        // The id is "reports.accel"; the args key is "accel". Keying on the id
        // would never match anything the device says.
        expect(parseToggleStates([tog("reports.accel", "accel")], "accel=1")).toEqual({
            accel: true,
        });
    });
});

describe("answerCarriesGroupState", () => {
    const group = { read: "get_reports", toggles: [tog("reports.accel", "accel")] };

    it("accepts the group's read command", () => {
        expect(answerCarriesGroupState(group, "get_reports")).toBe(true);
    });

    // ⚠️ A refusal still reports the CURRENT state, so a write's answer is just
    // as authoritative as a read's — confirmed against a board 2026-08-26.
    it("accepts a toggle's write command too", () => {
        expect(answerCarriesGroupState(group, "set_reports")).toBe(true);
    });

    it("ignores answers to other commands", () => {
        expect(answerCarriesGroupState(group, "identify")).toBe(false);
        expect(answerCarriesGroupState(group, undefined)).toBe(false);
    });
});

describe("writeArgsFor", () => {
    it("sends only the toggle being flipped, keyed on its wire field", () => {
        expect(writeArgsFor(tog("reports.mag", "mag"), { mag: false, accel: true }))
            .toEqual({ mag: true });
    });
});
