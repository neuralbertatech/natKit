import { describe, expect, it } from "vitest";
import {
    REPORTS_GROUP,
    IDENTIFY_CONTROL,
    SOURCE_BUTTON_CONTROLS,
    SOURCE_TOGGLE_GROUPS,
    answerCarriesGroupState,
    parseToggleStates,
    writeArgsFor,
} from "./deviceControls";

describe("the catalogue", () => {
    it("exposes Identify as a button", () => {
        expect(IDENTIFY_CONTROL.kind).toBe("button");
        expect(IDENTIFY_CONTROL.command).toBe("identify");
        expect(SOURCE_BUTTON_CONTROLS).toContain(IDENTIFY_CONTROL);
    });

    it("exposes exactly the four BNO08x reports as toggles", () => {
        expect(SOURCE_TOGGLE_GROUPS).toContain(REPORTS_GROUP);
        expect(REPORTS_GROUP.toggles.map((t) => t.id)).toEqual([
            "accel",
            "gyro",
            "mag",
            "rotation",
        ]);
    });
});

describe("parseToggleStates", () => {
    it("reads the device's own answer format", () => {
        expect(parseToggleStates(REPORTS_GROUP, "accel=1 gyro=1 mag=0 rotation=1"))
            .toEqual({ accel: true, gyro: true, mag: false, rotation: true });
    });

    it("does not care about order or surrounding prose", () => {
        expect(
            parseToggleStates(
                REPORTS_GROUP,
                "reports now: rotation=0 mag=1 gyro=0 accel=1 (saved)",
            ),
        ).toEqual({ accel: true, gyro: false, mag: true, rotation: false });
    });

    // ⚠️ The case that matters. A partial map would render some switches from the
    // device and the rest from nothing, which on screen is indistinguishable from
    // a device that really has them off.
    it("returns null when ANY toggle is missing, never a partial map", () => {
        expect(parseToggleStates(REPORTS_GROUP, "accel=1 gyro=1 mag=0")).toBeNull();
        expect(parseToggleStates(REPORTS_GROUP, "unrecognised command")).toBeNull();
        expect(parseToggleStates(REPORTS_GROUP, "")).toBeNull();
    });

    it("will not match a key inside a longer word", () => {
        expect(
            parseToggleStates(REPORTS_GROUP, "xmag=1 accel=1 gyro=1 rotation=1"),
        ).toBeNull();
    });

    it("rejects a non-binary value rather than coercing it", () => {
        expect(
            parseToggleStates(REPORTS_GROUP, "accel=2 gyro=1 mag=0 rotation=1"),
        ).toBeNull();
    });
});

describe("answerCarriesGroupState", () => {
    it("accepts both the read and the write command", () => {
        // A refusal still reports the CURRENT state, so a set_reports answer is
        // just as authoritative as a get_reports one.
        expect(answerCarriesGroupState(REPORTS_GROUP, "get_reports")).toBe(true);
        expect(answerCarriesGroupState(REPORTS_GROUP, "set_reports")).toBe(true);
    });

    it("ignores answers to other commands", () => {
        expect(answerCarriesGroupState(REPORTS_GROUP, "identify")).toBe(false);
        expect(answerCarriesGroupState(REPORTS_GROUP, undefined)).toBe(false);
    });
});

describe("writeArgsFor", () => {
    // ⚠️ Only the changed field. The device starts from its current mask, so two
    // toggles in flight cannot clobber each other.
    it("sends only the toggle being flipped", () => {
        const current = { accel: true, gyro: true, mag: false, rotation: true };
        expect(writeArgsFor(REPORTS_GROUP.toggles[2], current)).toEqual({ mag: true });
        expect(writeArgsFor(REPORTS_GROUP.toggles[0], current)).toEqual({ accel: false });
    });
});
