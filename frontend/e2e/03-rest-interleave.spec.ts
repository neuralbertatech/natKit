/**
 * TEC-NATKIT-2 (#313) — rests are interleaved at compile time.
 *
 * The point of the feature: a group holds only cue rows, and a rest is inserted
 * after every child (including the last, which is what separates consecutive
 * passes) when the protocol compiles — AFTER shuffling, which is the whole
 * reason it is a compile step and not real rows.
 */
import { expect, test } from "./support/fixtures";

test("converting a legacy protocol yields cue rows with rests interleaved", async ({
    designer,
    evidence,
}) => {
    await designer.convertToSteps();

    const group = designer.groups.first();
    // Cue rows only: previously this was 10 rows alternating cue/rest.
    const children = await designer.groupChildKinds();
    expect(children.length).toBeGreaterThan(0);
    expect(new Set(children)).toEqual(new Set(["cue"]));
    await expect(designer.ownField(group, "Rest between steps")).toBeChecked();

    await evidence.shot(
        designer.body.locator(".step-list").first(),
        "313",
        "interleave-on-by-default",
        "Converting the default protocol yields cue rows only, with 'Rest between steps' already on — previously ten rows alternating cue and rest. The compiled timeline is unchanged, which a unit test pins.",
    );
    await evidence.shot(
        group.locator(".card-main").first(),
        "313",
        "group-row-controls",
        "The repeat-group row: Times, the shuffle Seed and its reroll, the interleaved Rest (s) and its ± Jitter, and the toggles.",
    );
    await evidence.shot(
        designer.timeline,
        "313",
        "timeline-interleaved",
        "The compiled timeline with the interleaved rests present, even though no rest row exists in the editor. The rests are inserted after shuffling, so they can never end up back to back.",
    );
});

test("interleaving adds exactly one rest per cue, and 0s adds nothing", async ({ designer }) => {
    await designer.convertToSteps();
    const group = designer.groups.first();
    const toggle = designer.ownField(group, "Rest between steps");
    const cuesPerPass = (await designer.groupChildKinds()).length;
    const passes = Number(await designer.ownField(group, "Times").inputValue());
    const cues = cuesPerPass * passes;

    const withRests = (await designer.timelineShape()).segments;

    await toggle.uncheck();
    await expect.poll(async () => (await designer.timelineShape()).segments).toBe(withRests - cues);
    const withoutRests = (await designer.timelineShape()).segments;

    await toggle.check();
    await expect.poll(async () => (await designer.timelineShape()).segments).toBe(withRests);

    // "Interleave on, 0s" must insert nothing at all — an inserted zero-length
    // rest would still be a marker interval in the recording.
    await designer.ownField(group, "Rest (s)").fill("0");
    await expect.poll(async () => (await designer.timelineShape()).segments).toBe(withoutRests);
    await expect(toggle).toBeChecked();
});

test("the collapsed summary says the rests are there", async ({ designer }) => {
    await designer.convertToSteps();
    const group = designer.groups.first();
    await group.locator(".collapse-btn").click();
    // Without this the summary would claim "5 steps" for a group that compiles
    // to ten intervals.
    await expect(group.locator(".group-summary")).toContainText("+ rests");
});
