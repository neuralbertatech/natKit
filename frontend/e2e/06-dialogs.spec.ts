/**
 * TEC-NATKIT-14 (#337) — in-app dialogs replaced every native one.
 *
 * The standing regression guard is in the `health` fixture and applies to the
 * WHOLE suite: it asserts Playwright's `dialog` event never fires, so a
 * reintroduced `window.confirm` fails a test rather than being auto-dismissed
 * and silently passing. This spec covers what the native dialogs could not do.
 */
import { expect, test } from "./support/fixtures";

test("the name dialog lists existing names, filters them, and warns on a collision", async ({
    app,
    evidence,
    scratchLabel,
}) => {
    const dialog = await app.startCreateExperiment();
    await expect(dialog.locator(".dialog-suggestions li").first()).toBeVisible();
    await evidence.shot(
        dialog,
        "337",
        "name-dialog-lists-existing",
        "The new-experiment dialog replaces window.prompt: it lists every existing experiment and says where each one is bound, so a name is chosen with the others in view.",
    );

    const existing = (await dialog.locator(".dialog-suggestions .suggestion-name").first().innerText()).trim();
    const total = await dialog.locator(".dialog-suggestions li").count();

    await app.page.fill(".dialog-field input", existing.slice(0, 3));
    await expect(dialog.locator(".dialog-count")).toContainText(" of ");
    await evidence.shot(
        dialog,
        "337",
        "name-dialog-filters-as-you-type",
        `Typing "${existing.slice(0, 3)}" filters the list live, and the counter says how many of the existing names still match.`,
    );

    await app.page.fill(".dialog-field input", existing);
    await expect(dialog.locator(".dialog-collision")).toBeVisible();
    await expect(dialog.locator(".dialog-suggestions li.exact")).toHaveCount(1);
    // It warns but does NOT block: ids are generated, so duplicate labels are
    // legal, only confusing.
    await expect(dialog.locator(".dialog-actions .btn.primary")).toBeEnabled();
    await evidence.shot(
        dialog,
        "337",
        "name-dialog-collision-warning",
        `An exact match ("${existing}") warns and highlights the clashing row. It does not block: ids are generated, so duplicate labels are legal, only confusing.`,
    );

    await app.page.fill(".dialog-field input", scratchLabel);
    await expect(dialog.locator(".dialog-none")).toBeVisible();
    expect(total).toBeGreaterThan(0);
    await evidence.shot(
        dialog,
        "337",
        "name-dialog-free-name",
        "A name with no overlap says so explicitly, rather than leaving the absence of a warning to be interpreted.",
    );

    // Enter submits, which is what makes the dialog usable without the mouse.
    await app.page.press(".dialog-field input", "Enter");
    await expect(app.page.locator(".designer-panel")).toBeVisible();
});

test("a destructive confirm spells out the consequences", async ({
    app,
    designer,
    evidence,
}) => {
    await designer.close();
    await app.openExperimentPanel();
    await app.page.click('button[title="Delete this experiment"]');

    const dialog = app.dialog;
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveClass(/danger/);
    // It has to say what is and is NOT destroyed. A window.confirm could show
    // this sentence but not the danger styling that stops it reading like an
    // ordinary prompt.
    await expect(dialog.locator(".dialog-body")).toContainText("are kept");
    await expect(dialog.locator(".dialog-icon.danger")).toBeVisible();
    await evidence.shot(
        dialog,
        "337",
        "delete-experiment-confirm",
        "Destructive actions use the danger variant and spell out what is and is not deleted, as a bulleted list a native confirm could not render.",
    );

    await dialog.locator(".dialog-actions .btn.primary").click();
    await expect(dialog).toHaveCount(0);
    await expect(app.page.locator(".experiment-pill")).not.toHaveClass(/bound/);
});

test("Escape cancels a dialog without acting", async ({ app }) => {
    await app.startCreateExperiment();
    await app.page.keyboard.press("Escape");
    await expect(app.dialog).toHaveCount(0);
    // Cancelling must resolve the promise as "no", not create anything.
    await expect(app.page.locator(".designer-panel")).toHaveCount(0);
    await expect(app.page.locator(".experiment-pill")).not.toHaveClass(/bound/);

    // And the queue survives a cancellation: the next dialog still opens.
    await app.startCreateExperiment();
    await expect(app.dialog.locator(".dialog-field input")).toBeFocused();
});

test("a text paragraph in a dialog is not laid out as columns", async ({ app }) => {
    // Regression guard for a CSS trap that DOM assertions missed: a
    // `display:flex` container turns bare text nodes into flex items, and the
    // collision sentence stacked into columns. Caught only by looking at a
    // screenshot, so the shape is measured here instead.
    const dialog = await app.startCreateExperiment();
    await app.page.fill(
        ".dialog-field input",
        (await dialog.locator(".dialog-suggestions .suggestion-name").first().innerText()).trim(),
    );
    const collision = dialog.locator(".dialog-collision");
    await expect(collision).toBeVisible();

    const box = await collision.boundingBox();
    expect(box).not.toBeNull();
    // A sentence stacked into columns is much taller than it is wide.
    expect(box!.width).toBeGreaterThan(box!.height);
});
