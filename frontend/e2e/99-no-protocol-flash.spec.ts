/**
 * TEC-NATKIT-19 (#342) — the designer must not re-render the PREVIOUS protocol
 * while a debounced edit is in flight.
 *
 * This reproduces the ticket's own measurement rather than asserting a
 * symptom-free end state, because the end state was always correct. The bug was
 * a MutationObserver record over the designer body that looked like this:
 *
 *   3892  qs=1 steps=0      recipe card mounts
 *   4303  qs=0 steps=3      pre-edit step list is BACK   <- the flash
 *   4314  qs=1 steps=0      recipe card returns
 *
 * ~410ms after the edit — the 400ms debounce — the pre-edit protocol came back
 * for ~11ms, because the pending edit was cleared when the save was SENT rather
 * than when the backend echoed it.
 *
 * ⚠️ The assertion is about the whole interval, not its ends. An end-state check
 * passes on the broken code.
 */
import { expect, test } from "./support/fixtures";

test("a protocol edit never re-renders the previous protocol", async ({ designer }) => {
    const page = designer.page;
    await designer.convertToSteps();
    const before = (await designer.stepKinds()).length;
    expect(before).toBeGreaterThan(0);

    // Record every mutation of the designer body across the whole round trip.
    await page.evaluate(() => {
        const w = window as unknown as { __flash?: { t: number; steps: number }[] };
        w.__flash = [];
        const body = document.querySelector(".designer-body");
        if (!body) throw new Error("no .designer-body to observe");
        const sample = () =>
            w.__flash!.push({
                t: Math.round(performance.now()),
                steps: document.querySelectorAll(
                    ".designer-body > .step-list > .step-card",
                ).length,
            });
        sample();
        new MutationObserver(sample).observe(body, { childList: true, subtree: true });
    });

    // The same queue -> 400ms debounce -> save -> echo path the ticket measured.
    await designer.body
        .locator(".step-add:not(.nested) .add-step-btn", { hasText: "Cue" })
        .first()
        .click();
    await expect(designer.steps).toHaveCount(before + 1);

    // Well past the debounce and any plausible round trip.
    await page.waitForTimeout(2500);

    const samples = await page.evaluate(
        () => (window as unknown as { __flash: { t: number; steps: number }[] }).__flash,
    );
    const counts = samples.map((s) => s.steps);
    console.log(`step-card counts across the round trip: ${counts.join(",")}`);

    // Once the list has grown it must never shrink back to the pre-edit length.
    const grewAt = counts.findIndex((n) => n === before + 1);
    expect(grewAt, "the added step never appeared").toBeGreaterThanOrEqual(0);
    const reverted = counts.slice(grewAt).filter((n) => n <= before);
    expect(
        reverted,
        `the designer reverted to the pre-edit protocol: ${counts.join(",")}`,
    ).toEqual([]);
});
