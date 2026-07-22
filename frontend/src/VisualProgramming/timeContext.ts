// Per-graph time context + timeline layout helpers (Phase 4 of the
// experiments-and-time plan). A graph never runs at "now" specifically — it runs
// at a TIME CONTEXT: either the live head, or a point/range in recorded history.
// The timeline strip renders against this context. These helpers are pure so
// they can be unit-tested without the DOM / websocket.

import type { BufferedMarkerEvent } from "../StreamViewer/types";

export type TimeMode = "live" | "replay";

// Playback speed. "max" means as-fast-as-possible (batch reprocessing).
export type PlaybackSpeed = 0.5 | 1 | 2 | 4 | "max";

export interface TimeContext {
  mode: TimeMode;
  // Playhead position on the canonical microsecond axis. For live this tracks
  // the head; for replay it is where playback currently sits.
  playheadUs: number;
  // Optional bound of a replay window (an experiment's end), microseconds.
  endUs?: number;
  speed: PlaybackSpeed;
  playing: boolean;
  // The experiment/session this context is scoped to (replay), if any.
  sessionId?: string;
}

export function createLiveContext(nowUs: number): TimeContext {
  return { mode: "live", playheadUs: nowUs, speed: 1, playing: true };
}

// The visible axis window [startUs, endUs] on the canonical microsecond axis.
export interface TimeWindow {
  startUs: number;
  endUs: number;
}

// Default live window width (30s) — the "Live (last 30 s)" preset.
export const LIVE_WINDOW_US = 30_000_000;

// Compute the axis window. In live mode it's the last LIVE_WINDOW_US ending at
// the live edge (nowUs). In replay it spans the context's session window when
// known, else a window centered near the playhead. Markers widen the window so
// every recorded event is visible.
export function computeTimeWindow(
  ctx: TimeContext,
  nowUs: number,
  markers: BufferedMarkerEvent[],
  windowUs: number = LIVE_WINDOW_US,
): TimeWindow {
  let startUs: number;
  let endUs: number;
  if (ctx.mode === "live") {
    endUs = nowUs;
    startUs = nowUs - windowUs;
  } else {
    // Replay: prefer the explicit session window; else a window around the
    // playhead.
    endUs = ctx.endUs ?? ctx.playheadUs + windowUs / 2;
    startUs = ctx.playheadUs - windowUs / 2;
  }
  // Widen to include all markers so the recorded timeline is always in view.
  if (markers.length > 0) {
    for (const m of markers) {
      if (m.emitted_at_us < startUs) startUs = m.emitted_at_us;
      if (m.emitted_at_us > endUs) endUs = m.emitted_at_us;
    }
  }
  if (endUs <= startUs) {
    endUs = startUs + windowUs;
  }
  return { startUs, endUs };
}

// Map a microsecond time to a 0..1 fraction of the window (clamped).
export function timeToFraction(us: number, window: TimeWindow): number {
  const span = window.endUs - window.startUs;
  if (span <= 0) return 0;
  const f = (us - window.startUs) / span;
  return Math.max(0, Math.min(1, f));
}

// Inverse: a 0..1 fraction back to a microsecond time on the window.
export function fractionToTime(fraction: number, window: TimeWindow): number {
  const span = window.endUs - window.startUs;
  return Math.round(window.startUs + Math.max(0, Math.min(1, fraction)) * span);
}

export interface TimelineTick {
  fraction: number;
  label: string;
  event: string;
  session: boolean;
  us: number;
}

export interface TimelineRegion {
  startFraction: number;
  widthFraction: number;
  label: string;
  sessionId: string;
  recording: boolean;
}

// A session lifecycle marker delimits a recorded run/experiment.
function isSessionMarker(m: BufferedMarkerEvent): boolean {
  return m.marker_type === "session";
}

export function layoutTicks(
  markers: BufferedMarkerEvent[],
  window: TimeWindow,
): TimelineTick[] {
  return markers.map((m) => ({
    fraction: timeToFraction(m.emitted_at_us, window),
    label: m.label,
    event: m.event,
    session: isSessionMarker(m),
    us: m.emitted_at_us,
  }));
}

// Pair session start/end markers into experiment regions. A start with no end
// (recording live) extends to the live edge (nowUs).
export function layoutRegions(
  markers: BufferedMarkerEvent[],
  window: TimeWindow,
  nowUs: number,
): TimelineRegion[] {
  const regions: TimelineRegion[] = [];
  const openBySession = new Map<string, number>();
  for (const m of markers) {
    if (!isSessionMarker(m)) continue;
    if (m.event === "start") {
      openBySession.set(m.session_id, m.emitted_at_us);
    } else if (m.event === "end") {
      const startUs = openBySession.get(m.session_id);
      if (startUs !== undefined) {
        const startFraction = timeToFraction(startUs, window);
        const endFraction = timeToFraction(m.emitted_at_us, window);
        regions.push({
          startFraction,
          widthFraction: Math.max(0, endFraction - startFraction),
          label: m.session_id,
          sessionId: m.session_id,
          recording: false,
        });
        openBySession.delete(m.session_id);
      }
    }
  }
  // Still-open sessions (recording): draw to the live edge.
  for (const [sessionId, startUs] of openBySession) {
    const startFraction = timeToFraction(startUs, window);
    const endFraction = timeToFraction(nowUs, window);
    regions.push({
      startFraction,
      widthFraction: Math.max(0, endFraction - startFraction),
      label: sessionId,
      sessionId,
      recording: true,
    });
  }
  return regions;
}

// Numeric speed for pacing (max -> Infinity).
export function speedToRate(speed: PlaybackSpeed): number {
  return speed === "max" ? Infinity : speed;
}

// Advance a replay playhead by a wall-clock delta at the context's speed,
// clamped to endUs. Returns the new playhead and whether playback reached the
// end (so the caller can pause / snap).
export function advancePlayhead(
  ctx: TimeContext,
  wallDeltaMs: number,
  endUs: number,
): { playheadUs: number; reachedEnd: boolean } {
  if (ctx.mode !== "replay" || !ctx.playing) {
    return { playheadUs: ctx.playheadUs, reachedEnd: false };
  }
  const rate = speedToRate(ctx.speed);
  const advanceUs =
    rate === Infinity ? endUs - ctx.playheadUs : wallDeltaMs * 1000 * rate;
  const next = ctx.playheadUs + advanceUs;
  if (next >= endUs) {
    return { playheadUs: endUs, reachedEnd: true };
  }
  return { playheadUs: next, reachedEnd: false };
}
