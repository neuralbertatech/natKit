import { expect, test } from "./support/fixtures";
import { VpApp } from "./support/app";

/**
 * TEC-NATKIT-106 — marble strips on node cards, captured from a RUNNING graph.
 *
 * The strips exist to make four things visible that are invisible anywhere else:
 * a combine silently misaligning, a starved input, a drop-oldest gap, and an
 * output pattern that does not follow from its inputs. So the evidence has to be
 * a graph with genuinely different cadences on it — a single rate makes every
 * strip identical and proves nothing.
 *
 * ⚠️ REQUIRES A LIVE FEED. Two synthetic devices publish through the real MQTT
 * -> bridge -> Kafka path while this runs (scratchpad/feed.py: 909001 at ~50 Hz
 * frames, 909002 at ~5 Hz). Without it the graph starts and every strip is
 * correctly absent, which is a passing-looking run that captures nothing — so
 * the test asserts the strips are present rather than screenshotting whatever is
 * there.
 */

// A data topic embeds its own stream id: `Data-<stream_id>-Json-<schema>`, and
// `get_streams` keys its map by exactly that number. So the feed's device ids
// ARE the stream ids and no lookup is needed — which also means this test does
// not depend on the stream registry having noticed the topics yet, only on the
// backend being able to resolve them from Kafka metadata when the graph starts.
const FAST_ID = "909001";
const SLOW_ID = "909002";

// The card root carries no id of its own, but every port inside it does. A
// source node's visible label is its DEVICE NAME rather than the label the test
// set (and is then truncated), so matching on text is not an option.
function card(page: import("@playwright/test").Page, nodeId: string) {
    return page
        .locator(".node")
        .filter({ has: page.locator(`[data-node-id="${nodeId}"]`) })
        .first();
}

