import { describe, expect, it } from "vitest";

import {
    ASSIGNABLE_SENSOR_POSITIONS,
    CALIBRATION_MINIMUM,
    SENSOR_POSITION_NAMES,
    duplicatePositions,
    isAssignedPosition,
    meetsCalibrationMinimum,
} from "./sensorPositions";

describe("sensor positions", () => {
    it("offers every placement plus an explicit not-stated", () => {
        expect(SENSOR_POSITION_NAMES).toContain("N/A");
        expect(ASSIGNABLE_SENSOR_POSITIONS).not.toContain("N/A");
        expect(ASSIGNABLE_SENSOR_POSITIONS).toHaveLength(
            SENSOR_POSITION_NAMES.length - 1,
        );
    });

    it("covers the eight the IMU ADL template lays out", () => {
        // The template drops one stream node per placement, so a missing name
        // here is a node the operator cannot map.
        for (const position of [
            "Left Hand", "Right Hand",
            "Left Forearm", "Right Forearm",
            "Left Shoulder", "Right Shoulder",
            "Trunk", "Base",
        ]) {
            expect(ASSIGNABLE_SENSOR_POSITIONS).toContain(position);
        }
    });

    // ⚠️ The template does not use these, and they are kept anyway. A position
    // name is written into a recording's `sensor_positions` and into live board
    // configs, so deleting one orphans every reference and renders as a value the
    // dropdown can no longer offer. Adding is free; removing is a migration.
    it("keeps the upper arms even though the ADL template does not use them", () => {
        expect(ASSIGNABLE_SENSOR_POSITIONS).toContain("Left Upper Arm");
        expect(ASSIGNABLE_SENSOR_POSITIONS).toContain("Right Upper Arm");
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

describe("the Record gate's calibration minimum", () => {
    it("is Medium — named, not guessed", () => {
        // CalibrationStatus: Unknown 0, Unreliable 1, Low 2, Medium 3, High 4.
        expect(CALIBRATION_MINIMUM).toBe(3);
    });

    it("passes Medium and High, refuses Low and Unreliable", () => {
        expect(meetsCalibrationMinimum(4)).toBe(true);
        expect(meetsCalibrationMinimum(3)).toBe(true);
        expect(meetsCalibrationMinimum(2)).toBe(false);
        expect(meetsCalibrationMinimum(1)).toBe(false);
    });

    it("⚠️ refuses Unknown, and refuses a missing reading the same way", () => {
        // A missing reading and a bad reading are the same thing to a gate: nothing
        // has said this sensor is trustworthy. Treating Unknown as "probably fine"
        // is how a rig with no accuracy feed records a whole cohort unchecked.
        expect(meetsCalibrationMinimum(0)).toBe(false);
        expect(meetsCalibrationMinimum(undefined)).toBe(false);
    });
});
