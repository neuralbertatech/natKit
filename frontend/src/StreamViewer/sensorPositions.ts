// Body positions an IMU can be worn at — the canonical list.
//
// This lived in `ImuExperiment/util.ts`, inside one of the standalone pages that
// TEC-NATKIT-61 will retire, and Visual Programming imported it from there. Moved
// so retirement cannot take the enumeration with it; the old page re-exports this
// so nothing there has to change (TEC-NATKIT-62).
//
// ⚠️ These are STRINGS, and they are what ends up in a recorded run's position
// mapping. Renaming one silently orphans the mapping of every run already
// recorded, which is why they are written out rather than derived from a prettier
// enum: the wire format IS the label.
export const SENSOR_POSITION_NAMES = [
    "N/A",
    // Distal to proximal down each arm, then the body, then the reference. The
    // order is the order the dropdown shows, so it reads like an arm rather than
    // like the order features were added.
    "Left Hand",
    "Right Hand",
    "Left Forearm",
    "Right Forearm",
    "Left Upper Arm",
    "Right Upper Arm",
    "Left Shoulder",
    "Right Shoulder",
    "Trunk",
    // ⚠️ Not worn. The stationary reference sensor every other position is
    // measured against; a rig without one has no way to separate the
    // participant's motion from the room's.
    "Base",
] as const;

// ⚠️ THE UPPER ARMS ARE KEPT DELIBERATELY. The IMU ADL template does not use
// them, but a position name is written into a recording's `sensor_positions` and
// into live board configs — so removing one orphans every reference to it, and
// the value would render as a position the dropdown can no longer offer. Checked
// 2026-08-26: no sealed instance uses them, but two live boards do. Adding is
// free; removing is a migration.

export type SensorPositionName = (typeof SENSOR_POSITION_NAMES)[number];

/** "N/A" means "not stated", and is the only value allowed to repeat. */
export const UNASSIGNED_POSITION: SensorPositionName = "N/A";

/** Every real position, i.e. everything a completeness check should care about. */
export const ASSIGNABLE_SENSOR_POSITIONS = SENSOR_POSITION_NAMES.filter(
    (name) => name !== UNASSIGNED_POSITION,
);

export function isAssignedPosition(
    position: string | undefined | null,
): position is SensorPositionName {
    return (
        typeof position === "string" &&
        position.length > 0 &&
        position !== UNASSIGNED_POSITION
    );
}

/**
 * Which positions are claimed by more than one stream.
 *
 * ⚠️ The error this exists to catch is a swapped left/right forearm, which is
 * INVISIBLE in the data and cannot be corrected afterwards without knowing it
 * happened. A duplicate is the one form of it that a machine can see, so it is
 * worth refusing rather than warning about.
 */
export function duplicatePositions(
    positions: (string | undefined | null)[],
): SensorPositionName[] {
    const seen = new Map<string, number>();
    for (const position of positions) {
        if (!isAssignedPosition(position)) continue;
        seen.set(position, (seen.get(position) ?? 0) + 1);
    }
    return [...seen.entries()]
        .filter(([, count]) => count > 1)
        .map(([position]) => position as SensorPositionName);
}

// --- The Record gate's calibration threshold (TEC-NATKIT-63) ---------------
//
// `CalibrationStatus` runs Unknown(0) / Unreliable(1) / Low(2) / Medium(3) /
// High(4). The minimum a run must clear is a DECISION, not a constant to guess at,
// so it is named here with its reasoning rather than buried in a comparison:
//
// **Medium.** Below that the BNO08x's own fusion is telling you it does not trust
// its own orientation, and an ADL study's whole signal is limb orientation over a
// 10-15 s window. Requiring High would be stricter than the hardware reliably
// reaches while worn — the magnetometer in particular sits at Medium indoors — so
// it would make the gate something operators route around rather than satisfy,
// which is worse than a threshold slightly too low.
export const CALIBRATION_MINIMUM = 3; // CalibrationStatus.Medium

// Unknown(0) is deliberately NOT treated as "probably fine". A missing reading and
// a bad reading are the same thing to a gate: nothing has said this sensor is
// trustworthy. It stays overridable, because "no calibration data available" is a
// rig-configuration state an operator may legitimately need to record through.
export function meetsCalibrationMinimum(status: number | undefined): boolean {
    return typeof status === "number" && status >= CALIBRATION_MINIMUM;
}
