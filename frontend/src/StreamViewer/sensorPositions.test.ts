import { describe, expect, it } from "vitest";

import {
    ASSIGNABLE_SENSOR_POSITIONS,
    SENSOR_POSITION_NAMES,
    duplicatePositions,
    isAssignedPosition,
} from "./sensorPositions";

describe("sensor positions", () => {
    it("offers the seven body positions plus an explicit not-stated", () => {
        // The seven are the ADL study's sensor set; "N/A" is not one of them.
        expect(ASSIGNABLE_SENSOR_POSITIONS).toHaveLength(7);
        expect(SENSOR_POSITION_NAMES).toHaveLength(8);
        expect(SENSOR_POSITION_NAMES).toContain("N/A");
        expect(ASSIGNABLE_SENSOR_POSITIONS).not.toContain("N/A");
    });

    it("treats absent, empty and N/A alike as not stated", () => {
        // Three ways of saying nothing arrive from three places: a node created
        // before the field existed (undefined), a cleared select (""), and the
        // explicit option ("N/A"). Any of them counting as a placement would let an
        // unmapped sensor pass a completeness check.
        expect(isAssignedPosition(undefined)).toBe(false);
        expect(isAssignedPosition(null)).toBe(false);
        expect(isAssignedPosition("")).toBe(false);
        expect(isAssignedPosition("N/A")).toBe(false);
        expect(isAssignedPosition("Left Forearm")).toBe(true);
    });

    it("finds a limb claimed by two sensors", () => {
        expect(
            duplicatePositions(["Left Forearm", "Trunk", "Left Forearm"]),
        ).toEqual(["Left Forearm"]);
    });

    it("does NOT report N/A as a duplicate, however many are unset", () => {
        // ⚠️ The whole point: unset sensors are a completeness problem, not a
        // conflict. Reporting them as clashing would make the real clash — a
        // swapped left/right — impossible to see among the noise.
        expect(duplicatePositions(["N/A", "N/A", "", undefined])).toEqual([]);
    });

    it("reports each duplicated limb once, and several at a time", () => {
        expect(
            duplicatePositions([
                "Left Forearm",
                "Left Forearm",
                "Left Forearm",
                "Trunk",
                "Trunk",
            ]).sort(),
        ).toEqual(["Left Forearm", "Trunk"]);
    });

    it("says nothing about a correct full seven-sensor mapping", () => {
        expect(duplicatePositions([...ASSIGNABLE_SENSOR_POSITIONS])).toEqual([]);
    });
});
