import { describe, expect, it } from "vitest";
import { configOptionLabel, visibleConfigFields } from "./streamGraph";

// Mirrors what the backend's node catalog advertises for the combine node
// (buildNodeCatalogJson). Kept as a literal rather than imported so a change to
// the backend's shape shows up here as a failing test rather than as silence.
const COMBINE_FIELDS = [
    {
        id: "join_policy",
        label: "Join policy",
        type: "enum" as const,
        required: true,
        default_option: "zip",
        options: ["zip", "combine_latest", "with_latest_from", "sample"],
        option_labels: [
            "zip — lockstep, wait for laggards",
            "combine latest — emit on any input",
            "with latest from — input 1 is the clock",
            "sample — a fixed rate drives output",
        ],
    },
    {
        id: "align_tolerance_ms",
        label: "Align tolerance (ms)",
        type: "number" as const,
        required: false,
        default_value: 50,
        visible_when: { field: "join_policy", equals: ["zip"] },
    },
    {
        id: "sample_rate_hz",
        label: "Output rate (Hz)",
        type: "number" as const,
        required: false,
        default_value: 10,
        visible_when: { field: "join_policy", equals: ["sample"] },
    },
];

const ids = (config: Record<string, unknown> | null | undefined) =>
    visibleConfigFields(COMBINE_FIELDS, config).map((field) => field.id);

describe("visibleConfigFields", () => {
    // The case the guard exists for: a tolerance that does nothing under
    // combine_latest must not be offered, or the author sets it and wonders why
    // nothing changed.
    it("shows only the fields the selected join policy actually reads", () => {
        expect(ids({ join_policy: "zip" })).toEqual([
            "join_policy",
            "align_tolerance_ms",
        ]);
        expect(ids({ join_policy: "sample" })).toEqual([
            "join_policy",
            "sample_rate_hz",
        ]);
        expect(ids({ join_policy: "combine_latest" })).toEqual(["join_policy"]);
        expect(ids({ join_policy: "with_latest_from" })).toEqual(["join_policy"]);
    });

    // A node dropped on the canvas has no config yet, and the backend will run
    // it as `zip`. The inspector must agree with that rather than hiding
    // everything, or the default is unreachable until something else is picked
    // first.
    it("falls back to the guard field's own default when config is empty", () => {
        expect(ids({})).toEqual(["join_policy", "align_tolerance_ms"]);
        expect(ids(undefined)).toEqual(["join_policy", "align_tolerance_ms"]);
        expect(ids(null)).toEqual(["join_policy", "align_tolerance_ms"]);
    });

    it("keeps unguarded fields regardless of config", () => {
        const plain = [{ id: "cutoff_hz" }, { id: "order" }];
        expect(visibleConfigFields(plain, {}).map((f) => f.id)).toEqual([
            "cutoff_hz",
            "order",
        ]);
    });

    // An unknown policy is reported by backend validation, not silently
    // rewritten, so the inspector should not invent fields for it.
    it("hides a guarded field when the guard matches nothing", () => {
        expect(ids({ join_policy: "nonsense" })).toEqual(["join_policy"]);
    });

    it("treats a numeric guard value as its string form", () => {
        const fields = [
            { id: "mode", default_value: 2 },
            { id: "gain", visible_when: { field: "mode", equals: ["2"] } },
        ];
        expect(visibleConfigFields(fields, { mode: 2 }).map((f) => f.id)).toEqual(
            ["mode", "gain"],
        );
        expect(visibleConfigFields(fields, { mode: 3 }).map((f) => f.id)).toEqual(
            ["mode"],
        );
    });
});

describe("configOptionLabel", () => {
    // The wire value has to stay terse (it is what the backend parses); the
    // picker has to say what the option DOES, because picking wrong here is
    // silently wrong rather than an error.
    it("prefers the advertised label for an option", () => {
        expect(configOptionLabel(COMBINE_FIELDS[0], "with_latest_from")).toBe(
            "with latest from — input 1 is the clock",
        );
    });

    it("falls back to the raw value when no labels are advertised", () => {
        expect(
            configOptionLabel({ options: ["a", "b"] }, "b"),
        ).toBe("b");
        expect(configOptionLabel(COMBINE_FIELDS[0], "unlisted")).toBe("unlisted");
    });
});
