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

// --- operator-shaped strips (TEC-NATKIT-119 / 120) ------------------------
//
// A strip used to be one anonymous row per node — "something came out at these
// times" — which is the identical picture whether the node is a zip, a filter
// or a threshold. Zach, looking at a live board: "the visualization does not
// make sense to me... currently they are not very useful."
//
// The grammar is: inputs on their own rows ABOVE, output BELOW, on the shared
// axis, with a glyph between them naming the operation. The merge is implied by
// the layout rather than drawn as converging geometry — cheap enough to read at
// 270px and it keeps the cards close to their current height.
//
// ⚠️ THE STARVED-INPUT CASE IS THE ACCEPTANCE TEST. One input silent while its
// sibling stays dense, and an output that dies with it, must be readable
// without opening anything.

import type { NamedChannelActivity } from "../StreamViewer/types";

export interface StripRow {
  role: "input" | "output";
  label: string;
  layout: StripLayout;
  caption: string;
  // The row's lane has said nothing for the whole window. Called out explicitly
  // because an empty row and a row that never existed mean different things,
  // and because this is the failure the rows were added to reveal.
  silent: boolean;
}

export interface OperatorStrip {
  rows: StripRow[];
  // Names the operation between the input rows and the output row. Carries the
  // join policy for a combine and the level/direction for a threshold, so the
  // two are distinguishable without opening the inspector.
  glyph: string;
}

// How long a lane may go without an event before the strip calls it silent.
// Matches classifyTransformWorkerStatus's own 3s, so the card and the node
// badge cannot disagree about whether something is still running.
export const LANE_SILENCE_US = 3_000_000;

/**
 * Is this lane dead by the WALL clock?
 *
 * ⚠️ THE RELATIVE TEST CANNOT ANSWER THIS. `layoutStrip`'s `stale` is measured
 * against the graph's own newest event, so it only ever says "this lane is
 * behind the others" — when every lane stops at the same moment none is behind
 * any other, and the strips go on reporting their last known rates. A board
 * whose feeds had been dead for two and a half hours still read "50.0/s"
 * (TEC-NATKIT-123).
 *
 * Returns false when the backend sent no stamp (older build) or the lane has
 * never recorded anything, so a missing signal never invents silence.
 */
export function laneIsSilent(
  activity: { last_seen_wall_us?: string } | undefined,
  nowWallUs: number,
): boolean {
  if (!activity || !nowWallUs) return false;
  const lastSeen = Number(activity.last_seen_wall_us ?? 0);
  if (!Number.isFinite(lastSeen) || lastSeen <= 0) return false;
  return nowWallUs - lastSeen > LANE_SILENCE_US;
}

/** A rate, or how long a lane has been quiet — whichever the row is saying. */
export function captionFor(
  activity: ChannelActivityLike | undefined,
  layout: StripLayout,
  axisEndUs: number,
  nowWallUs = 0,
): string {
  if (!activity || activity.total <= 0) {
    if (!activity) return "—";
    // Total 0 inside a live window still means "nothing recently".
    return "0/s";
  }
  // The wall clock first: a lane everything else also stopped with is invisible
  // to the relative test below, and reporting its old rate is the bug.
  if (laneIsSilent(activity, nowWallUs)) {
    const quietUs = nowWallUs - Number(activity.last_seen_wall_us ?? 0);
    const seconds = quietUs / 1_000_000;
    if (seconds >= 3600) return `silent ${(seconds / 3600).toFixed(1)}h`;
    if (seconds >= 60) return `silent ${Math.round(seconds / 60)}m`;
    return `silent ${seconds.toFixed(0)}s`;
  }
  if (layout.stale) {
    const quietUs = axisEndUs - Number(activity.base_us);
    const seconds = quietUs / 1_000_000;
    return seconds >= 1
      ? `silent ${seconds.toFixed(0)}s`
      : `silent ${Math.round(quietUs / 1000)}ms`;
  }
  const seconds = activity.window_us / 1_000_000;
  if (seconds <= 0) return `${activity.total}`;
  const rate = activity.total / seconds;
  if (rate < 1) return `${activity.total} in ${seconds.toFixed(0)}s`;
  return `${rate >= 100 ? rate.toFixed(0) : rate.toFixed(1)}/s`;
}

// Structural subset, so this stays usable from tests without the full wire type.
interface ChannelActivityLike {
  window_us: number;
  base_us: string;
  total: number;
  last_seen_wall_us?: string;
}

const JOIN_POLICY_GLYPH: Record<string, string> = {
  zip: "zip",
  combine_latest: "combine latest",
  with_latest_from: "with latest from",
  sample: "sample",
};

