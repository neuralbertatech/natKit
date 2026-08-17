import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests for the Visual Programming UI, run against the dev stack.
 *
 * These drive ONE shared backend and mutate its board/experiment stores, so
 * they are deliberately serial: `workers: 1` and no retries. A retry would also
 * duplicate entries in the screenshot ledger, and a second worker would race
 * another test's scratch data.
 *
 * Auth is open on the dev stack, so there is no login step.
 */
export default defineConfig({
    testDir: "./e2e",
    workers: 1,
    fullyParallel: false,
    retries: 0,
    forbidOnly: !!process.env.CI,
    timeout: 120_000,
    expect: { timeout: 15_000 },
    reporter: [["list"]],
    // Playwright's own failure artifacts (traces, videos) stay out of git.
    outputDir: "./test-results",
    globalSetup: "./e2e/support/global-setup.ts",
    globalTeardown: "./e2e/support/global-teardown.ts",
    use: {
        baseURL: process.env.NATKIT_E2E_BASE_URL ?? "http://localhost:8080",
        // Fixed viewport and 2x scale so the screenshot set is visually
        // consistent shot to shot and legible once attached to a ticket.
        viewport: { width: 1600, height: 1050 },
        deviceScaleFactor: 2,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
    },
});
