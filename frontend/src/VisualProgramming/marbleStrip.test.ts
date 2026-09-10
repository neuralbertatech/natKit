import { describe, expect, it } from "vitest";
import {
    describeStrip,
    layoutStrip,
    resolveAxisEndUs,
} from "./marbleStrip";
import { getNodeHeight, MARBLE_ROW_HEIGHT } from "./streamGraph";
import type { ChannelActivity } from "../StreamViewer/types";

const WINDOW = 4_000_000;
const BUCKET = 25_000;

const exact = (baseUs: number, offsets: number[]): ChannelActivity => ({
    mode: "exact",
    window_us: WINDOW,
    bucket_us: BUCKET,
    base_us: String(baseUs),
    total: offsets.length,
    offsets_us: offsets,
});

const density = (
    baseUs: number,
    buckets: number[],
    total?: number,
): ChannelActivity => ({
    mode: "density",
    window_us: WINDOW,
    bucket_us: BUCKET,
    base_us: String(baseUs),
    total: total ?? buckets.reduce((sum, count) => sum + count, 0),
    buckets,
});

describe("resolveAxisEndUs", () => {
    // ⚠️ The axis is shared across the card set, not per strip. The backend
    // snapshots each lane against its OWN newest event because a worker cannot
    // know what the rest of the graph is doing, so the caller must resolve one
    // end for all of them.
    it("takes the newest base across every lane", () => {
        expect(
            resolveAxisEndUs([
                exact(1_000_000, [0]),
                exact(9_000_000, [0]),
                undefined,
            ]),
        ).toBe(9_000_000);
    });

    it("is zero when nothing has any activity", () => {
        expect(resolveAxisEndUs([])).toBe(0);
        expect(resolveAxisEndUs([undefined, undefined])).toBe(0);
    });
});

describe("layoutStrip", () => {
    it("returns an empty layout for a lane with no activity", () => {
        expect(layoutStrip(undefined, 1_000_000).mode).toBe("empty");
        expect(layoutStrip(exact(1_000_000, []), 1_000_000).mode).toBe("empty");
    });

    it("places the newest event at the right edge when it defines the axis", () => {
        const layout = layoutStrip(exact(10_000_000, [0]), 10_000_000);
        expect(layout.mode).toBe("exact");
        expect(layout.marbles).toHaveLength(1);
        expect(layout.marbles[0].position).toBeCloseTo(1, 6);
    });

    it("places an event one window old at the left edge", () => {
        const layout = layoutStrip(exact(10_000_000, [WINDOW]), 10_000_000);
        expect(layout.marbles).toHaveLength(1);
        expect(layout.marbles[0].position).toBeCloseTo(0, 6);
    });

    // ⚠️ THE TEST THIS WHOLE MODULE EXISTS FOR.
    //
    // Two lanes, one live and one that stopped two seconds ago. Positioned
    // against their OWN bases they would both right-align and look identically
    // healthy. Against the shared axis the stalled lane sits half a window to
    // the left, which is the reading that makes a starved input visible.
    it("pushes a lagging lane left rather than right-aligning it", () => {
        const axisEnd = 10_000_000;
        const live = layoutStrip(exact(axisEnd, [0]), axisEnd);
        const lagging = layoutStrip(exact(axisEnd - 2_000_000, [0]), axisEnd);

        expect(live.marbles[0].position).toBeCloseTo(1, 6);
        expect(lagging.marbles[0].position).toBeCloseTo(0.5, 6);
        expect(lagging.marbles[0].position).toBeLessThan(
            live.marbles[0].position,
        );
    });

    it("drops events outside the window rather than piling them on an edge", () => {
        // Piling them on the edge would invent activity at a time when there was
        // none, which is worse than showing nothing.
        const layout = layoutStrip(
            exact(10_000_000, [0, WINDOW * 2, WINDOW * 3]),
            10_000_000,
        );
        expect(layout.marbles).toHaveLength(1);
        expect(layout.marbles[0].position).toBeCloseTo(1, 6);
        // The reported total stays the backend's exact count regardless of how
        // many were renderable.
        expect(layout.total).toBe(3);
    });

    it("marks a lane whose newest event predates the whole window as stale", () => {
        const axisEnd = 20_000_000;
        const stalled = layoutStrip(exact(5_000_000, [0]), axisEnd);
        expect(stalled.stale).toBe(true);
        // And nothing is drawn, because nothing happened in the window.
        expect(stalled.mode).toBe("empty");

        expect(layoutStrip(exact(axisEnd, [0]), axisEnd).stale).toBe(false);
    });

    describe("density mode", () => {
        it("normalises intensity against the busiest bucket in the same strip", () => {
            const layout = layoutStrip(density(10_000_000, [1, 2, 4]), 10_000_000);
            expect(layout.mode).toBe("density");
            expect(layout.columns).toHaveLength(3);
            const intensities = layout.columns.map((c) => c.intensity);
            expect(intensities[2]).toBeCloseTo(1, 6);
            expect(intensities[1]).toBeCloseTo(0.5, 6);
            expect(intensities[0]).toBeCloseTo(0.25, 6);
        });

        // Per-strip normalisation is deliberate: the question a strip answers is
        // "even or bursty", and that has to be legible on a 10 Hz lane and a
        // 1 kHz lane alike.
        it("gives a slow and a fast lane the same shape for the same pattern", () => {
            const slow = layoutStrip(density(10_000_000, [1, 5]), 10_000_000);
            const fast = layoutStrip(density(10_000_000, [200, 1000]), 10_000_000);
            expect(slow.columns.map((c) => c.intensity)).toEqual(
                fast.columns.map((c) => c.intensity),
            );
        });

        it("skips empty buckets so a gap reads as a gap", () => {
            const layout = layoutStrip(
                density(10_000_000, [5, 0, 0, 0, 5]),
                10_000_000,
            );
            expect(layout.columns).toHaveLength(2);
            // The two surviving columns are separated by the gap's width.
            const [first, last] = layout.columns;
            expect(last.position - first.position).toBeCloseTo(
                (4 * BUCKET) / WINDOW,
                6,
            );
        });

        it("orders columns oldest-first, left to right", () => {
            const layout = layoutStrip(
                density(10_000_000, [1, 1, 1]),
                10_000_000,
            );
            const positions = layout.columns.map((c) => c.position);
            expect(positions[0]).toBeLessThan(positions[1]);
            expect(positions[1]).toBeLessThan(positions[2]);
            // The newest bucket's right edge is this lane's own newest event.
            const lastColumn = layout.columns[layout.columns.length - 1];
            expect(lastColumn.position + lastColumn.width).toBeCloseTo(1, 6);
        });

        it("reports the backend's exact total, not the bucket sum it drew", () => {
            // Density buckets are exact, but a strip may drop columns outside
            // the window; the count must remain the true one.
            const layout = layoutStrip(density(10_000_000, [3, 4], 4213), 10_000_000);
            expect(layout.total).toBe(4213);
        });
    });
});

