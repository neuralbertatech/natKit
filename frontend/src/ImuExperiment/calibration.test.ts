import { describe, expect, it } from "vitest";

import {
    CalibrationStatus,
    calibration_status_for_accuracies,
    sensorIsReporting,
    type SensorAccuracies,
} from "./util";

// The headline is the WORST case across sub-sensors, which is what makes a
// silent sensor dangerous: it reads 0, 0 means Unreliable, and one of those
// drags a perfectly calibrated device down with it. These pin the distinction
// between "off" and "on and badly calibrated", which the accuracy number alone
// cannot express.
describe("calibration_status_for_accuracies", () => {
    it("excludes a sensor that is not reporting from the worst case", () => {
        const accuracies: SensorAccuracies = {
            accelerometer: 3,
            gyroscope: 3,
            rotation: 3,
            // Reads 0 because it is switched off, NOT because it is uncalibrated.
            magnetometer: 0,
            reporting: {
                accelerometer: true,
                gyroscope: true,
                rotation: true,
                magnetometer: false,
            },
        };

        expect(calibration_status_for_accuracies(accuracies)).toBe(
            CalibrationStatus.High,
        );
    });

    it("counts a reporting sensor that is genuinely uncalibrated", () => {
        const accuracies: SensorAccuracies = {
            accelerometer: 3,
            gyroscope: 3,
            rotation: 3,
            magnetometer: 0,
            reporting: {
                accelerometer: true,
                gyroscope: true,
                rotation: true,
                // Same 0 as above, but the sensor IS on — so it counts.
                magnetometer: true,
            },
        };

        expect(calibration_status_for_accuracies(accuracies)).toBe(
            CalibrationStatus.Unreliable,
        );
    });

    it("counts the magnetometer, which was previously invisible", () => {
        const accuracies: SensorAccuracies = {
            accelerometer: 3,
            gyroscope: 3,
            rotation: 3,
            magnetometer: 1,
            reporting: {
                accelerometer: true,
                gyroscope: true,
                rotation: true,
                magnetometer: true,
            },
        };

        expect(calibration_status_for_accuracies(accuracies)).toBe(
            CalibrationStatus.Low,
        );
    });

    // ⚠️ An older backend sends no `reporting` at all. Treating that as "nothing
    // is reporting" would blank every panel; treating it as "everything is"
    // reproduces the previous behaviour exactly.
    it("falls back to counting everything when the backend does not say", () => {
        const accuracies = {
            accelerometer: 3,
            gyroscope: 0,
            rotation: 3,
        } as SensorAccuracies;

        expect(calibration_status_for_accuracies(accuracies)).toBe(
            CalibrationStatus.Unreliable,
        );
    });

    it("ignores a magnetometer a v1 frame never had", () => {
        // No `magnetometer` key at all: the frame format predates it, so there
        // is no reading to be bad.
        const accuracies = {
            accelerometer: 3,
            gyroscope: 3,
            rotation: 3,
        } as SensorAccuracies;

        expect(sensorIsReporting(accuracies, "magnetometer")).toBe(false);
        expect(calibration_status_for_accuracies(accuracies)).toBe(
            CalibrationStatus.High,
        );
    });
});
