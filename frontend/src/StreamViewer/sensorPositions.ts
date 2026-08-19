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
    "Left Forearm",
    "Right Forearm",
    "Left Upper Arm",
    "Right Upper Arm",
    "Left Shoulder",
    "Right Shoulder",
    "Trunk",
] as const;

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