test("marble strips render per lane on a running graph", async ({
    page,
    app,
    viewer,
    evidence,
}) => {
    await app.open();
    await app.createScratchBoard();

    const fastId = FAST_ID;
    const slowId = SLOW_ID;

    // A chain whose stages run at deliberately different rates, so the strips
    // differ from each other rather than all showing the same bar:
    //   fast source (50 Hz frames) ─┐
    //                               ├─ combine (zip)
    //   slow source (5 Hz frames)  ─┘
    await app.attachNodes([
        { ...VpApp.sourceNode(fastId), id: "fast", label: "EMG (fast)", position: { x: 320, y: 140 } },
        { ...VpApp.sourceNode(slowId), id: "slow", label: "IMU (slow)", position: { x: 320, y: 420 } },
        {
            id: "join",
            kind: "combine",
            label: "Combine",
            input_port_ids: ["in1", "in2"],
            output_port_ids: ["out"],
            position: { x: 760, y: 260 },
            output_identifier: "marbles-join",
            config: { join_policy: "combine_latest" },
        },
    ]);

    // Wire the two sources into the combine.
    const board = await viewer.getGraph(app.boardId);
    if (!board) throw new Error("scratch board vanished");
    const { editor_metadata: _drop, ...rest } = board;
    await page.goto("about:blank");
    await viewer.saveGraph({
        ...rest,
        edges: [
            { id: "e1", source_node_id: "fast", source_port: "data", target_node_id: "join", target_port: "in1" },
            { id: "e2", source_node_id: "slow", source_port: "data", target_node_id: "join", target_port: "in2" },
        ],
    });
    await app.open();
    await page.locator(".graph-list-item").filter({ hasText: app.boardId }).first().click();
    await expect(page.locator(".node").first()).toBeVisible({ timeout: 15_000 });

    // Start it, then wait for the strips themselves rather than a timeout: the
    // backend only reports a lane once it has carried something, so their
    // appearance IS the signal that frames are flowing.
    await page.locator(".graph-toolbar .action-btn", { hasText: "Start" }).first().click();
    await expect(page.locator(".marble-row").first()).toBeVisible({ timeout: 45_000 });

    // Let a few seconds of history accumulate so a strip shows a cadence rather
    // than its first marble.
    await page.waitForTimeout(6_000);

    // ⚠️ ASSERT A MARBLE WAS DRAWN, not merely that a row exists. An empty row
    // and a populated one are different claims — the whole point of the feature
    // is what is IN the track — and a row with an empty track is exactly what a
    // broken axis or a bad layout would produce while still passing a
    // "row is visible" check.
    const drawn = await page.evaluate(() => ({
        rows: document.querySelectorAll(".marble-row").length,
        marbles: document.querySelectorAll(".marble-track .marble").length,
        density: document.querySelectorAll(".marble-track .density").length,
        quiet: document.querySelectorAll(".marble-quiet").length,
        counts: [...document.querySelectorAll(".marble-count")].map((n) => n.textContent),
    }));
    console.log("strip contents:", JSON.stringify(drawn));
    expect(drawn.rows).toBeGreaterThan(0);
    expect(drawn.marbles + drawn.density).toBeGreaterThan(0);

    await evidence.shot(
        card(page, "join"),
        "TEC-NATKIT-106",
        "combine-strip",
        "The combine's card, fed a ~50 Hz and a ~5 Hz source under " +
            "combine_latest. The row labelled `data` is the join's ACTUAL " +
            "emission pattern and the number beside it is the exact frame count " +
            "in the four-second window. This is the thing that was previously " +
            "invisible: nothing in the UI reported what a join was really doing.",
    );
    await evidence.shot(
        card(page, "fast"),
        "TEC-NATKIT-106",
        "fast-source-no-strip",
        "The fast source (~50 Hz). A stream_source is not a worker, so it " +
            "records no activity and correctly shows NO strip row at all — " +
            "absence, not an empty row. An empty row would claim its data had " +
            "stopped, which is a different and wrong statement.",
    );
    await evidence.shot(
        card(page, "slow"),
        "TEC-NATKIT-106",
        "slow-source-no-strip",
        "The slow source (~5 Hz), same reasoning. Both sources feed the join " +
            "that does have a strip, so this pair shows the distinction is by " +
            "node kind rather than by whether data is flowing.",
    );
    // Measure the track, do not just look at it. The first version of this
    // feature rendered every density column into a 2px-wide box: correct DOM,
    // passing assertions, invisible strip. A width assertion is the only thing
    // that catches that class of bug.
    const geometry = await page.evaluate(() => {
        const track = document.querySelector(".marble-track");
        const rect = track?.getBoundingClientRect();
        return {
            trackWidth: rect ? Math.round(rect.width) : 0,
            drawn: document.querySelectorAll(".marble-track .marble, .marble-track .density").length,
        };
    });
    console.log("strip geometry:", JSON.stringify(geometry));
    expect(geometry.trackWidth, "the strip track needs real width to say anything")
        .toBeGreaterThan(80);
    expect(geometry.drawn).toBeGreaterThan(0);

    await evidence.shot(
        page.locator(".graph-canvas").first(),
        "TEC-NATKIT-106",
        "canvas-shared-axis",
        "The whole board while running. Every strip on the canvas is placed " +
            "against ONE axis resolved across the graph, so rows are comparable " +
            "between cards; a per-card axis would right-align them all and make " +
            "a stalled input look identical to a live one.",
    );

    // Stop the graph before teardown. A running board cannot be deleted, so
    // leaving it would leak a scratch record and the health check would report
    // the stores as unrestored -- which is a real signal and should not be
    // spent on the test's own untidiness.
    await page.locator(".graph-toolbar .action-btn", { hasText: "Stop" }).first().click();
    await expect(page.locator(".graph-list-item").filter({ hasText: "RUNNING" })).toHaveCount(0, {
        timeout: 20_000,
    });
});

/**
 * TEC-NATKIT-106 — the strips showing a FAILURE, which is what they exist for.
 *
 * The first test proves the strips render and are legible on a healthy graph.
 * That is not the claim the feature makes. The claim is that a starved input, a
 * gap and a stalled join become visible, and none of those is in a healthy
 * capture.
 *
 * ⚠️ THE STARVATION IS CAUSED BY THE TEST, not waited for. An earlier version
 * relied on the feeder's own scripted silent window and had to guess when the
 * graph would be running relative to it -- which is a timing race dressed up as
 * a test. Here the test kills the fast feed itself, so the failure happens at a
 * known moment and the assertions are about cause and effect.
 *
 * Requires BOTH feeds running, one process each:
 *   libnatkit/scripts/natkit_synthetic_feed.py --device fast --seconds 600 &
 *   libnatkit/scripts/natkit_synthetic_feed.py --device slow --seconds 600 &
 */
