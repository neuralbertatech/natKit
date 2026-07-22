import { describe, it, expect } from "vitest";
import type { BufferedMarkerEvent } from "../StreamViewer/types";
import {
  createLiveContext,
  computeTimeWindow,
  timeToFraction,
  fractionToTime,
  layoutTicks,
  layoutRegions,
  advancePlayhead,
  LIVE_WINDOW_US,
  type TimeContext,
} from "./timeContext";

function marker(
  partial: Partial<BufferedMarkerEvent> & { emitted_at_us: number },
): BufferedMarkerEvent {
  return {
    session_id: "exp1",
    marker_type: "cue",
    marker_id: "m",
    event: "hold",
    label: "a",
    attributes: {},
    received_at_ms: 0,
    ...partial,
  };
}

describe("computeTimeWindow", () => {
  it("live mode spans the last LIVE_WINDOW_US ending at now", () => {
    const ctx = createLiveContext(1_000_000_000);
    const w = computeTimeWindow(ctx, 1_000_000_000, []);
    expect(w.endUs).toBe(1_000_000_000);
    expect(w.startUs).toBe(1_000_000_000 - LIVE_WINDOW_US);
  });

  it("widens the window to include all markers", () => {
    const ctx = createLiveContext(1_000_000_000);
    const w = computeTimeWindow(ctx, 1_000_000_000, [
      marker({ emitted_at_us: 500_000_000 }),
    ]);
    expect(w.startUs).toBeLessThanOrEqual(500_000_000);
  });
});

describe("timeToFraction / fractionToTime", () => {
  const w = { startUs: 100, endUs: 1100 };
  it("maps time to a clamped 0..1 fraction", () => {
    expect(timeToFraction(100, w)).toBe(0);
    expect(timeToFraction(600, w)).toBeCloseTo(0.5, 5);
    expect(timeToFraction(1100, w)).toBe(1);
    expect(timeToFraction(5000, w)).toBe(1);
  });
  it("round-trips a fraction back to time", () => {
    expect(fractionToTime(0.5, w)).toBe(600);
    expect(fractionToTime(0, w)).toBe(100);
    expect(fractionToTime(1, w)).toBe(1100);
  });
});

describe("layoutTicks / layoutRegions", () => {
  const window = { startUs: 0, endUs: 1000 };
  const markers: BufferedMarkerEvent[] = [
    marker({ marker_type: "session", event: "start", emitted_at_us: 100, session_id: "s1", label: "s1" }),
    marker({ marker_type: "cue", event: "hold", emitted_at_us: 300, label: "a" }),
    marker({ marker_type: "cue", event: "hold", emitted_at_us: 600, label: "b" }),
    marker({ marker_type: "session", event: "end", emitted_at_us: 800, session_id: "s1", label: "s1" }),
  ];

  it("lays out a tick per marker with session flag", () => {
    const ticks = layoutTicks(markers, window);
    expect(ticks).toHaveLength(4);
    expect(ticks[0].session).toBe(true);
    expect(ticks[1].session).toBe(false);
    expect(ticks[2].fraction).toBeCloseTo(0.6, 5);
  });

  it("pairs session start/end into a region", () => {
    const regions = layoutRegions(markers, window, 1000);
    expect(regions).toHaveLength(1);
    expect(regions[0].sessionId).toBe("s1");
    expect(regions[0].startFraction).toBeCloseTo(0.1, 5);
    expect(regions[0].widthFraction).toBeCloseTo(0.7, 5);
    expect(regions[0].recording).toBe(false);
  });

  it("draws an open (recording) session to the live edge", () => {
    const open = [
      marker({ marker_type: "session", event: "start", emitted_at_us: 200, session_id: "live", label: "live" }),
    ];
    const regions = layoutRegions(open, { startUs: 0, endUs: 1000 }, 1000);
    expect(regions).toHaveLength(1);
    expect(regions[0].recording).toBe(true);
    expect(regions[0].widthFraction).toBeCloseTo(0.8, 5);
  });
});

describe("advancePlayhead", () => {
  const base: TimeContext = {
    mode: "replay",
    playheadUs: 0,
    speed: 1,
    playing: true,
  };

  it("advances at 1x by wall-clock delta (ms -> us)", () => {
    const r = advancePlayhead(base, 100, 10_000_000);
    expect(r.playheadUs).toBe(100_000); // 100ms * 1000 * 1x
    expect(r.reachedEnd).toBe(false);
  });

  it("advances faster at 2x", () => {
    const r = advancePlayhead({ ...base, speed: 2 }, 100, 10_000_000);
    expect(r.playheadUs).toBe(200_000);
  });

  it("jumps to end at max speed", () => {
    const r = advancePlayhead({ ...base, speed: "max" }, 1, 5_000_000);
    expect(r.playheadUs).toBe(5_000_000);
    expect(r.reachedEnd).toBe(true);
  });

  it("clamps to end and flags reachedEnd", () => {
    const r = advancePlayhead({ ...base, playheadUs: 9_990_000 }, 100, 10_000_000);
    expect(r.playheadUs).toBe(10_000_000);
    expect(r.reachedEnd).toBe(true);
  });

  it("does not advance in live mode or when paused", () => {
    expect(advancePlayhead({ ...base, mode: "live" }, 100, 10).playheadUs).toBe(0);
    expect(advancePlayhead({ ...base, playing: false }, 100, 10).playheadUs).toBe(0);
  });
});