const DIRECTION_ARROW: Record<string, string> = {
  rising: "↑",
  falling: "↓",
  either: "↕",
};

/**
 * The glyph between the input rows and the output row.
 *
 * Deliberately carries the CONFIG that changes the operator's behaviour, not
 * just its name: two combines differ only by join policy, and two thresholds
 * only by level and direction, so a name alone would make them indistinguishable
 * on the canvas — which is the problem this whole change is fixing.
 */
export function operatorGlyph(
  kind: string,
  config: Record<string, unknown> | undefined,
): string {
  if (kind === "combine") {
    const policy = String(config?.join_policy ?? "zip");
    return JOIN_POLICY_GLYPH[policy] ?? policy;
  }
  if (kind === "threshold") {
    const level = config?.level;
    const arrow = DIRECTION_ARROW[String(config?.direction ?? "either")] ?? "↕";
    return level === undefined ? `threshold ${arrow}` : `${level} ${arrow}`;
  }
  return kind.replace(/_/g, " ");
}

/**
 * Builds the stacked rows for one node.
 *
 * `inputs` come from the backend already named by port; the output row is
 * whichever lane the node actually publishes. Returns null when there is
 * nothing to draw at all, so the card renders no block rather than an empty
 * one — an empty block reads as "this stopped", a different claim.
 */
export function buildOperatorStrip(
  kind: string,
  config: Record<string, unknown> | undefined,
  inputs: NamedChannelActivity[] | undefined,
  output: ChannelActivity | undefined,
  outputLabel: string,
  axisEndUs: number,
  // The backend's wall clock at snapshot time. 0 disables the absolute test,
  // which is what an older backend gets.
  nowWallUs = 0,
): OperatorStrip | null {
  const rows: StripRow[] = [];
  for (const input of inputs ?? []) {
    const layout = layoutStrip(input, axisEndUs);
    rows.push({
      role: "input",
      label: input.port_id,
      layout,
      caption: captionFor(input, layout, axisEndUs, nowWallUs),
      silent:
        layout.stale ||
        input.total === 0 ||
        laneIsSilent(input, nowWallUs),
    });
  }
  if (rows.length === 0 && !output) return null;

  const outLayout = layoutStrip(output, axisEndUs);
  rows.push({
    role: "output",
    label: outputLabel,
    layout: outLayout,
    caption: captionFor(output, outLayout, axisEndUs, nowWallUs),
    silent:
      !!output &&
      (outLayout.stale ||
        output.total === 0 ||
        laneIsSilent(output, nowWallUs)),
  });

  return { rows, glyph: operatorGlyph(kind, config) };
}

// --- the tracks grammar (TEC-NATKIT-122) ---------------------------------
//
// The second of the two grammars, switchable from the toolbar. Where the
// stacked rows IMPLY the operation by layout, this one DRAWS it: marbles ride
// rails that physically converge for a merge and split for a fork.
//
// The two answer different questions and that is why both exist. Rows are
// denser and read like a table — best when comparing rates across several
// nodes. Tracks are bigger but say what the operator DOES at a glance, which is
// what somebody meeting a board for the first time needs.
//
// ⚠️ COORDINATES ARE REAL PIXELS, NOT A NORMALISED 0..100 BOX. The first cut
// used a 100-wide viewBox stretched with preserveAspectRatio="none", which
// scales x and y by different factors — so every text label came out distorted
// and overlapping its neighbours. A design-width box scaled uniformly keeps
// text proportional, and a card a little wider or narrower than the design
// width only scales it slightly.

// The width this diagram is designed at. The SVG scales uniformly from here, so
// a card within ~20% of it looks exactly as laid out.
export const TRACK_DESIGN_WIDTH = 240;
// Vertical pitch between lanes, in the same units.
// ⚠️ Must be at least ~2.5x the caption font size. For a MERGE the output sits
// on the centre line, only half a pitch from each input, so a pitch sized for
// the rails alone puts three captions on top of each other on the right.
const TRACK_LANE = 24;
const TRACK_PAD = 6;
// Room reserved at each end for the lane label and its caption.
const LABEL_W = 26;
const CAPTION_W = 36;

export interface TrackMarble {
  x: number;
  y: number;
}

export interface TrackColumn {
  x: number;
  width: number;
  y: number;
  intensity: number;
}

export interface TrackLane {
  role: "input" | "output" | "passthrough";
  label: string;
  caption: string;
  silent: boolean;
  lane: "data" | "markers";
  // The straight run the marbles ride on.
  x1: number;
  x2: number;
  y: number;
  marbles: TrackMarble[];
  columns: TrackColumn[];
}

