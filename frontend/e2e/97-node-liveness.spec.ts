import { expect, test } from "./support/fixtures";
import { VpApp } from "./support/app";

/**
 * TEC-NATKIT-116 — a node's state tracks whether it is being FED, not only
 * whether it is emitting.
 *
 * A healthy gap detector reported `stalled` and, because `derived_run_state` is
 * "any stalled node → the whole board is stalled", marked an entire healthy
 * board unhealthy. The node whose job is to report faults looked broken
 * precisely when there were none.
 *
 * ⚠️ THE EVIDENCE HAS TO SHOW BOTH DIRECTIONS. A shot of a green board proves
 * nothing on its own: the naive fix — "never call these kinds stalled" — makes
 * exactly the same picture, while reporting health forever for a detector whose
 * upstream has died (which is TEC-NATKIT-123 all over again). So the pair of
 * shots is the evidence, and the second is the one that distinguishes the two
 * implementations.
 *
 * ⚠️ REQUIRES A LIVE FEED for the first half and its ABSENCE for the second, so
 * this test owns the feed rather than depending on an ambient one:
 * `libnatkit/scripts/natkit_synthetic_feed.py --device fast`.
 */
const FAST_ID = "909001";

function card(page: import("@playwright/test").Page, nodeId: string) {
    return page
        .locator(".node")
        .filter({ has: page.locator(`[data-node-id="${nodeId}"]`) })
        .first();
}

async function nodeStates(page: import("@playwright/test").Page) {
    return page.evaluate(() =>
        [...document.querySelectorAll(".node")].map((node) => ({
            label: node.querySelector(".node-label")?.textContent?.trim() ?? "",
            badge:
                node.querySelector(".node-runtime-badge")?.textContent?.trim() ?? "",
        })),
    );
}

test("a silent operator on a live feed is not reported as stalled", async ({
    page,
    app,
    viewer,
    evidence,
}) => {
    const { spawn } = await import("node:child_process");
    const { resolve } = await import("node:path");
    const feedScript = resolve(
        process.cwd(),
        "../libnatkit/scripts/natkit_synthetic_feed.py",
    );
    const feed = spawn("python3", [feedScript, "--device", "fast", "--seconds", "300"], {
        stdio: "ignore",
    });

    try {
        await app.open();
        await app.createScratchBoard();

        // Two operators that are silent while perfectly healthy:
        //   gap_detect  — speaks only when data DROPS OUT, so silence is health
        //   threshold   — level far above the signal, so it never crosses
        // Both used to read `stalled` here, and either one alone dragged the
        // board's run_state down with it.
        await app.attachNodes([
            {
                ...VpApp.sourceNode(FAST_ID),
                id: "src",
                label: "Fast 400Hz",
                position: { x: 320, y: 260 },
            },
            {
                id: "gap",
                kind: "gap_detect",
                label: "Gap detector",
                input_port_ids: ["in"],
                output_port_ids: ["markers"],
                position: { x: 780, y: 140 },
                output_identifier: "liveness-gap",
                // Far longer than any gap this feed produces.
                config: { gap_ms: 2000 },
            },
            {
                id: "thr",
                kind: "threshold",
                label: "Threshold (never fires)",
                input_port_ids: ["in"],
                output_port_ids: ["markers"],
                position: { x: 780, y: 420 },
                output_identifier: "liveness-thr",
                // ⚠️ 1000.0 against a signal that never approaches it, on
                // purpose: a permanently silent operator on a healthy stream.
                config: { level: 1000.0, direction: "either" },
            },
        ]);

        const board = await viewer.getGraph(app.boardId);
        if (!board) throw new Error("scratch board vanished");
        const { editor_metadata: _drop, ...rest } = board;
        await page.goto("about:blank");
        await viewer.saveGraph({
            ...rest,
            edges: [
                {
                    id: "e1",
                    source_node_id: "src",
                    source_port: "data",
                    target_node_id: "gap",
                    target_port: "in",
                },
                {
                    id: "e2",
                    source_node_id: "src",
                    source_port: "data",
                    target_node_id: "thr",
                    target_port: "in",
                },
            ],
        });
        await app.open();
        await page
            .locator(".graph-list-item")
            .filter({ hasText: app.boardId })
            .first()
            .click();
        await expect(page.locator(".node").first()).toBeVisible({ timeout: 15_000 });

        await page
            .locator(".graph-toolbar .action-btn", { hasText: "Start" })
            .first()
            .click();

        // ⚠️ WAIT PAST THE STALL WINDOW. It is 3s, and a node inside its first
        // 3s reads `starting` — so a shot taken too early would show a healthy
        // badge that says nothing about this fix.
        await page.waitForTimeout(9_000);

        const fedStates = await nodeStates(page);
        console.log("fed:", JSON.stringify(fedStates));
        const fedBadges = new Set(fedStates.map((n) => n.badge));
        expect(
            [...fedBadges].join(","),
            "a silent operator on a healthy feed must not read stalled",
        ).not.toContain("stalled");

        await evidence.shot(
            page.locator(".graph-canvas").first(),
            "TEC-NATKIT-116",
            "fed-silent-operators-live",
            "The board with its feed running. Both the gap detector and the " +
                "threshold have emitted NOTHING — the detector has no dropout to " +
                "report and the threshold's level is above the signal — and both " +
                "now read `live` rather than `stalled`. Before this change either " +
                "one alone made the whole board's run_state `stalled` while its " +
                "data was flowing normally.",
        );
        await evidence.shot(
            card(page, "gap"),
            "TEC-NATKIT-116",
            "gap-detector-fed",
            "The gap detector close up, on a healthy stream. The input row is " +
                "dense and the marker row is empty: 'watching, nothing to " +
                "report'. That picture is the healthy case, and it is the one " +
                "that used to be labelled stalled.",
        );

        // ── The other direction ────────────────────────────────────────────
        // ⚠️ THIS IS THE SHOT THAT MATTERS. A per-kind exemption produces the
        // two shots above just as well; only this one tells the two apart.
        feed.kill("SIGTERM");
        await page.waitForTimeout(9_000);

        const deadStates = await nodeStates(page);
        console.log("dead:", JSON.stringify(deadStates));
        const operatorBadges = deadStates
            .filter((n) => /Gap detector|Threshold/.test(n.label))
            .map((n) => n.badge);
        expect(
            operatorBadges.join(","),
            "with the upstream dead, silence is no longer excusable",
        ).toContain("stalled");

        await evidence.shot(
            page.locator(".graph-canvas").first(),
            "TEC-NATKIT-116",
            "unfed-operators-stalled",
            "The same board with its feed killed. Both operators now read " +
                "`stalled` — nothing is arriving, which is a real fault and says " +
                "so. This is the shot the fix has to earn: excusing these kinds " +
                "by name would leave them reading `live` here forever, which is " +
                "the same lie as a dead board quoting its last known rates " +
                "(TEC-NATKIT-123).",
        );

        await page
            .locator(".graph-toolbar .action-btn", { hasText: "Stop" })
            .first()
            .click();
        await expect(
            page.locator(".graph-list-item").filter({ hasText: "RUNNING" }),
        ).toHaveCount(0, { timeout: 20_000 });
    } finally {
        if (feed.exitCode === null) feed.kill("SIGKILL");
    }
});
