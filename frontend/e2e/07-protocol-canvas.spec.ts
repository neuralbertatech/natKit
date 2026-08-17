/**
 * TEC-NATKIT-13 (#336) — the spatial protocol canvas.
 *
 * The list stays canonical; the canvas is a second view of the same protocol,
 * rendering the same `StepFields` in its inspector so the two cannot drift.
 */
import { expect, test } from "./support/fixtures";

test("the canvas shows the protocol as a sequence with groups as containers", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();
    const listKinds = await designer.stepKinds();

    await evidence.shot(
        designer.page.locator(".view-switch"),
        "336",
        "view-toggle",
        "The List / Canvas toggle. The list stays canonical and keyboard-complete; the canvas is a second view of the same protocol.",
    );

    const canvas = await designer.showCanvas();
    // One node per top-level step: a canvas that quietly drops a step would
    // otherwise look fine.
    await expect(canvas.locator(".lane > .node")).toHaveCount(listKinds.length);
    await expect(canvas.locator(".node.is-group")).toHaveCount(1);

    await evidence.shot(
        canvas,
        "336",
        "sequence-lane",
        "Steps as nodes in a sequence lane, colour-coded by kind, with the repeat group drawn as a black box that shows what is inside it.",
    );
    await evidence.shot(
        canvas.locator(".node.is-group"),
        "336",
        "container-node",
        "The repeat group as a container: how many passes, whether it shuffles and from which seed, the interleaved rests, and a one-line summary of its interior.",
    );
});

test("a container node is not squeezed by a global stylesheet", async ({ designer }) => {
    // Regression guard for a bug found only by measuring: container nodes had
    // ~300px of dead space either side because a dependency ships a global
    // `.container { margin: auto }`. Svelte scopes OUR rules, but a global rule
    // still matches our element by class name — so generic class names are
    // unsafe here even with scoped styles, and `auto` margins on these nodes are
    // the symptom to watch for.
    await designer.convertToSteps();
    const canvas = await designer.showCanvas();
    const group = canvas.locator(".node.is-group");

    const margins = await group.evaluate((element) => {
        const style = getComputedStyle(element);
        return { left: style.marginLeft, right: style.marginRight };
    });
    expect(margins).toEqual({ left: "0px", right: "0px" });

    // And the symptom, measured rather than inferred: consecutive nodes sit a
    // connector apart, not hundreds of pixels.
    const gaps = await canvas.locator(".lane > .node").evaluateAll((nodes) =>
        nodes.slice(1).map((node, index) => {
            const previous = nodes[index].getBoundingClientRect();
            return node.getBoundingClientRect().left - previous.right;
        }),
    );
    expect(gaps.length).toBeGreaterThan(0);
    for (const gap of gaps) {
        expect(gap).toBeLessThan(60);
    }
});

test("selecting a node opens its fields, and a group can be zoomed into", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();
    // Read this from the list before switching: the canvas replaces the list, so
    // the step rows are not in the DOM to count once it is showing.
    const childCount = (await designer.groupChildKinds()).length;
    const canvas = await designer.showCanvas();

    await canvas.locator(".node").first().locator(".node-hit").click();
    const inspector = designer.page.locator(".inspector");
    await expect(inspector).toBeVisible();
    // The same StepFields the list rows render — assert by a field name, since
    // that is what would break if the canvas grew its own copy.
    await expect(inspector.locator("label", { hasText: "Step type" })).toBeVisible();
    await evidence.shot(
        inspector,
        "336",
        "selection-inspector",
        "Selecting a node opens its labelled fields — detail on demand rather than every field on every node. These are the same StepFields the list rows render, so the two views cannot drift.",
    );

    await canvas.locator(".node.is-group .open-btn").click();
    // Inside the group: the breadcrumb says where you are, and the add palette
    // omits Repeat group because groups do not nest.
    await expect(canvas.locator(".crumb.current")).toBeVisible();
    await expect(
        canvas.locator(".lane-add .add-btn", { hasText: "Repeat group" }),
    ).toHaveCount(0);
    await expect(canvas.locator(".lane > .node")).toHaveCount(childCount);

    await evidence.shot(
        canvas,
        "336",
        "zoomed-into-group",
        "Zoomed inside the repeat group: the breadcrumb shows the path, the hint explains the pass semantics, and the add palette omits Repeat group because groups do not nest.",
    );

    // Back out, and the list still agrees with the canvas.
    await canvas.locator(".crumb").first().click();
    await expect(canvas.locator(".node.is-group")).toBeVisible();
});

test("an edit made on the canvas shows up in the list", async ({ designer }) => {
    await designer.convertToSteps();
    const canvas = await designer.showCanvas();

    await canvas.locator(".node").first().locator(".node-hit").click();
    const inspector = designer.page.locator(".inspector");
    await designer.field(inspector, "Shown to participant").fill("Canvas edit");

    await designer.page.click('button[role="tab"]:has-text("List")');
    await expect(designer.field(designer.steps.first(), "Shown to participant")).toHaveValue(
        "Canvas edit",
    );
});