test("a starved input and a stalled join are visible on the strips", async ({
    page,
    app,
    viewer,
    evidence,
}) => {
    await app.open();
    await app.createScratchBoard();

    // Sources record no activity -- only workers do -- so each branch needs a
    // transform of its own for the branch to have a strip at all.
    await app.attachNodes([
        { ...VpApp.sourceNode(FAST_ID), id: "fast", position: { x: 300, y: 130 } },
        { ...VpApp.sourceNode(SLOW_ID), id: "slow", position: { x: 300, y: 430 } },
        {
            id: "fastx", kind: "transform", label: "Fast rectify",
            transform_kind: "rectify", input_mapping_id: "canonical_channel_frame",
            config: { cutoff_hz: 5 },
            // ⚠️ The backend NORMALISES a transform's ports to input/output
            // (StreamViewerWebSocket.cpp:2448) whatever the saved node says, so
            // edges must use those ids. Using in/out fails validation with
            // "Edge target port does not exist on its node" and the graph never
            // starts -- which presents as zero strips, not as an error.
            input_port_ids: ["input"], output_port_ids: ["output"],
            position: { x: 640, y: 130 }, output_identifier: "gapdemo-fast",
        },
        {
            id: "slowx", kind: "transform", label: "Slow rectify",
            transform_kind: "rectify", input_mapping_id: "canonical_channel_frame",
            config: { cutoff_hz: 5 },
            input_port_ids: ["input"], output_port_ids: ["output"],
            position: { x: 640, y: 430 }, output_identifier: "gapdemo-slow",
        },
        {
            id: "join", kind: "combine", label: "Combine",
            input_port_ids: ["in1", "in2"], output_port_ids: ["out"],
            position: { x: 990, y: 280 }, output_identifier: "gapdemo-join",
            config: { join_policy: "combine_latest" },
        },
    ]);

    const board = await viewer.getGraph(app.boardId);
    if (!board) throw new Error("scratch board vanished");
    const { editor_metadata: _drop, ...rest } = board;
    await page.goto("about:blank");
    await viewer.saveGraph({
        ...rest,
        edges: [
            { id: "e1", source_node_id: "fast", source_port: "data", target_node_id: "fastx", target_port: "input" },
            { id: "e2", source_node_id: "slow", source_port: "data", target_node_id: "slowx", target_port: "input" },
            { id: "e3", source_node_id: "fastx", source_port: "output", target_node_id: "join", target_port: "in1" },
            { id: "e4", source_node_id: "slowx", source_port: "output", target_node_id: "join", target_port: "in2" },
        ],
    });
    await app.open();
    await page.locator(".graph-list-item").filter({ hasText: app.boardId }).first().click();
    await expect(page.locator(".node").first()).toBeVisible({ timeout: 15_000 });

    // Surface a validation failure as itself. A bad edge means the graph never
    // starts, which otherwise shows up only as "0 strips after 45s" -- a
    // timeout that says nothing about the cause.
    const diagnostics = await page.locator(".diagnostic-item, .diagnostics-list li").allInnerTexts();
    expect(diagnostics.join(" | "), "the board must validate before it can run").not.toContain(
        "does not exist",
    );

    await page.locator(".graph-toolbar .action-btn", { hasText: "Start" }).first().click();
    // Three strips: both branches and the join. Waiting for the third is the
    // signal that frames are reaching the join, not just the transforms.
    await expect(page.locator(".marble-row")).toHaveCount(3, { timeout: 45_000 });
    await page.waitForTimeout(6_000);

    const totals = async () => {
        const read = async (nodeId: string) =>
            Number((await card(page, nodeId).locator(".marble-count").first().innerText()).trim());
        return { fast: await read("fastx"), slow: await read("slowx"), join: await read("join") };
    };

    const healthy = await totals();
    console.log("healthy totals:", JSON.stringify(healthy));
    expect(healthy.fast).toBeGreaterThan(healthy.slow);  // 50 Hz vs 5 Hz

    await evidence.shot(
        page.locator(".graph-canvas").first(),
        "TEC-NATKIT-106",
        "healthy-three-lanes",
        "Baseline: both branches and the join, all flowing. The fast branch " +
            "renders as a density bar and the slow one as individual marbles — " +
            "the exact/density switch — on one shared axis, so the cadence " +
            "difference is readable across cards.",
    );

    // Starve the fast branch. One process per device is exactly so this can be
    // done to one of them.
    const { execFileSync } = await import("node:child_process");
    try {
        execFileSync("pkill", ["-f", "natkit_synthetic_feed.py --device fast"]);
    } catch {
        // pkill exits 1 when nothing matched; the assertions below are the real
        // check, so a miss shows up as "fast kept growing" rather than silence.
    }
    await page.waitForTimeout(7_000);

    const starved = await totals();
    const flags = await page.evaluate(() => {
        const of = (nodeId: string) => {
            const port = document.querySelector(`[data-node-id="${nodeId}"]`);
            const card = port?.closest(".node");
            const row = card?.querySelector(".marble-row");
            const marks = [...(row?.querySelectorAll(".marble, .density") ?? [])];
            const lefts = marks.map((m) => parseFloat((m as HTMLElement).style.left) || 0);
            return {
                stale: !!row?.classList.contains("stale"),
                quiet: !!row?.querySelector(".marble-quiet"),
                rightmost: lefts.length ? Math.max(...lefts) : null,
            };
        };
        return { fast: of("fastx"), slow: of("slowx"), join: of("join") };
    });
    console.log("starved totals:", JSON.stringify(starved));
    console.log("starved flags:", JSON.stringify(flags));

    await evidence.shot(
        page.locator(".graph-canvas").first(),
        "TEC-NATKIT-106",
        "starved-input-and-stalled-join",
        "The fast feed was killed 7s before this shot. Its branch has gone " +
            "stale — dimmed, marbles gone from the window — while the slow " +
            "branch keeps advancing on the shared axis. The join has gone " +
            "stale with it, which is combine_latest holding at the slowest " +
            "input's high-water mark rather than running on stale data. Three " +
            "of the four failure modes the strips exist to reveal, in one frame.",
    );
    await evidence.shot(
        card(page, "fastx"),
        "TEC-NATKIT-106",
        "starved-branch-card",
        "The starved branch alone. Its count is FROZEN, not decaying: each lane " +
            "is snapshotted against its own newest event, so a dead lane keeps " +
            "reporting its last four seconds. Staleness is what says it stopped " +
            "— and staleness is only computable because the axis is shared " +
            "across the graph. A per-card axis would have right-aligned this " +
            "and made it look perfectly healthy.",
    );

    // Stop BEFORE asserting, so a failed expectation cannot leave a running
    // board behind: a running graph cannot be deleted, so the leak would show
    // up as a stores-not-restored health failure and mask the real error.
    await page.locator(".graph-toolbar .action-btn", { hasText: "Stop" }).first().click();
    await expect(page.locator(".graph-list-item").filter({ hasText: "RUNNING" })).toHaveCount(0, {
        timeout: 20_000,
    });

    // ⚠️ THE COUNT DOES NOT DECAY, and asserting that it does was wrong about
    // this feature's own design. `total` is events in the four-second WINDOW,
    // and each lane is snapshotted against its OWN newest event -- so a steady
    // 5 Hz lane sits at 20 for ever and a dead lane freezes rather than
    // draining. What distinguishes them is STALENESS, computed in the frontend
    // against the shared axis.
    expect(flags.fast.stale, "the starved branch must read as stale").toBe(true);
    expect(flags.fast.quiet, "and must say so, not show an empty track").toBe(true);
    expect(flags.slow.stale, "the still-fed branch must NOT be stale").toBe(false);
    // The join stalls with its starved input, by design: combine_latest holds at
    // the slowest input's high-water mark (CombineJoin.hpp) rather than emitting
    // on stale data. Here that is on real frames rather than in a unit test.
    expect(flags.join.stale, "the join must stall behind its starved input").toBe(true);
    // The counts corroborate: frozen, not growing.
    expect(starved.fast).toBeLessThanOrEqual(healthy.fast);
    expect(starved.join).toBeLessThanOrEqual(healthy.join + 2);
});