export interface TrackDiagram {
  width: number;
  height: number;
  lanes: TrackLane[];
  // The diagonals, as explicit segments so the renderer draws no geometry of
  // its own — everything positional stays here where it is testable.
  joins: { x1: number; y1: number; x2: number; y2: number; silent: boolean }[];
  hub: { x: number; y: number };
  glyph: string;
  glyphX: number;
  glyphY: number;
}

/**
 * Places an operator strip's rows as converging or forking tracks.
 *
 * `mode` decides the shape: a merge fans N inputs into one output (combine), a
 * fork splits one input into what passed and what did not (threshold).
 *
 * ⚠️ THE FORK'S LOWER BRANCH IS NOT A COUNT. For a threshold the input is
 * FRAMES and the output is CROSSINGS, and one frame can produce several
 * crossings — so "input.total - output.total" would be a fabricated number
 * dressed up as a measurement. The lower branch carries the input's own density
 * dimmed and is left unlabelled, which says "this much went in, this little
 * crossed" without inventing anything.
 */
export function layoutTrackDiagram(
  strip: OperatorStrip,
  mode: "merge" | "fork",
  outputLane: "data" | "markers",
  width: number = TRACK_DESIGN_WIDTH,
): TrackDiagram {
  const inputs = strip.rows.filter((row) => row.role === "input");
  const output = strip.rows.find((row) => row.role === "output");
  const right = width - CAPTION_W;

  const place = (
    row: StripRow,
    x1: number,
    x2: number,
    y: number,
    lane: "data" | "markers",
  ): TrackLane => ({
    role: row.role,
    label: row.label,
    caption: row.caption,
    silent: row.silent,
    lane,
    x1,
    x2,
    y,
    marbles: row.layout.marbles.map((marble) => ({
      x: x1 + marble.position * (x2 - x1),
      y,
    })),
    columns: row.layout.columns.map((column) => ({
      x: x1 + column.position * (x2 - x1),
      width: column.width * (x2 - x1),
      y,
      intensity: column.intensity,
    })),
  });

  if (mode === "fork" && output && inputs.length === 1) {
    const height = TRACK_LANE * 2 + TRACK_PAD * 2;
    const centre = height / 2;
    const upper = centre - TRACK_LANE / 2;
    const lower = centre + TRACK_LANE / 2;
    const fanStart = LABEL_W + (right - LABEL_W) * 0.42;
    const fanEnd = fanStart + 22;
    const lanes: TrackLane[] = [
      place(inputs[0], LABEL_W, fanStart, centre, "data"),
      place(output, fanEnd + 4, right, upper, outputLane),
      {
        ...place(inputs[0], fanEnd + 4, right, lower, "data"),
        role: "passthrough",
        label: "",
        caption: "",
      },
    ];
    return {
      width,
      height,
      lanes,
      joins: [
        { x1: fanStart, y1: centre, x2: fanEnd, y2: upper, silent: output.silent },
        { x1: fanStart, y1: centre, x2: fanEnd, y2: lower, silent: inputs[0].silent },
      ],
      hub: { x: (fanStart + fanEnd) / 2, y: centre },
      glyph: strip.glyph,
      glyphX: (LABEL_W + fanStart) / 2,
      glyphY: centre - 9,
    };
  }

  // Merge: inputs stacked, output on the centre line between them.
  const rowCount = Math.max(inputs.length, 2);
  const height = TRACK_LANE * rowCount + TRACK_PAD * 2;
  const centre = height / 2;
  const fanStart = LABEL_W + (right - LABEL_W) * 0.46;
  const fanEnd = fanStart + 20;
  const lanes: TrackLane[] = inputs.map((row, index) =>
    place(
      row,
      LABEL_W,
      fanStart,
      TRACK_PAD + TRACK_LANE / 2 + index * TRACK_LANE,
      "data",
    ),
  );
  const joins = lanes.map((lane, index) => ({
    x1: fanStart,
    y1: lane.y,
    x2: fanEnd,
    y2: centre,
    silent: inputs[index].silent,
  }));
  if (output) {
    // ⚠️ The run starts clear of the hub, not at it: the output's label is
    // drawn just left of its own rail, and at the hub it lands on top of the
    // junction dot.
    lanes.push(place(output, fanEnd + 22, right, centre, outputLane));
  }
  return {
    width,
    height,
    lanes,
    joins,
    hub: { x: fanEnd, y: centre },
    glyph: strip.glyph,
    // Above the junction, so it names the operation without sitting on the
    // incoming diagonals.
    glyphX: fanEnd,
    glyphY: centre - 9,
  };
}

/** Which shape a kind draws. Merge is the default: most operators fan in. */
export function trackModeFor(kind: string): "merge" | "fork" {
  return kind === "threshold" ? "fork" : "merge";
}
