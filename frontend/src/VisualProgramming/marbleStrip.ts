// Layout for the marble strips on node cards (TEC-NATKIT-106).
//
// Pure, so the thing that actually matters here is testable: WHERE a marble
// lands on a shared time axis. Two rows are only comparable if they share one
// axis — that is the entire reason to draw them together, and it is what makes
// a misaligning combine visible as two input rows whose marbles do not line up
// above the output row.
//
// ⚠️ THE AXIS IS SHARED ACROSS THE GRAPH, NOT PER STRIP. The backend snapshots
// each lane relative to its OWN newest event, because a worker does not know
// what the rest of the graph is doing. Positioning each strip against its own
// base would silently right-align every row, so a stalled input would look
// perfectly healthy and aligned with a live one — the exact failure this is
// meant to reveal. The caller resolves one `axisEndUs` for the whole card set
// and every strip is placed against it.

import type { ChannelActivity } from "../StreamViewer/types";

// A marble to draw, positioned as a fraction of the strip's width: 0 is the
// oldest edge of the window, 1 the newest.
export interface MarblePlacement {
  position: number;
}

// A density column, likewise positioned 0..1, with an intensity 0..1 relative
// to the busiest bucket in the same strip.
export interface DensityColumn {
  position: number;
  width: number;
  intensity: number;
}

export interface StripLayout {
  mode: "exact" | "density" | "empty";
  marbles: MarblePlacement[];
  columns: DensityColumn[];
  // What the strip is reporting, for the label: the true event count, which is
  // exact in both modes.
  total: number;
  // True when the lane's newest event is older than the whole window — the row
  // is genuinely silent right now rather than merely sparse. Worth saying
  // explicitly, because an empty row and a missing row mean different things.
  stale: boolean;
}

const EMPTY: StripLayout = {
  mode: "empty",
  marbles: [],
  columns: [],
  total: 0,
  stale: false,
};

/**
 * Resolves the shared axis end for a set of lanes: the newest event any of them
 * has seen.
 *
 * Uses the DATA clock rather than the wall clock, so a paused replay holds its
 * strips still instead of draining them, and a live graph and a replay of that
 * same graph draw identically.
 */
export function resolveAxisEndUs(
  activities: (ChannelActivity | undefined)[],
): number {
  let newest = 0;
  for (const activity of activities) {
    if (!activity) continue;
    const base = Number(activity.base_us);
    if (Number.isFinite(base) && base > newest) {
      newest = base;
    }
  }
  return newest;
}

/**
 * Places one lane's activity on the shared axis.
 *
 * `axisEndUs` is the right-hand edge for every strip on the card; `windowUs`
 * comes from the activity itself so the backend remains the authority on how
 * much history a strip shows.
 */
export function layoutStrip(
  activity: ChannelActivity | undefined,
  axisEndUs: number,
): StripLayout {
  if (!activity || activity.total <= 0) {
    return EMPTY;
  }
  const windowUs = activity.window_us > 0 ? activity.window_us : 1;
  const baseUs = Number(activity.base_us);
  if (!Number.isFinite(baseUs) || baseUs <= 0) {
    return EMPTY;
  }
  const axisEnd = axisEndUs > 0 ? axisEndUs : baseUs;
  const axisStart = axisEnd - windowUs;
  // How far this lane's newest event sits behind the shared axis end. A lane
  // that stopped a while ago is pushed left and eventually off the strip, which
  // is exactly the reading we want: silence looks like silence.
  const stale = baseUs < axisStart;

  const toPosition = (atUs: number): number => (atUs - axisStart) / windowUs;

  if (activity.mode === "exact") {
    const marbles: MarblePlacement[] = [];
    for (const offset of activity.offsets_us ?? []) {
      const position = toPosition(baseUs - offset);
      // Clamp nothing: a marble outside 0..1 is genuinely outside the window
      // and is dropped rather than piled onto an edge, which would invent
      // activity at a time when there was none.
      if (position < 0 || position > 1) continue;
      marbles.push({ position });
    }
    return {
      mode: marbles.length > 0 ? "exact" : "empty",
      marbles,
      columns: [],
      total: activity.total,
      stale,
    };
  }

  const buckets = activity.buckets ?? [];
  if (buckets.length === 0) {
    return { ...EMPTY, total: activity.total, stale };
  }
  const bucketUs = activity.bucket_us > 0 ? activity.bucket_us : windowUs;
  // Intensity is relative to the busiest bucket IN THIS STRIP, not to an
  // absolute rate: the question a strip answers is "is this even, or bursty",
  // and normalising per strip is what makes a gap or a burst legible on a 10 Hz
  // lane and a 1 kHz lane alike.
  let peak = 0;
  for (const count of buckets) {
    if (count > peak) peak = count;
  }
  if (peak <= 0) {
    return { ...EMPTY, total: activity.total, stale };
  }

  const columns: DensityColumn[] = [];
  const width = bucketUs / windowUs;
  for (let index = 0; index < buckets.length; index += 1) {
    const count = buckets[index];
    if (count <= 0) continue;
    // Buckets arrive oldest-first, and the last one ends at this lane's own
    // newest event — so its right edge is baseUs, not the shared axis end.
    const endUs = baseUs - (buckets.length - 1 - index) * bucketUs;
    const position = toPosition(endUs - bucketUs);
    if (position + width < 0 || position > 1) continue;
    columns.push({ position, width, intensity: count / peak });
  }

  return {
    mode: columns.length > 0 ? "density" : "empty",
    marbles: [],
    columns,
    total: activity.total,
    stale,
  };
}

/**
 * A short human label for a strip: the event count and, when it is dense enough
 * to be a rate rather than a list, the implied rate.
 *
 * The rate is derived from the count over the window rather than read from a
 * declared sample_rate_hz, deliberately: the declared rate is what a device
 * claims and this is what actually arrived, and the gap between those two is
 * the whole reason to look at a strip.
 */
export function describeStrip(
  activity: ChannelActivity | undefined,
): string {
  if (!activity || activity.total <= 0) {
    return "no activity";
  }
  const seconds = activity.window_us / 1_000_000;
  if (seconds <= 0) {
    return `${activity.total}`;
  }
  const rate = activity.total / seconds;
  if (activity.total < 10) {
    return `${activity.total} in ${seconds.toFixed(0)}s`;
  }
  const shown = rate >= 100 ? rate.toFixed(0) : rate.toFixed(1);
  return `${activity.total} in ${seconds.toFixed(0)}s · ~${shown}/s`;
}
