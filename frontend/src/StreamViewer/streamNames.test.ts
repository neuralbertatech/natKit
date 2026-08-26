import { describe, expect, it } from "vitest";
import { streamDisplayName, streamNameParts } from "./streamNames";

const ID = "13793649671244";

describe("streamDisplayName", () => {
    it("shows the alias AND the id, never the alias alone", () => {
        // ⚠️ The id is what topics, recordings and log lines are keyed by.
        // Replacing it would make them unsearchable from the screen that named it.
        expect(streamDisplayName(ID, { [ID]: "Left Hand" })).toBe(
            `Left Hand (${ID})`,
        );
    });

    it("falls back to the bare id when nothing friendlier is known", () => {
        expect(streamDisplayName(ID)).toBe(ID);
    });

    it("prefers a human alias over the device's own name", () => {
        expect(
            streamDisplayName(ID, { [ID]: "Left Hand" }, { [ID]: "natKit-IMU" }),
        ).toBe(`Left Hand (${ID})`);
    });

    it("uses the device name when no alias is set", () => {
        expect(streamDisplayName(ID, {}, { [ID]: "natKit-IMU" })).toBe(
            `natKit-IMU (${ID})`,
        );
    });

    // ⚠️ "13793649671244 (13793649671244)" is worse than the bare number.
    it("ignores a device name that is just the id again", () => {
        expect(streamDisplayName(ID, {}, { [ID]: ID })).toBe(ID);
    });

    it("treats a whitespace-only alias as no alias", () => {
        expect(streamDisplayName(ID, { [ID]: "   " })).toBe(ID);
    });

    it("trims a padded alias rather than rendering the padding", () => {
        expect(streamDisplayName(ID, { [ID]: "  Trunk  " })).toBe(`Trunk (${ID})`);
    });

    it("accepts a numeric stream id", () => {
        expect(streamDisplayName(13793649671244, { [ID]: "Base" })).toBe(
            `Base (${ID})`,
        );
    });

    it("renders nothing for no stream, rather than the word undefined", () => {
        expect(streamDisplayName(null)).toBe("");
        expect(streamDisplayName(undefined)).toBe("");
    });
});

describe("streamNameParts", () => {
    it("reports where the name came from", () => {
        expect(streamNameParts(ID, { [ID]: "Left Hand" }).source).toBe("alias");
        expect(streamNameParts(ID, {}, { [ID]: "natKit-IMU" }).source).toBe("device");
        expect(streamNameParts(ID).source).toBe("none");
        expect(streamNameParts(ID).label).toBeNull();
    });
});
