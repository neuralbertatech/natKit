import { expect, test } from "./support/fixtures";
import { VpApp } from "./support/app";

/**
 * The node detail view is a modal, so focus has to move INTO it and come back
 * out again.
 *
 * ⚠️ svelte-check's a11y warning ("elements with the 'dialog' role must have a
 * tabindex") is satisfied by the attribute alone, which is why it is worth
 * asserting the BEHAVIOUR here instead. Adding `tabindex="-1"` and nothing else
 * silences the linter while leaving the real defect in place: focus stays on the
 * canvas behind the panel, so a keyboard user tabs through content the dialog is
 * covering and a screen reader never announces what just opened.
 *
 * Escape kept working throughout, because it is handled on the window rather
 * than on the panel — which is exactly what made this invisible to anyone
 * checking by clicking around.
 */
const FAST_ID = "909001";

test("the node detail view takes focus, and gives it back", async ({
    page,
    app,
}) => {
    await app.open();
    await app.createScratchBoard();
    await app.attachNodes([
        {
            ...VpApp.sourceNode(FAST_ID),
            id: "src",
            label: "Fast 400Hz",
            position: { x: 360, y: 240 },
        },
    ]);
    await app.open();
    await page
        .locator(".graph-list-item")
        .filter({ hasText: app.boardId })
        .first()
        .click();

    const node = page
        .locator(".node")
        .filter({ has: page.locator('[data-node-id="src"]') })
        .first();
    await expect(node).toBeVisible({ timeout: 15_000 });

    // Focus something on the canvas first, so "focus moved" is a real claim and
    // not just "focus was on <body> and now it is not".
    await node.locator(".node-header").first().focus();
    expect(
        await page.evaluate(() => document.activeElement?.className ?? ""),
    ).toContain("node-header");

    await node.dblclick();

    // ⚠️ The double-click itself moves focus to the card root, so THAT -- not
    // the header focused above -- is what the panel captures and must restore.
    // Asserting the header back would be asserting a bug: focus belongs where
    // the user actually left it, not where the test put it.
    await expect(page.locator(".node-detail")).toBeVisible();

    const focused = await page.evaluate(() => ({
        className: document.activeElement?.className ?? "",
        insideDialog: !!document.activeElement?.closest(".node-detail"),
        // -1 keeps the container out of the tab order while still letting focus
        // be placed on it; 0 would put the panel itself ahead of its own fields.
        tabindex: document
            .querySelector(".node-detail")
            ?.getAttribute("tabindex"),
    }));
    console.log("on open:", JSON.stringify(focused));
    expect(focused.insideDialog, "focus must move into the modal").toBe(true);
    expect(focused.tabindex).toBe("-1");

    // Escape closes it, and focus returns to where it came from rather than to
    // the top of the document (which is where it lands when a focused element is
    // removed and nobody says otherwise).
    await page.keyboard.press("Escape");
    await expect(page.locator(".node-detail")).toHaveCount(0);

    const after = await page.evaluate(() => {
        const active = document.activeElement;
        return {
            className: active?.className ?? "",
            // The identity that matters: is focus back on the card that opened
            // the panel, rather than on <body> at the top of the document?
            nodeId:
                active
                    ?.closest(".node")
                    ?.querySelector("[data-node-id]")
                    ?.getAttribute("data-node-id") ?? null,
            onBody: active === document.body,
        };
    });
    console.log("on close:", JSON.stringify(after));
    expect(after.onBody, "focus must not fall back to <body>").toBe(false);
    expect(
        after.nodeId,
        "focus must come back to the node that opened the panel",
    ).toBe("src");
});
