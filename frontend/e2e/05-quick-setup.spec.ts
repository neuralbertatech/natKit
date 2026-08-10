/**
 * #335 — experiment quick setup: upload images, skip the details.
 *
 * The recipe generates a protocol in the shape get-ready → practice (tutorial)
 * → ready gate → main block, built on the interleaved rest so the result is N
 * cue rows rather than 2N. Detaching is one-way by design and is enforced at the
 * `commitSteps` choke point, so a hand edit anywhere drops the recipe.
 */
import { fileURLToPath } from "node:url";
import { expect, test } from "./support/fixtures";

const IMAGES = ["Fist Closed.png", "open_hand.png", "Pinch-Grip.png"].map((name) =>
    fileURLToPath(new URL(`./fixtures/images/${name}`, import.meta.url)),
);

test("images become classes, knobs regenerate, and customizing detaches", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();

    const onramp = designer.page.locator(".quick-setup-entry");
    await expect(onramp).toBeVisible();
    await evidence.shot(
        onramp,
        "335",
        "onramp",
        "The quick-setup on-ramp, offered whenever a protocol is being hand-edited.",
    );

    // Starting quick setup replaces the hand-written steps, so it confirms first.
    await designer.page.click('button[title="Generate a protocol from images, one class per image"]');
    const dialog = designer.page.locator(".dialog-panel");
    await expect(dialog).toBeVisible();
    // The bulleted consequences are a large part of why these dialogs exist — a
    // window.confirm can only show one string. `list-item` is a regression guard:
    // flexing a <ul> strips it and the bullet markers vanish, which was caught
    // only by looking at a screenshot.
    await expect(dialog.locator(".dialog-points li").first()).toBeVisible();
    expect(
        await dialog
            .locator(".dialog-points li")
            .first()
            .evaluate((element) => getComputedStyle(element).display),
    ).toBe("list-item");
    await evidence.shot(
        dialog,
        "337",
        "quicksetup-confirm",
        "The quick-setup confirm: a styled dialog stating how many steps will be replaced and what happens next, with bulleted consequences a window.confirm could not show.",
    );
    await dialog.locator(".dialog-actions .btn.primary").click();

    const card = designer.page.locator(".quick-setup");
    await expect(card).toBeVisible();
    // With nothing added it says what is missing rather than generating an
    // unrecordable protocol.
    await expect(card.locator(".qs-summary .blocked")).toBeVisible();
    await evidence.shot(
        card,
        "335",
        "card-empty",
        "Quick setup with nothing added yet: it says exactly what is missing before it can record.",
    );

    await designer.page.setInputFiles(".drop-zone input[type=file]", IMAGES);
    await expect(card.locator(".cue-tile")).toHaveCount(3);

    // Labels come from the filenames — the point being that a researcher's
    // "Fist Closed.PNG" turns into a usable class id without being asked.
    const labels = await card.locator(".cue-tile .field input").evaluateAll((inputs) =>
        inputs.map((input) => (input as HTMLInputElement).value),
    );
    expect(labels).toEqual(["fist_closed", "open_hand", "pinch_grip"]);

    // The thumbnails must actually load: an upload whose URL 404s back would
    // still render a tile, so the tile count proves nothing on its own.
    await expect
        .poll(
            () =>
                card
                    .locator(".cue-tile img")
                    .evaluateAll((images) =>
                        images.every((image) => (image as HTMLImageElement).naturalWidth > 0),
                    ),
            { message: "uploaded thumbnails should load from /api/media" },
        )
        .toBe(true);
    await expect(card.locator(".qs-summary .blocked")).toHaveCount(0);

    await evidence.shot(
        card,
        "335",
        "card-with-images",
        "Three images dropped in. Each became a class, with the label derived from the filename ('Fist Closed.png' → fist_closed) and still editable.",
    );
    await evidence.shot(
        designer.panel,
        "335",
        "designer-full",
        "The whole designer in quick-setup mode, with the generated protocol's compiled timeline along the bottom.",
    );
    await evidence.shot(
        designer.timeline,
        "335",
        "timeline-generated",
        "The generated schedule: a hatched practice pass, the amber wait-for-ready tick, then the main block of cues and interleaved rests.",
    );

    // A knob is not a field on a stored protocol — it regenerates the protocol,
    // so the compiled timeline has to grow with it.
    const rounds = designer.field(card, "Rounds");
    const beforeRounds = (await designer.timelineShape()).segments;
    await rounds.fill(String(Number(await rounds.inputValue()) + 2));
    await expect
        .poll(async () => (await designer.timelineShape()).segments)
        .toBeGreaterThan(beforeRounds);

    // Detach: confirmed, one-way, and it keeps the generated steps.
    await designer.page.click("text=Customize steps…");
    await expect(dialog).toBeVisible();
    await evidence.shot(
        dialog,
        "335",
        "detach-confirm",
        "Leaving quick setup is confirmed and one-way, and says why: regenerating the recipe later would overwrite hand edits.",
    );
    await dialog.locator(".dialog-actions .btn.primary").click();

    await expect(card).toHaveCount(0);
    await expect(designer.steps.first()).toBeVisible();
    const detachedKinds = await designer.stepKinds();
    expect(detachedKinds).toContain("repeat");

    await evidence.shot(
        designer.body,
        "335",
        "detached-steps",
        "After detaching: the generated protocol as ordinary editable steps, recipe gone. Detach is enforced where every hand edit funnels through, so it cannot be reattached by a later edit.",
    );

    // And a hand edit afterwards must not bring the recipe back.
    await designer.stepAction(designer.steps.last(), "Duplicate this step").click();
    await expect(card).toHaveCount(0);
    await expect(onramp).toBeVisible();
});

test("quick setup can be driven from class names alone", async ({ app, designer }) => {
    await designer.convertToSteps();
    await designer.page.click('button[title="Generate a protocol from a list of class names"]');
    await designer.page.locator(".dialog-panel .dialog-actions .btn.primary").click();

    const card = designer.page.locator(".quick-setup");
    await expect(card).toBeVisible();
    await app.waitForStoredProtocol((protocol) => protocol.quick_setup != null);

    const classes = card.locator('input[placeholder="e.g. fist, open, pinch"]');
    await classes.fill("up, down, left");
    // The comma list commits on change, not per keystroke — so it needs the blur
    // a real user gives it. `fill` alone only raises `input`.
    await classes.press("Tab");
    await expect(card.locator(".class-row")).toHaveCount(3);
    await expect(card.locator(".qs-summary")).toContainText("3");
    await expect(card.locator(".qs-summary .blocked")).toHaveCount(0);
});
