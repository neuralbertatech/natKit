import { describe, expect, it } from "vitest";
import { hubFleet } from "./hubFleet";

describe("hubFleet", () => {
    it("says nothing when the hub has not reported at all", () => {
        expect(hubFleet(undefined).state).toBe("unknown");
        expect(hubFleet({}).state).toBe("unknown");
        expect(hubFleet({}).text).toBe("—");
    });

    // ⚠️ The case the whole thing exists for. A hub too old to report presence
    // sends nodes_present = 0, and drawing that as "0/4" would put every rig on
    // the old firmware into alarm — which is how a real alarm gets ignored.
    it("falls back to the bare roster when the hub does not report presence", () => {
        const fleet = hubFleet({ nodes_known: 4, nodes_present: 0, nodes_present_valid: 0 });
        expect(fleet.state).toBe("unreported");
        expect(fleet.text).toBe("4");
        expect(fleet.present).toBeNull();
    });

    it("treats a missing presence flag as unreported, not as none present", () => {
        expect(hubFleet({ nodes_known: 4 }).state).toBe("unreported");
        expect(hubFleet({ nodes_known: 4 }).text).toBe("4");
    });

    it("is complete when every roster node is heard", () => {
        const fleet = hubFleet({ nodes_known: 4, nodes_present: 4, nodes_present_valid: 1 });
        expect(fleet.state).toBe("complete");
        expect(fleet.text).toBe("4/4");
    });

    // The fault as measured on 2026-08-24: one board on the roster, off the air.
    // nodes_known deliberately does not move — the roster is persistent — so the
    // two disagreeing IS the signal.
    it("is short when a roster node is off the air", () => {
        const fleet = hubFleet({ nodes_known: 4, nodes_present: 3, nodes_present_valid: 1 });
        expect(fleet.state).toBe("short");
        expect(fleet.text).toBe("3/4");
        expect(fleet.present).toBe(3);
        expect(fleet.known).toBe(4);
    });

    // ⚠️ Zero present WITH the flag set is real, and must not be quietly softened
    // into the old firmware's fallback. It is the worst state the rig can be in.
    it("reports nothing heard as a fault rather than as unreported", () => {
        const fleet = hubFleet({ nodes_known: 4, nodes_present: 0, nodes_present_valid: 1 });
        expect(fleet.state).toBe("short");
        expect(fleet.text).toBe("0/4");
    });

    it("accepts a boolean flag as well as the schema's 0/1", () => {
        expect(hubFleet({ nodes_known: 2, nodes_present: 1, nodes_present_valid: true }).text).toBe("1/2");
    });
});
