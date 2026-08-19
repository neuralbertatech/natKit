export enum SensorPosition {
    None = 0,
    LeftForearm,
    RightForearm,
    LeftUpperArm,
    RightUpperArm,
    LeftShoulder,
    RightShoulder,
    Trunk,
}

export enum CalibrationStatus {
    Unknown = 0,
    Unreliable = 1,
    Low,
    Medium,
    High,
}

export function sensor_position_to_string(position: SensorPosition) {
    switch (position) {
        case SensorPosition.LeftForearm:
            return "Left Forearm";
        case SensorPosition.RightForearm:
            return "Right Forearm";
        case SensorPosition.LeftUpperArm:
            return "Left Upper Arm";
        case SensorPosition.RightUpperArm:
            return "Right Upper Arm";
        case SensorPosition.LeftShoulder:
            return "Left Shoulder";
        case SensorPosition.RightShoulder:
            return "Right Shoulder";
        case SensorPosition.Trunk:
            return "Trunk";
        case SensorPosition.None:
            return "N/A";
    }
}

export function parse_sensor_position_from_string(str: string) {
    switch (str) {
        case "Left Forearm":
            return SensorPosition.LeftForearm;
        case "Right Forearm":
            return SensorPosition.RightForearm;
        case "Left Upper Arm":
            return SensorPosition.LeftUpperArm;
        case "Right Upper Arm":
            return SensorPosition.RightUpperArm;
        case "Left Shoulder":
            return SensorPosition.LeftShoulder;
        case "Right Shoulder":
            return SensorPosition.RightShoulder;
        case "Trunk":
            return SensorPosition.Trunk;
        default:
            return SensorPosition.None;
    }
}

// --- Shared calibration helpers -------------------------------------------
// The BNO08x reports an accuracy of 0-3 per sub-sensor. These were previously
// private to Calibration.svelte; they are exported so the Visual Programming
// calibration node reports status identically rather than reimplementing the
// mapping (two definitions of "is this sensor calibrated" is one too many).

export interface SensorAccuracies {
    accelerometer: number;
    gyroscope: number;
    rotation: number;
}

export function accuracy_int_to_calibration_status(
    val: number,
): CalibrationStatus {
    if (val === 0) return CalibrationStatus.Unreliable;
    if (val === 1) return CalibrationStatus.Low;
    if (val === 2) return CalibrationStatus.Medium;
    if (val === 3) return CalibrationStatus.High;
    return CalibrationStatus.Unknown;
}

/** Worst case across sub-sensors: a good accelerometer cannot rescue a bad gyro. */
export function min_calibration_status(
    statuses: CalibrationStatus[],
): CalibrationStatus {
    const known = statuses.filter((s) => s !== CalibrationStatus.Unknown);
    if (known.length === 0) return CalibrationStatus.Unknown;
    return known.reduce((worst, s) => (s < worst ? s : worst), known[0]);
}

export function calibration_status_to_string(status: CalibrationStatus) {
    switch (status) {
        case CalibrationStatus.Unreliable:
            return "Unreliable";
        case CalibrationStatus.Low:
            return "Low";
        case CalibrationStatus.Medium:
            return "Medium";
        case CalibrationStatus.High:
            return "High";
        default:
            return "Unknown";
    }
}

/** CSS-friendly class name, matching the IMU Experiment tab's colour language. */
export function calibration_status_to_color(status: CalibrationStatus) {
    switch (status) {
        case CalibrationStatus.Unreliable:
            return "gray";
        case CalibrationStatus.Low:
            return "red";
        case CalibrationStatus.Medium:
            return "yellow";
        case CalibrationStatus.High:
            return "green";
        default:
            return "faded";
    }
}

/** Overall status for one stream, from whatever shape the API returned. */
export function calibration_status_for_accuracies(
    raw: unknown,
): CalibrationStatus {
    if (
        typeof raw === "object" &&
        raw !== null &&
        "accelerometer" in raw &&
        "gyroscope" in raw &&
        "rotation" in raw
    ) {
        const a = raw as SensorAccuracies;
        return min_calibration_status([
            accuracy_int_to_calibration_status(Number(a.accelerometer ?? 0)),
            accuracy_int_to_calibration_status(Number(a.gyroscope ?? 0)),
            accuracy_int_to_calibration_status(Number(a.rotation ?? 0)),
        ]);
    }
    if (raw === undefined || raw === null) return CalibrationStatus.Unknown;
    return accuracy_int_to_calibration_status(Number(raw));
}

// Re-exported: the canonical list moved to StreamViewer/sensorPositions.ts so
// retiring this page (TEC-NATKIT-61) cannot take the enumeration with it. Kept as
// a re-export rather than updating this page's imports, because the page is a
// rollback path and should not be churned.
export {
    SENSOR_POSITION_NAMES,
    type SensorPositionName,
} from "../StreamViewer/sensorPositions";
