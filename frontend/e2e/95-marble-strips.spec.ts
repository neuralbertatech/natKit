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
