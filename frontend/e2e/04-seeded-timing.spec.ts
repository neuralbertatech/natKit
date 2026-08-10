/**
 * TEC-NATKIT-2 (#313) — jitter is seeded, so a schedule is reproducible.
 *
 * Proven by image equality rather than by a DOM assertion: capture the compiled
 * timeline at seed 1, at seed 2, then at seed 1 again, and require the first and
 * third to be byte-identical while the second differs. Nothing about "the same
 * seed recreates the same schedule" is more convincing than that, and the shots
 * are evidence a ticket can carry.
 */
import { readFileSync } from "node:fs";
import { expect, test } from "./support/fixtures";

test("the same timing seed recompiles the same schedule", async ({ designer, evidence }) => {
    await designer.convertToSteps();
    const group = designer.groups.first();

    // Jitter the interleaved rests so the seed has something to vary.
    await designer.ownField(group, "± Jitter (s)").fill("1");

    const captureAtSeed = async (seed: string, slug: string, caption: string) => {
        await designer.timingSeed.fill(seed);
        // The strip recompiles from the protocol on every edit; give the field's
        // change a beat to land before shooting.
        await expect(designer.timingSeed).toHaveValue(seed);
        await designer.page.waitForTimeout(400);
        return evidence.shot(designer.timeline, "313", slug, caption);
    };

    const first = await captureAtSeed(
        "1",
        "jitter-seed-1",
        "Rests jittered by ±1s with the timing seed at 1. Note the uneven grey segments — the durations are drawn from one seeded stream, advanced once per jittered emission.",
    );
    const second = await captureAtSeed(
        "2",
        "jitter-seed-2",
        "Seed 2: a different, equally valid variation of the same protocol.",
    );
    const third = await captureAtSeed(
        "1",
        "jitter-seed-1-again",
        "Back to seed 1 and the strip is byte-identical to the first shot — the test asserts the image equality, so randomization is provably reproducible from the stored seed rather than merely looking similar.",
    );

    const bytes = (path: string) => readFileSync(path);
    expect(
        bytes(first).equals(bytes(third)),
        "seed 1 must recompile to a pixel-identical schedule",
    ).toBe(true);
    expect(bytes(first).equals(bytes(second)), "a different seed must vary the schedule").toBe(
        false,
    );
});

test("rerolling a seed stores a new one and recompiles", async ({ designer }) => {
    await designer.convertToSteps();
    const group = designer.groups.first();
    await designer.ownField(group, "± Jitter (s)").fill("1");

    // The dice is the "give me another variation" affordance. It has to WRITE a
    // seed, not just randomize once: an unstored reroll would recompile
    // differently on every load.
    const timingSeed = designer.timingSeed;
    const before = await timingSeed.inputValue();
    await designer.page.locator(".designer-header .dice-btn").click();
    await expect(timingSeed).not.toHaveValue(before);

    // Same for the group's shuffle seed, which drives the order rather than the
    // durations.
    const shuffleSeed = designer.ownField(group, "Seed");
    const shuffleBefore = await shuffleSeed.inputValue();
    await group.locator(".card-main").first().locator(".dice-btn").click();
    await expect(shuffleSeed).not.toHaveValue(shuffleBefore);
});

test("a barrier never jitters", async ({ designer }) => {
    await designer.convertToSteps();
    const instruction = designer.steps.filter({ hasText: "Instruction" }).first();
    await expect(designer.field(instruction, "± Jitter (s)")).toBeVisible();

    // Holding for input makes the step a zero-length barrier, and a barrier with
    // a jittered length is a contradiction — so the field goes away with it.
    await designer.field(instruction, "Wait for input").check();
    await expect(designer.field(instruction, "± Jitter (s)")).toHaveCount(0);
});
