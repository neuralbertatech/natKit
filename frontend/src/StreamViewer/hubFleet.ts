// The hub's fleet, as against its roster (TEC-NATKIT-81).
//
// ⚠️ THE DISTINCTION THIS MODULE EXISTS TO PRESERVE. A leaf stopped talking to
// the hub and the panel's `nodes` metric read 4 for hours, because it read
// `nodes_known` — the hub's PERSISTENT registry, kept in NVS so a sealed rig
// recognises a node on its return. That number is not supposed to fall when a
// board dies, and reading it as "the rig is complete" is the mistake.
//
// The hub now also reports `nodes_present`: how many of those it can actually
// hear. Three states, not two:
//
//   * `unreported` — a hub too old to say. Its `nodes_present` byte is ZERO, and
//     zero present is a real state and the more alarming one (every leaf gone),
//     so the count alone cannot carry both meanings. `nodes_present_valid` is the
//     byte that tells them apart, and an un-flashed hub must fall back to the
//     bare roster rather than being drawn as an empty rig.
//   * `complete` — every node on the roster is being heard.
//   * `short` — a node is registered and off the air, which is the fault itself.

/** The `fields` bag off a DeviceHealthEntry: the hub's status frame as JSON. */
type Fields = Record<string, unknown> | undefined;

export type HubFleetState = "unknown" | "unreported" | "complete" | "short";

export interface HubFleet {
    state: HubFleetState;
    /** What to print: "3/4", or the bare roster count when presence is unreported. */
    text: string;
    /** Nodes the hub can hear, or null when it does not report that. */
    present: number | null;
    /** Nodes on the roster, or null when the hub has not reported at all. */
    known: number | null;
}

const UNKNOWN: HubFleet = { state: "unknown", text: "—", present: null, known: null };

export function hubFleet(fields: Fields): HubFleet {
    const known = fields?.["nodes_known"];
    if (typeof known !== "number") return UNKNOWN;

    const present = fields?.["nodes_present"];
    // ⚠️ The flag is emitted as 0/1 by the C++ schema's toJson, so it arrives as a
    // number rather than a boolean. Checked for truthiness so either encoding
    // works, and a missing flag reads as unreported — which is what a hub that
    // predates the field is.
    const reported = Boolean(fields?.["nodes_present_valid"]);
    if (!reported || typeof present !== "number") {
        return { state: "unreported", text: String(known), present: null, known };
    }

    return {
        state: present < known ? "short" : "complete",
        text: `${present}/${known}`,
        present,
        known,
    };
}
