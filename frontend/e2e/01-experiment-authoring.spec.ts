/**
 * TEC-NATKIT-3 (#314) — the experiment authoring surface.
 *
 * Creating and binding an experiment, the designer overlay, labelled step
 * fields, and the compiled-timeline strip.
 */
import { expect, test } from "./support/fixtures";

test("creating an experiment binds it to the board and opens the designer", async ({
    app,
    designer,
    scratchLabel,
    evidence,
}) => {
    // The toolbar pill is where the binding is visible at a glance.
    await expect(app.page.locator(".experiment-pill")).toHaveText(new RegExp(scratchLabel.slice(0, 20)));
    await expect(app.page.locator(".experiment-pill")).toHaveClass(/bound/);
    await expect(designer.panel).toHaveAttribute("role", "dialog");

    await evidence.shot(
        designer.panel,
        "314",
        "designer-opens-on-create",
        "A new experiment is bound to the board and the designer opens straight away — a brand-new experiment's next step is authoring its protocol.",
    );

    // Esc closes the overlay; "Edit protocol" on the operator card reopens it.
    await designer.close();
    const panel = await app.openExperimentPanel();
    await expect(panel.locator(".protocol-card")).toBeVisible();
    await evidence.shot(
        panel,
        "314",
        "operator-status-card",
        "With the designer closed, the board-level panel is the operator's status card: what is bound, participant and notes, a protocol summary, Record/Stop and the run history. Authoring lives behind 'Edit protocol'.",
    );
    await panel.locator(".edit-protocol").click();
    await expect(designer.panel).toBeVisible();
});

test("every step field is labelled and the timeline compiles", async ({ designer, evidence }) => {
    await designer.convertToSteps();

    const group = designer.groups.first();
    const cue = designer.page.locator(".group-children > .step-card.kind-cue").first();

    // The original complaint was unlabelled fields: assert the labels by name.
    for (const label of ["Step type", "Shown to participant", "Class label (trained on)", "Hold (s)", "± Jitter (s)"]) {
        await expect(cue.locator("label", { hasText: label }).first()).toBeVisible();
    }
    for (const label of ["Times", "Shuffle each pass", "Rest between steps", "Tutorial"]) {
        await expect(group.locator("label", { hasText: label }).first()).toBeVisible();
    }
    await evidence.shot(
        cue,
        "314",
        "labelled-step-fields",
        "A cue step: every field carries its name and a tooltip saying what it is for. 'Class label (trained on)' is the field that says which parts of a recording a classifier learns from.",
    );

    const shape = await designer.timelineShape();
    expect(shape.segments).toBeGreaterThan(0);
    await expect(designer.timeline.locator(".legend-total")).toBeVisible();
    await evidence.shot(
        designer.timeline,
        "314",
        "compiled-timeline-strip",
        "The compiled-timeline strip: what the protocol actually becomes, per-class colour-coded, with total length and a class legend. It compiles both protocol shapes, so it does not go blank on a legacy protocol.",
    );
});

test("an instruction can hold for input instead of running for a fixed time", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();
    const before = await designer.timelineShape();

    const instruction = designer.steps.filter({ hasText: "Instruction" }).first();
    await expect(designer.field(instruction, "Duration (s)")).toBeVisible();

    await instruction.locator("label", { hasText: "Wait for input" }).locator("input").check();

    // Duration is meaningless once the step is a barrier, so it is replaced by
    // the button's text — and the strip gains a zero-length wait tick.
    await expect(designer.field(instruction, "Duration (s)")).toHaveCount(0);
    await expect(designer.field(instruction, "Continue-button text")).toBeVisible();
    await expect
        .poll(async () => (await designer.timelineShape()).waits)
        .toBe(before.waits + 1);

    await evidence.shot(
        instruction,
        "314",
        "instruction-holds-for-input",
        "'Wait for input' turns an instruction into a barrier: Duration is replaced by the continue-button text. It compiles to the same zero-length barrier the retired 'wait' step emitted.",
    );
    await evidence.shot(
        designer.timeline,
        "314",
        "timeline-wait-tick",
        "The same change in the compiled timeline: a held instruction is an amber tick, because a barrier has no length to draw.",
    );
});

test("steps can be added, duplicated and retyped without losing their content", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();
    const initial = await designer.stepKinds();

    await designer.body.locator(".step-add:not(.nested) .add-step-btn", { hasText: "Cue" }).first().click();
    await expect(designer.steps).toHaveCount(initial.length + 1);

    const added = designer.steps.last();
    await designer.field(added, "Shown to participant").fill("Squeeze hard");
    await designer.field(added, "Class label (trained on)").fill("squeeze");

    // Duplicate deep-copies, so the copy is independent.
    await designer.stepAction(added, "Duplicate this step").click();
    await expect(designer.steps).toHaveCount(initial.length + 2);
    await expect(designer.field(designer.steps.last(), "Shown to participant")).toHaveValue("Squeeze hard");

    // Retyping swaps the step wholesale rather than merging, so old-kind fields
    // cannot linger — but the text it shows the participant carries over.
    await designer.steps.last().locator(".step-kind").selectOption("rest");
    await expect(designer.steps.last()).toHaveClass(/kind-rest/);
    await expect(designer.field(designer.steps.last(), "Shown to participant")).toHaveValue("Squeeze hard");
    await expect(designer.field(designer.steps.last(), "Class label (optional)")).toBeVisible();

    await evidence.shot(
        designer.body.locator(".step-add:not(.nested)"),
        "314",
        "add-step-palette",
        "The add-step palette: each kind has its colour dot and a tooltip saying what it is for. The standalone 'Wait' step is gone — an instruction that holds for input covers it.",
    );
});
