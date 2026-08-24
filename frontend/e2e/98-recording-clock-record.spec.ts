/**
 * TEC-NATKIT-77 (#442) — a sealed recording's clock record, as the instance
 * inspector shows it.
 *
 * The backend half was verified against the live rig by reading the record back
 * out of the store. This is the half that was not, and could not be until
 * TEC-NATKIT-80 was fixed: two separate bugs were hiding a freshly sealed run
 * from the sidebar entirely.
 *
 * The case pinned here is the AWKWARD one on purpose. A scratch board has no
 * source nodes, so this run has no devices to vouch for — and before this test
 * existed the summary read "all 0 held", a statement about an empty set dressed
 * as a clean bill, on precisely the run whose sources were never resolved.
 */
import { expect, test } from "./support/fixtures";
import { VpApp } from "./support/app";

test("a sealed run shows its clock record, and says so when there is nothing to vouch for", async ({
    app,
    designer,
    viewer,
    page,
    evidence,
}) => {
    await designer.close();

    const experiments = await viewer.listExperiments();
    const bound = experiments.find((experiment) => experiment.live_graph_id === app.boardId);
    expect(bound, "the scratch experiment should be bound to the scratch board").toBeTruthy();

    const started = (await viewer.request("start_experiment_instance", {
        experiment_id: bound!.experiment_id,
        participant_id: "e2e-clock-record",
    })) as Record<string, unknown>;
    const instance = (started["instance"] ?? {}) as Record<string, unknown>;
    const instanceId = String(instance["graph_id"] ?? started["graph_id"] ?? "");
    expect(instanceId, "the backend did not return an instance id").not.toEqual("");
    await viewer.request("finish_experiment_instance", {
        graph_id: instanceId,
        completed: true,
    });

    // Reload so the sidebar lists the new run, then select it by graph id.
    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator(".conn-pill.connected")).toBeVisible({ timeout: 20_000 });
    await app.openInstance(instanceId);

    const record = page.locator(".clock-record");
    await expect(record).toBeVisible({ timeout: 10_000 });
    const summary = record.locator(".summary-row strong");

    // The assertion that matters: never a reassurance about nothing.
    await expect(summary).toHaveText("no devices recorded");
    await expect(summary).toHaveClass(/clock-troubled/);

    await evidence.shot(
        record,
        "442",
        "clock-record-no-devices",
        "A sealed run with no source nodes: the clock record says 'no devices recorded' rather than 'all 0 held'. A run whose sources were never resolved is exactly when the reader needs telling, not reassuring.",
    );
});

/**
 * TEC-NATKIT-80 — the regression test for the two bugs that hid this run.
 *
 * Both were silent: no error, no empty state, just history that was not there.
 */
test("every recorded run appears in the instance tree, whatever its outcome", async ({
    app,
    designer,
    viewer,
    page,
}) => {
    await designer.close();
    const experiments = await viewer.listExperiments();
    const bound = experiments.find((experiment) => experiment.live_graph_id === app.boardId)!;

    // Two runs, so this experiment has a run-0001 AND a run-0002 of its own.
    const ids: string[] = [];
    for (let i = 0; i < 2; i += 1) {
        const started = (await viewer.request("start_experiment_instance", {
            experiment_id: bound.experiment_id,
            participant_id: `e2e-tree-${i}`,
        })) as Record<string, unknown>;
        const inst = (started["instance"] ?? {}) as Record<string, unknown>;
        const id = String(inst["graph_id"] ?? started["graph_id"] ?? "");
        await viewer.request("finish_experiment_instance", { graph_id: id, completed: true });
        ids.push(id);
    }

    await page.reload({ waitUntil: "networkidle" });
    await expect(page.locator(".conn-pill.connected")).toBeVisible({ timeout: 20_000 });

    // ⚠️ Run numbering restarts per experiment, so the store holds several
    // "run-0001"s. Keying the tree's node map on `instance_id` made them collide
    // and `Map.set` kept only the last — on the dev store that silently dropped a
    // third of all recorded history, all the survivors belonging to one experiment.
    for (const id of ids) {
        await expect(
            page.locator(`.tree-instance[data-graph-id="${id}"]`),
            `run ${id} should be in the tree`,
        ).toHaveCount(1);
    }

    // And every run in the store is on screen — not just these two.
    const storeRuns = (await viewer.listGraphs()).filter(
        (graph) => !!graph.instance_id && !graph.workspace_id,
    ).length;
    const shown = await page.locator(".tree-instance").count();
    expect(shown, "every unfiled run in the store should have a row").toBe(storeRuns);
});

/**
 * The per-device rows — the half of TEC-NATKIT-77's rendering that the
 * no-devices case above cannot reach.
 *
 * ⚠️ Needs hardware. It SKIPS rather than fails when no device is publishing a
 * clock fit: "no rig attached" is not a regression, and a test that fails for it
 * teaches people to ignore red.
 */
test("a run with a real device records and shows that device's clock", async ({
    app,
    designer,
    viewer,
    page,
    evidence,
}) => {
    const devices = await viewer.devicesWithClockFit();
    test.skip(
        devices.length === 0,
        "no device is publishing a clock fit — the rig is not attached",
    );

    await designer.close();
    // ⚠️ The device id is DISCOVERED, never hardcoded: these are hardware ids that
    // change when a board is swapped, and a pinned one fails months later for a
    // reason that looks nothing like its cause.
    const deviceId = devices[0];
    await app.attachNodes([VpApp.sourceNode(deviceId)]);

    const experiments = await viewer.listExperiments();
    const bound = experiments.find((experiment) => experiment.live_graph_id === app.boardId)!;
    const started = (await viewer.request("start_experiment_instance", {
        experiment_id: bound.experiment_id,
        participant_id: "e2e-clock-device",
    })) as Record<string, unknown>;
    const instance = (started["instance"] ?? {}) as Record<string, unknown>;
    const instanceId = String(instance["graph_id"] ?? started["graph_id"] ?? "");

    // Long enough that the beacon counters move, so the differenced rate is real.
    await page.waitForTimeout(7000);
    await viewer.request("finish_experiment_instance", {
        graph_id: instanceId,
        completed: true,
    });

    await app.open();
    await app.openInstance(instanceId);

    const record = page.locator(".clock-record");
    await expect(record).toBeVisible({ timeout: 10_000 });

    // A row for that device, saying something specific about it.
    const row = record.locator(".clock-device", { hasText: deviceId });
    await expect(row, `a row for device ${deviceId}`).toHaveCount(1);
    const note = (await row.locator(".clock-note").first().textContent()) ?? "";
    // ⚠️ Whatever it says, it must be a CLAIM — not the "does not report one"
    // wording, which would mean the recording never saw the device it recorded.
    expect(note).not.toMatch(/does not report one/i);
    expect(note).toMatch(/fit held|no usable fit|stopped reporting/i);

    await evidence.shot(
        record,
        "442",
        "clock-record-with-device",
        `A run recorded with a live device attached: the sealed instance carries that device's clock fit, differenced over the run. This is the record that outlives the status frames it came from — they age out of Kafka long before anybody asks.`,
    );
});
