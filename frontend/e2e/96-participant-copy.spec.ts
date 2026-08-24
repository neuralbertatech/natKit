/**
 * TEC-NATKIT-69 (#419) — the words a PARTICIPANT reads come from the protocol,
 * not from the component.
 *
 * This is the caveat that shipped with that ticket: the strings were asserted by
 * unit tests, but nobody had seen them rendered at full size, which is where they
 * are read from. The run surface lives on the markers node, so the board needs
 * one — that is why this could not be written until the fixture could build a
 * board with nodes on it.
 */
import { expect, test } from "./support/fixtures";
import { VpApp } from "./support/app";

/**
 * ⚠️ The words that must never reach an ADL participant. "Relax your hand" told
 * to somebody performing a reach-overhead or trunk task is not imprecise, it is
 * an instruction to do something other than the protocol — delivered at full size
 * during a recorded run.
 */
const BODY_PARTS = /hand|arm|wrist|shoulder|finger/i;

/**
 * The component's OWN words, excluding the author's.
 *
 * ⚠️ This distinction is the whole point and it caught the first draft of this
 * test: the runner's text includes the protocol's label and its class chips, and a
 * protocol legitimately called "Finger counting" with a class named `open_hand`
 * matched the body-part guard. An author naming their own classes after body parts
 * is not the defect — the defect was the COMPONENT telling a participant to relax
 * a hand it knew nothing about. So the guard reads only what the component
 * generates.
 */
async function componentCopy(runner: import("@playwright/test").Locator): Promise<string> {
    const parts = await Promise.all([
        runner.locator(".ready-meta").allTextContents(),
        runner.locator(".how-to").allTextContents(),
        runner.locator(".cue-instruction, .instruction").allTextContents(),
    ]);
    return parts.flat().join(" | ");
}

test("a protocol that states no wording gets copy that names no body part", async ({
    app,
    designer,
    viewer,
    page,
    evidence,
}) => {
    await designer.close();
    await app.attachNodes([VpApp.markersNode()]);

    // ⚠️ The wording is STRIPPED first, deliberately. A fresh scratch experiment
    // carries the finger-counting EMG protocol, which now declares its own
    // "gesture" vocabulary — correctly; that is the other half of this fix. A test
    // that just opened a new experiment would therefore check the authored case
    // twice and the DEFAULT never, and the default is the case that matters: it is
    // what an ADL protocol written by hand inherits.
    const experiments = await viewer.listExperiments();
    const bound = experiments.find((experiment) => experiment.live_graph_id === app.boardId)!;
    const record = bound as unknown as Record<string, unknown>;
    const protocol = { ...((record["protocol"] ?? {}) as Record<string, unknown>) };
    delete protocol["participant_copy"];
    await viewer.request("save_experiment", { experiment: { ...record, protocol } });

    await app.open();
    await page.locator(".graph-list-item").filter({ hasText: app.boardId }).first().click();
    // ⚠️ The LARGE view: the ticket's harm is copy "delivered in the large
    // participant view, at full size, during a recorded run". The inline surface on
    // the node card is the operator's thumbnail, and it does not even carry the
    // how-to lines — where the rest instruction lives.
    const runner = await app.openParticipantView();
    const copy = await componentCopy(runner);

    // What it must NOT say. Every one of these was in the copy that shipped.
    expect(copy, "EMG vocabulary must not reach an ADL participant").not.toMatch(/gesture/i);
    expect(copy, "no body part in the default wording").not.toMatch(BODY_PARTS);
    expect(copy, "'contractions' is EMG vocabulary").not.toMatch(/contraction/i);

    // And what it says instead — the two lines the ticket singled out.
    expect(copy, "the neutral noun").toMatch(/tasks?/i);
    expect(copy, "the rest instruction, in the how-to").toMatch(
        /return to a comfortable resting position/i,
    );
    expect(copy, "the cue instruction").toMatch(/perform this task/i);

    await evidence.shot(
        runner,
        "419",
        "runner-default-copy",
        "The run surface for a protocol that states no wording of its own: neutral 'task' vocabulary and no body part named. The default matters more than any authored case — it is what an ADL protocol written by hand inherits.",
    );
});

test("a protocol's own wording replaces the default, so neither study is wrong", async ({
    app,
    designer,
    viewer,
    page,
    evidence,
}) => {
    await designer.close();
    await app.attachNodes([VpApp.markersNode()]);

    const experiments = await viewer.listExperiments();
    const bound = experiments.find((experiment) => experiment.live_graph_id === app.boardId)!;
    const record = bound as unknown as Record<string, unknown>;
    const protocol = (record["protocol"] ?? {}) as Record<string, unknown>;

    // ADL wording on the same component that renders the EMG study. ⚠️ This is
    // what makes the fix a fix rather than a defect moved: replacing the copy
    // outright would simply have made the other study wrong.
    await viewer.request("save_experiment", {
        experiment: {
            ...record,
            protocol: {
                ...protocol,
                participant_copy: {
                    cue_noun: "activity",
                    cue_noun_plural: "activities",
                    cue_instruction: "Perform this activity",
                    rest_instruction: "Return to a comfortable resting position",
                },
            },
        },
    });

    await app.open();
    await page.locator(".graph-list-item").filter({ hasText: app.boardId }).first().click();
    const runner = await app.openParticipantView();
    const copy = await componentCopy(runner);

    expect(copy, "the protocol's own plural").toMatch(/activities/i);
    expect(copy, "and not the default").not.toMatch(/\btasks\b/i);
    expect(copy, "no body part").not.toMatch(BODY_PARTS);

    await evidence.shot(
        runner,
        "419",
        "runner-authored-copy",
        "The same component, with the ADL protocol's own wording: 'activities' rather than the neutral default. The words live on the protocol precisely so that one component can run both studies without either being wrong.",
    );
});
