// The controls a device says it can be asked to do (TEC-NATKIT-10).
//
// ⚠️ THIS FILE USED TO BE THE PROBLEM. It held a hardcoded catalogue —
// SOURCE_BUTTON_CONTROLS and SOURCE_TOGGLE_GROUPS — shown for any node of kind
// stream_source, so a Muse headband or an EMG pill rendered four BNO08x report
// toggles it does not have, and "Read from device" sat there until it timed out.
//
// Nothing is declared here now. Every control comes from the device's own
// advertisement on its Configuration channel, resolved by the backend against a
// registry a third-party library can inject into. Adding a device means
// registering descriptors on the server, not editing this file.

/** One control, as the backend forwards it from the device's advertisement. */
export interface DeviceControl {
    id: string;
    kind: "button" | "toggle" | "input";
    /** The command that acts. For a button, this IS the action. */
    write: string;
    /** The command that reads state. Absent for a button — nothing to read. */
    read?: string;
    /** Controls read together share a group. */
    group?: string;
    /** The args key on the wire, e.g. "accel", "quarter_dbm". */
    field?: string;
    /** A FieldValueType name. */
    type?: string;
    min?: number;
    max?: number;
    /**
     * Resolved from the registry server-side.
     *
     * ⚠️ ABSENT means no library described this id. The UI must render the raw
     * id rather than invent a label — a control that silently disappears is
     * indistinguishable from a device that does not have it, which turns "you
     * did not load the library" into a hardware-looking bug.
     */
    label?: string;
    description?: string;
    unit?: string;
}

/** What the backend knows about one device's controls and reachability. */
export interface DeviceControlsEntry {
    device_id: string;
    controls: DeviceControl[];
    /**
     * ⚠️ NOT the same as `controls` being empty. "Never advertised" (firmware
     * predating the channel) and "advertised nothing" are different states and
     * need different words on screen.
     */
    has_advertisement: boolean;
    reachable: boolean;
    since_heartbeat_ms: number;
    /** Present only when a bridge advertised on this device's behalf. */
    advertised_by?: string;
}

export type ControlsAvailability =
    /** Advertised and reachable: controls are live. */
    | "live"
    /** Advertised, but no heartbeat inside the window. */
    | "unreachable"
    /** The device has never advertised — older firmware. */
    | "unadvertised"
    /** It advertised, and advertised nothing. */
    | "none";

export interface ResolvedControls {
    availability: ControlsAvailability;
    buttons: DeviceControl[];
    inputs: DeviceControl[];
    /** Toggles bundled by their group, in advertisement order. */
    toggleGroups: { group: string; read?: string; toggles: DeviceControl[] }[];
    /** Why controls cannot be used, or null when they can. */
    reason: string | null;
}

/** The words for a control: the registry's, the device's, or its raw id. */
export function controlLabel(control: DeviceControl): string {
    return control.label && control.label.length > 0 ? control.label : control.id;
}

/**
 * Resolve one device's entry into what the inspector should draw.
 *
 * ⚠️ Returns the controls even when the device is UNREACHABLE. They are drawn
 * disabled with a reason rather than hidden: a control that vanishes when a
 * board goes quiet is indistinguishable from a board that never had it, and the
 * operator loses the one piece of information that would tell them which end of
 * the rig to go and look at.
 */
export function resolveControls(
    entry: DeviceControlsEntry | null | undefined,
): ResolvedControls {
    const empty: ResolvedControls = {
        availability: "unadvertised",
        buttons: [],
        inputs: [],
        toggleGroups: [],
        reason:
            "This device has not said what it supports. Its firmware may predate " +
            "the control channel.",
    };
    if (!entry || !entry.has_advertisement) return empty;

    const controls = entry.controls ?? [];
    if (controls.length === 0) {
        return {
            ...empty,
            availability: "none",
            reason: "This device advertises no controls.",
        };
    }

    const buttons = controls.filter((c) => c.kind === "button");
    const inputs = controls.filter((c) => c.kind === "input");

    // Grouped in advertisement order, so the device decides the ordering rather
    // than a sort here inventing one.
    const toggleGroups: ResolvedControls["toggleGroups"] = [];
    for (const control of controls) {
        if (control.kind !== "toggle") continue;
        const group = control.group ?? control.id;
        let bucket = toggleGroups.find((g) => g.group === group);
        if (!bucket) {
            bucket = { group, read: control.read, toggles: [] };
            toggleGroups.push(bucket);
        }
        bucket.toggles.push(control);
    }

    const unreachable = !entry.reachable;
    return {
        availability: unreachable ? "unreachable" : "live",
        buttons,
        inputs,
        toggleGroups,
        reason: unreachable
            ? "This device is not currently reachable — no heartbeat. It " +
              "advertises these controls, so this is power or radio rather than " +
              "firmware."
            : null,
    };
}

/**
 * Parse a toggle group's state out of the device's answer, e.g.
 * `"accel=1 gyro=1 mag=0 rotation=1"`.
 *
 * ⚠️ Parsed from prose because the answer travels on the device LOG channel,
 * whose records are a human-readable message by design — the same channel a
 * person reads when asking why a node is quiet.
 *
 * ⚠️ ALL-OR-NOTHING: a message missing any toggle returns null rather than a
 * partial map. Half an answer would render some switches from the device and the
 * rest from nothing, which on screen is indistinguishable from a device that
 * really has them off.
 */
export function parseToggleStates(
    toggles: readonly DeviceControl[],
    message: string,
): Record<string, boolean> | null {
    const found: Record<string, boolean> = {};
    for (const toggle of toggles) {
        const key = toggle.field ?? toggle.id;
        // \b so a key cannot match inside a longer word ("xmag=1" is not "mag").
        const match = message.match(new RegExp(`\\b${key}=([01])\\b`));
        if (!match) return null;
        found[key] = match[1] === "1";
    }
    return found;
}

/** True if `command` is one whose answer carries this group's state. */
export function answerCarriesGroupState(
    group: { read?: string; toggles: readonly DeviceControl[] },
    command: string | undefined,
): boolean {
    if (!command) return false;
    if (group.read && command === group.read) return true;
    return group.toggles.some((toggle) => toggle.write === command);
}

/** The args that flip one toggle — only the changed field, never the whole mask. */
export function writeArgsFor(
    toggle: DeviceControl,
    current: Record<string, boolean>,
): Record<string, boolean> {
    const key = toggle.field ?? toggle.id;
    return { [key]: !current[key] };
}
