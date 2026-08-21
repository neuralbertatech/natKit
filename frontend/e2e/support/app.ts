/**
 * Page object for the Visual Programming editor: getting there, and getting a
 * scratch board + experiment to work on.
 *
 * Gotchas encoded here so no future test has to rediscover them:
 * - deep-linking `/VisualProgramming` does NOT route (tinro lands on Home), so
 *   the nav link has to be clicked;
 * - a board created in the editor only reaches the backend through a debounced
 *   auto-save, and an experiment cannot bind to a board the backend has never
 *   seen — so board creation waits for the store, not for a timeout;
 * - never reload and assume the same board is selected. The page picks its own,
 *   which once made a test read a different experiment.
 */
import { expect, type Locator, type Page } from "@playwright/test";
import type { ViewerSocket } from "./protocol";

/** Every scratch record the suite creates is labelled with this prefix. */
export const SCRATCH_PREFIX = "E2E Scratch";

export function scratchLabel(testTitle: string): string {
    return `${SCRATCH_PREFIX} — ${testTitle}`.slice(0, 80);
}

export class VpApp {
    /** Board id of the scratch board this run created. */
    boardId = "";

    constructor(
        readonly page: Page,
        readonly viewer: ViewerSocket,
    ) {}

    async open(): Promise<void> {
        await this.page.goto("/", { waitUntil: "networkidle" });
        await this.page.click("text=Visual Programming");
        await expect(this.page.locator(".graph-sidebar")).toBeVisible({ timeout: 20_000 });
        // Wait for the socket, not for a timeout. Every editor action that talks
        // to the backend returns false and only sets an error string when the
        // socket is not connected yet — so a Save clicked too early is a silent
        // no-op, which is exactly how the first version of this suite "lost" its
        // scratch boards.
        await expect(this.page.locator(".conn-pill.connected")).toBeVisible({ timeout: 20_000 });
    }

    /**
     * Create an empty board and wait until the backend has it.
     *
     * A new board is a local draft: there is no auto-save for one, so it is
     * saved explicitly. That matters for teardown — the suite can only delete
     * what the store knows about — and for binding, since `save_experiment`
     * refuses to stamp a board the backend has never seen.
     */
    async createScratchBoard(): Promise<string> {
        await this.page.locator(".sidebar-header .sidebar-actions .icon-btn").first().click();
        const boardId = (await this.page.locator(".graph-id").first().innerText()).trim();
        expect(boardId).not.toEqual("");
        await this.page.locator(".graph-toolbar .action-btn", { hasText: "Save" }).first().click();
        await this.viewer.waitForGraph(boardId);
        this.boardId = boardId;
        return boardId;
    }

    async openExperimentPanel(): Promise<Locator> {
        const panel = this.page.locator(".experiment-panel");
        if (!(await panel.isVisible())) {
            await this.page.click(".experiment-pill");
        }
        await expect(panel).toBeVisible();
        return panel;
    }

    /** The in-app name dialog, which replaced `window.prompt`. */
    get dialog(): Locator {
        return this.page.locator(".dialog-panel");
    }

    async startCreateExperiment(): Promise<Locator> {
        await this.openExperimentPanel();
        await this.page.click('button[title="Create a new experiment bound to this board"]');
        await expect(this.dialog).toBeVisible();
        return this.dialog;
    }

    /**
     * Create an experiment bound to the scratch board. The designer opens by
     * itself — a brand-new experiment's next step is authoring its protocol.
     */
    async createExperiment(label: string): Promise<void> {
        await this.startCreateExperiment();
        await this.page.fill(".dialog-field input", label);
        await this.page.press(".dialog-field input", "Enter");
        await expect(this.page.locator(".designer-panel")).toBeVisible({ timeout: 15_000 });
    }

    /**
     * Wait until the STORED protocol of the experiment bound to the scratch board
     * satisfies `match`.
     *
     * Protocol edits are debounced (400ms) and the editor drops its local pending
     * copy when it sends the save, so between send and echo the designer briefly
     * renders the last-saved protocol instead of the edited one. Anything holding
     * a reference INTO the protocol across that window — the canvas remembers
     * which group it is zoomed into by step id — gets reset. Waiting for the
     * round trip to complete is how a test avoids that window instead of racing
     * it with a sleep.
     */
    /**
     * Select a sealed run in the sidebar's instance tree.
     *
     * ⚠️ By its graph id, via `data-graph-id`, NOT by its "run-0001" label.
     * Run numbering restarts per experiment, so several boards in the store have a
     * run-0001 — an unscoped `hasText: /run-\d{4}/` picks whichever renders first,
     * which is how a verification "passed" against somebody else's recording twice
     * before this helper existed.
     */
    async openInstance(graphId: string): Promise<void> {
        // ⚠️ `data-graph-id`, not `title`: the title is the run's MESSAGE when it
        // has one, so a title selector silently fails to find any run that failed
        // or was stopped early — which is exactly the run you go looking for.
        const entry = this.page.locator(`.tree-instance[data-graph-id="${graphId}"]`);
        await expect(entry, `no instance row for ${graphId}`).toBeVisible({ timeout: 15_000 });
        await entry.click();
        // The inspector is keyed on the selection, so wait for it to catch up
        // rather than asserting against the previously selected record.
        await expect(this.page.locator(".graph-inspector")).toContainText("Instance");
    }

    async waitForStoredProtocol(
        match: (protocol: Record<string, unknown>) => boolean,
        timeoutMs = 15_000,
    ): Promise<void> {
        const deadline = Date.now() + timeoutMs;
        for (;;) {
            const experiments = await this.viewer.listExperiments();
            const bound = experiments.find(
                (experiment) => experiment.live_graph_id === this.boardId,
            );
            const protocol = (bound?.protocol ?? {}) as Record<string, unknown>;
            if (bound && match(protocol)) {
                return;
            }
            if (Date.now() > deadline) {
                throw new Error(
                    `the stored protocol for the board ${this.boardId} never matched: ` +
                        JSON.stringify(protocol).slice(0, 200),
                );
            }
            await this.page.waitForTimeout(150);
        }
    }
}
