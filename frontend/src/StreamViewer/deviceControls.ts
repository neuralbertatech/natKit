// The controls a node exposes for the DEVICE behind it (TEC-NATKIT-99 / -40).
//
// A stream_source stands for a physical board, and some questions only the board
// can answer or act on. This declares those as data — a button, or a toggle —
// so the inspector renders a catalogue rather than hand-written markup per
// control, and adding the next one is an entry here.
//
// ⚠️ THE TRUTH COMES FROM THE DEVICE, NOT FROM THE DATA. This is the constraint
// that shapes the whole toggle design, and it is not obvious: a disabled sensor
// and one that simply has not reported yet are IDENTICAL in a frame — both are
// zeroed with a clear has_data bit. A control driven off the samples would show
// "waiting" forever for something deliberately switched off. So a toggle has no
// state until the device has been asked, and `null` is a real, displayable state
// rather than a default of "off".

/** A control that performs a one-shot action on the device. */
export interface ButtonControl {
    kind: "button";
    id: string;
    label: string;
    /** Shown while the command is in flight. */
    pendingLabel: string;
    title: string;
    command: string;
    args?: Record<string, unknown>;
}

/** One switch within a toggle group. */
export interface ToggleSpec {
    /** The field name ON THE WIRE, e.g. "accel" — also the key sent to write it. */
    id: string;
    label: string;
}

/**
 * A set of switches that are READ TOGETHER and WRITTEN ONE AT A TIME.
 *
 * ⚠️ The asymmetry is deliberate and is what makes concurrent toggling safe: the
 * device starts from its current mask and applies only the field it was sent, so
 * two toggles in flight cannot clobber each other and a write can never
 * accidentally reset the others.
 */
export interface ToggleGroupSpec {
    id: string;
    /** Reads the state of every toggle in the group. */
    readCommand: string;
    /** Writes exactly one toggle. */
    writeCommand: string;
    readLabel: string;
    toggles: readonly ToggleSpec[];
    /** Shown under the group once its state is known. */
    note: string;
    /** Shown when the group has never been read. */
    unknownNote: string;
}

export const IDENTIFY_CONTROL: ButtonControl = {
    kind: "button",
    id: "identify",
    label: "Identify",
    pendingLabel: "Flashing…",
    title: "Flash this board's LED so you can see which one on the bench it is",
    command: "identify",
};

export const REPORTS_GROUP: ToggleGroupSpec = {
    id: "reports",
    readCommand: "get_reports",
    writeCommand: "set_reports",
    readLabel: "Read from device",
    toggles: [
        { id: "accel", label: "Accelerometer" },
        { id: "gyro", label: "Gyroscope" },
        { id: "mag", label: "Magnetometer" },
        { id: "rotation", label: "Rotation" },
    ],
    // ⚠️ Said out loud because the obvious assumption is wrong and would
    // otherwise be made silently: the hub delivers its reports in bursts at
    // ~88 Hz regardless of how many are enabled (TEC-NATKIT-41).
    note:
        "Turning a report off does not speed the others up — the sensor delivers " +
        "all of them together in bursts. Use it to save airtime and power, not to " +
        "gain rate.",
    unknownNote:
        "The device has not been asked yet. This cannot be read from the data: a " +
        "disabled sensor looks exactly like one that has not reported.",
};

/** Every button a stream_source exposes. */
export const SOURCE_BUTTON_CONTROLS: readonly ButtonControl[] = [IDENTIFY_CONTROL];

/** Every toggle group a stream_source exposes. */
export const SOURCE_TOGGLE_GROUPS: readonly ToggleGroupSpec[] = [REPORTS_GROUP];

/** True if `command` is one whose answer carries this group's state. */
export function answerCarriesGroupState(
    group: ToggleGroupSpec,
    command: string | undefined,
): boolean {
    return command === group.readCommand || command === group.writeCommand;
}

/**
 * Parse a group's state out of the device's answer, e.g.
 * `"accel=1 gyro=1 mag=0 rotation=1"`.
 *
 * ⚠️ Parsed from prose rather than sent as JSON because the answer travels on the
 * device LOG channel, whose records are a human-readable message by design — the
 * same channel a person reads when asking why a node is quiet. One format keeps
 * that log skimmable instead of turning it into a wire protocol nobody can read.
 *
 * ⚠️ ALL-OR-NOTHING: a message missing any toggle returns null rather than a
 * partial map. A half-parsed answer would render some switches from the device
 * and the rest from nothing, which is indistinguishable on screen from a device
 * that really has them off.
 */
export function parseToggleStates(
    group: ToggleGroupSpec,
    message: string,
): Record<string, boolean> | null {
    const found: Record<string, boolean> = {};
    for (const toggle of group.toggles) {
        // \b so a key cannot match inside a longer word ("xmag=1" is not "mag").
        const match = message.match(new RegExp(`\\b${toggle.id}=([01])\\b`));
        if (!match) return null;
        found[toggle.id] = match[1] === "1";
    }
    return found;
}

/** The args that flip one toggle — only the changed field, never the whole mask. */
export function writeArgsFor(
    toggle: ToggleSpec,
    current: Record<string, boolean>,
): Record<string, boolean> {
    return { [toggle.id]: !current[toggle.id] };
}
