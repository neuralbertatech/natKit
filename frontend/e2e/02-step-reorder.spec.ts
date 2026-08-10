/**
 * TEC-NATKIT-3 (#314) — reordering and repeat-group containment.
 *
 * The drop-into-group case is the regression guard for a real bug: dragover on
 * the group body bubbled to the group card's own handler, which overwrote
 * "into the group" with "after the group card", so every drop-into was silently
 * a no-op reorder. No DOM assertion about the drag itself would have caught it —
 * only checking where the step ended up.
 */
import { expect, test } from "./support/fixtures";

test("steps reorder by arrow and by drag", async ({ designer, evidence }) => {
    await designer.convertToSteps();
    const initial = await designer.stepKinds();
    expect(initial.length).toBeGreaterThan(2);

    // The accessible path: arrows. Kept precisely because drag is not usable by
    // everyone.
    await designer.stepAction(designer.steps.last(), "Move up").click();
    const afterArrow = await designer.stepKinds();
    expect(afterArrow).not.toEqual(initial);
    expect([...afterArrow].sort()).toEqual([...initial].sort());

    // And the drag path, which needs synthetic DragEvents — see Designer.
    await designer.dragStepOntoStep(afterArrow.length - 1, 0);
    const afterDrag = await designer.stepKinds();
    expect(afterDrag[0]).toBe(afterArrow[afterArrow.length - 1]);

    await evidence.shot(
        designer.body.locator(".step-list").first(),
        "314",
        "reordered-step-list",
        "Steps reordered by dragging the grip handle. The up/down arrows do the same thing and stay as the keyboard-accessible path.",
    );
});

test("a step can be dragged into a repeat group, and groups do not nest", async ({
    designer,
}) => {
    await designer.convertToSteps();
    const topBefore = await designer.stepKinds();
    const childrenBefore = await designer.groupChildKinds();
    const movable = topBefore.findIndex((kind) => kind !== "repeat");
    expect(movable).toBeGreaterThanOrEqual(0);

    await designer.dragStepIntoGroup(movable);

    // The step must actually be INSIDE the group, not merely moved next to it.
    await expect
        .poll(async () => (await designer.groupChildKinds()).length)
        .toBe(childrenBefore.length + 1);
    expect(await designer.stepKinds()).toHaveLength(topBefore.length - 1);

    // A repeat group refuses to be dragged into another one: nested repeats
    // would make the compiled schedule impossible to reason about.
    const groupIndex = (await designer.stepKinds()).indexOf("repeat");
    const childrenNow = (await designer.groupChildKinds()).length;
    await designer.dragStepIntoGroup(groupIndex);
    expect(await designer.groupChildKinds()).toHaveLength(childrenNow);
    expect(await designer.groups).toHaveCount(1);
});

test("a repeat group collapses to a one-line summary", async ({ designer, evidence }) => {
    await designer.convertToSteps();
    const group = designer.groups.first();
    await expect(group.locator(".group-children")).toBeVisible();

    await group.locator(".collapse-btn").click();
    await expect(group.locator(".group-children")).toBeHidden();
    // The summary has to carry the two facts the rows were showing: how much is
    // in there, and how long it runs.
    await expect(group.locator(".group-summary")).toContainText(/steps/);
    await expect(group.locator(".group-summary")).toContainText(/total/);

    await evidence.shot(
        group.locator(".card-main").first(),
        "314",
        "collapsed-repeat-group",
        "A collapsed repeat group: Times, the shuffle seed and reroll, the interleaved rest and its jitter, and a one-line summary of what is inside — so a long protocol stays readable.",
    );

    await group.locator(".collapse-btn").click();
    await expect(group.locator(".group-children")).toBeVisible();
});