describe("describeStrip", () => {
    it("says so plainly when there is nothing", () => {
        expect(describeStrip(undefined)).toBe("no activity");
        expect(describeStrip(exact(1_000, []))).toBe("no activity");
    });

    it("counts without a rate when there are too few for one to mean anything", () => {
        expect(describeStrip(exact(1_000_000, [0, 1_000]))).toBe("2 in 4s");
    });

    // The rate is derived from what ARRIVED, not from any declared
    // sample_rate_hz — the gap between those two is the reason to look.
    it("derives the rate from the observed count over the window", () => {
        const activity = density(10_000_000, [], 400);
        activity.buckets = [400];
        expect(describeStrip(activity)).toBe("400 in 4s · ~100/s");
    });

    it("drops the decimal once the rate is large enough not to need it", () => {
        const activity = density(10_000_000, [], 4000);
        activity.buckets = [4000];
        expect(describeStrip(activity)).toBe("4000 in 4s · ~1000/s");
    });
});

describe("card height reservation", () => {
    // ⚠️ THE REGRESSION THIS GUARDS.
    //
    // The strips first lived inside `.node-meta`, the column between the two
    // port columns. With a 2.4rem label and a 1.8rem count either side, the
    // track measured TWO PIXELS wide — so all 160 density columns rendered into
    // it, correctly, and the strip looked like an empty box. Every unit test
    // passed. Only measuring the DOM found it.
    //
    // The fix is a full-width block below the body, which means the card has to
    // reserve height per reported lane. A node that reserves nothing has
    // nowhere to draw, which is the same invisible failure by another route.
    it("grows the card by one row per reported lane", () => {
        const node = {
            id: "n",
            kind: "combine" as const,
            input_port_ids: ["a", "b"],
            output_port_ids: ["out"],
            position: { x: 0, y: 0 },
        };
        const base = getNodeHeight(node as never, 0);
        expect(getNodeHeight(node as never, 1)).toBe(base + MARBLE_ROW_HEIGHT);
        expect(getNodeHeight(node as never, 2)).toBe(base + 2 * MARBLE_ROW_HEIGHT);
    });

    it("defaults to reserving nothing, so an unrelated caller is unaffected", () => {
        const node = {
            id: "n",
            kind: "transform" as const,
            input_port_ids: ["in"],
            output_port_ids: ["out"],
            position: { x: 0, y: 0 },
        };
        expect(getNodeHeight(node as never)).toBe(getNodeHeight(node as never, 0));
    });
});
