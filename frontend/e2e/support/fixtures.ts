/**
 * The fixtures every spec builds on.
 *
 * Two things every throwaway verification script re-implemented, now in one
 * place: a scratch board + experiment that is *guaranteed* deleted, and a
 * WebSocket client for the setup/teardown the UI is a bad tool for.
 *
 * The teardown is the important part. A script that threw before its cleanup
 * leaked a scratch board AND experiment into the real store — twice — so
 * cleanup lives in fixture teardown, which Playwright runs even when the test
 * fails or times out.
 */
import { test as base, expect } from "@playwright/test";
import { Evidence } from "./evidence";
import { SCRATCH_PREFIX, VpApp, scratchLabel } from "./app";
import { Designer } from "./designer";
import { ViewerSocket } from "./protocol";

/**
 * Console errors that are not the app's fault. Empty on purpose: every entry
 * here is a hole in the guard, so add one only with a reason.
 */
const IGNORED_CONSOLE_ERRORS: RegExp[] = [];

export interface RunHealth {
    nativeDialogs: string[];
    consoleErrors: string[];
    /** Filled in by the `app` fixture's teardown. */
    storesRestored: boolean | null;
    leftoversCleaned: string[];
}

interface Fixtures {
    evidence: Evidence;
    health: RunHealth;
    viewer: ViewerSocket;
    app: VpApp;
    /** A scratch experiment bound to a scratch board, designer open. */
    designer: Designer;
    scratchLabel: string;
}

export const test = base.extend<Fixtures>({
    evidence: async ({}, use, testInfo) => {
        await use(new Evidence(testInfo.title));
    },

    scratchLabel: async ({}, use, testInfo) => {
        await use(scratchLabel(testInfo.title));
    },

    viewer: async ({ baseURL }, use) => {
        const wsUrl = `${(baseURL ?? "http://localhost:8080").replace(/^http/, "ws")}/ws/stream_viewer`;
        const socket = await ViewerSocket.open(wsUrl);
        await use(socket);
        socket.close();
    },

    /**
     * Attaches the two guards before anything navigates, and asserts them
     * afterwards. "No native dialog is ever raised" is the standing regression
     * guard for the in-app dialog work: a reintroduced `window.confirm` would
     * otherwise pass every DOM assertion in the suite.
     */
    health: async ({ page, evidence }, use, testInfo) => {
        const health: RunHealth = {
            nativeDialogs: [],
            consoleErrors: [],
            storesRestored: null,
            leftoversCleaned: [],
        };
        page.on("dialog", async (dialog) => {
            health.nativeDialogs.push(`${dialog.type()}: ${dialog.message()}`);
            await dialog.dismiss();
        });
        page.on("console", (message) => {
            if (message.type() !== "error") {
                return;
            }
            const text = message.text();
            if (IGNORED_CONSOLE_ERRORS.some((pattern) => pattern.test(text))) {
                return;
            }
            health.consoleErrors.push(text);
        });
        page.on("pageerror", (error) => {
            health.consoleErrors.push(`uncaught: ${error.message}`);
        });

        await use(health);

        evidence.recordHealth({ test: testInfo.title, ...health });
        expect(health.nativeDialogs, "no native browser dialog should be raised").toEqual([]);
        expect(health.consoleErrors, "no console errors").toEqual([]);
    },

    app: async ({ page, viewer, health }, use) => {
        // The baseline the stores must be returned to. Scratch records left by an
        // earlier crashed run are excluded from it and cleaned up below, so a
        // leak is self-healing rather than permanently poisoning the comparison.
        const before = await viewer.census();
        const isScratch = (label?: string) => (label ?? "").startsWith(SCRATCH_PREFIX);
        const leftovers = before.experiments.filter((experiment) => isScratch(experiment.label));
        const baseline = {
            graphs: before.graphs.length,
            experiments: before.experiments.length - leftovers.length,
        };

        const app = new VpApp(page, viewer);
        await app.open();
        await app.createScratchBoard();

        try {
            await use(app);
        } finally {
            // Stop the editor before deleting anything: its debounced auto-save
            // would otherwise resurrect the board we just removed.
            await page.goto("about:blank").catch(() => undefined);

            // ⚠️ GRAPHS FIRST, then experiments, and the order is load-bearing.
            // The backend refuses to delete an experiment that still owns
            // instances — correctly, since removing it would orphan immutable
            // snapshots reachable only through it. Deleting experiments first
            // therefore leaked one for any test that records, and the only
            // symptom was `storesRestored` failing afterwards, which points at
            // the count rather than at the cause.
            const knownGraphs = new Set(before.graphs.map((graph) => graph.graph_id));
            const stale = (await viewer.listGraphs()).filter(
                (graph) => !knownGraphs.has(graph.graph_id),
            );
            const cleanupErrors: string[] = [];
            for (const graph of stale) {
                // `force` because a scratch recording is sealed and would
                // otherwise refuse to go.
                await viewer.deleteGraph(graph.graph_id, true).catch((error) => {
                    cleanupErrors.push(`graph ${graph.graph_id}: ${error.message}`);
                });
            }

            const after = await viewer.census();
            for (const experiment of after.experiments.filter((e) => isScratch(e.label))) {
                // ⚠️ The reason is KEPT rather than swallowed. A silent catch here
                // turned "cannot delete: it still has 1 instance" into a bare
                // count mismatch, and I spent a while looking in the wrong place.
                await viewer.deleteExperiment(experiment.experiment_id).catch((error) => {
                    cleanupErrors.push(`experiment ${experiment.experiment_id}: ${error.message}`);
                });
                if (leftovers.some((l) => l.experiment_id === experiment.experiment_id)) {
                    health.leftoversCleaned.push(experiment.experiment_id);
                }
            }

            const end = await viewer.census();
            health.storesRestored =
                end.graphs.length === baseline.graphs &&
                end.experiments.length === baseline.experiments;
            expect(
                health.storesRestored,
                `stores not restored: ${end.graphs.length}/${baseline.graphs} boards, ` +
                    `${end.experiments.length}/${baseline.experiments} experiments` +
                    (cleanupErrors.length > 0
                        ? `. Cleanup errors: ${cleanupErrors.join("; ")}`
                        : ""),
            ).toBe(true);
        }
    },

    designer: async ({ app, scratchLabel }, use) => {
        await app.createExperiment(scratchLabel);
        await use(new Designer(app));
    },
});

export { expect };
