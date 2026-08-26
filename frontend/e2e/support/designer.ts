/**
 * Page object for the experiment designer overlay: the step list, the repeat
 * groups, the compiled-timeline strip and the canvas view.
 */
import { expect, type Locator, type Page } from "@playwright/test";
import type { VpApp } from "./app";

export class Designer {
    readonly page: Page;

    // Not stored: only `page` is needed past construction, and keeping `app` as a
    // property left something nothing reads.
    constructor(app: VpApp) {
        this.page = app.page;
    }

    get panel(): Locator {
        return this.page.locator(".designer-panel");
    }

    get body(): Locator {
        return this.page.locator(".designer-body");
    }

    get timeline(): Locator {
        return this.page.locator(".designer-timeline");
    }

    /** Top-level step cards, in order. */
    get steps(): Locator {
        return this.page.locator(".designer-body > .step-list > .step-card");
    }

    get groups(): Locator {
        return this.page.locator(".step-card.kind-repeat");
    }

    /**
     * A fresh experiment starts on the legacy fixed protocol; almost everything
     * interesting lives in the step shape, so tests convert first. Conversion
     * leaves the compiled timeline unchanged by design.
     */
    async convertToSteps(): Promise<void> {
        await this.panel.locator("button", { hasText: "Convert to editable steps" }).click();
        await expect(this.steps.first()).toBeVisible();
        // The settle that used to be here is gone (TEC-NATKIT-19): the designer no
        // longer re-renders the pre-conversion protocol while the save is in
        // flight, so there is nothing to wait out. A test that needs the STORE to
        // have caught up still calls app.waitForStoredProtocol itself — that is a
        // different guarantee from "the UI is not lying", and only the second one
        // was this helper's job.
    }

    /** Kinds of the top-level steps, e.g. `["instruction", "repeat"]`. */
    async stepKinds(): Promise<string[]> {
        return this.page.$$eval(".designer-body > .step-list > .step-card", (cards) =>
            cards.map((card) => card.className.match(/kind-(\w+)/)?.[1] ?? "?"),
        );
    }

    async groupChildKinds(): Promise<string[]> {
        return this.page.$$eval(".group-children > .step-card", (cards) =>
            cards.map((card) => card.className.match(/kind-(\w+)/)?.[1] ?? "?"),
        );
    }

    /** Segments in the compiled timeline strip; waits are separate zero-length ticks. */
    async timelineShape(): Promise<{ segments: number; waits: number }> {
        return {
            segments: await this.timeline.locator(".timeline-segment").count(),
            waits: await this.timeline.locator(".timeline-wait").count(),
        };
    }

    field(scope: Locator, label: string): Locator {
        return scope.locator("label", { hasText: label }).locator("input").first();
    }

    /**
     * A step card's OWN field or button, ignoring anything nested inside it.
     *
     * A repeat group contains its children's fields and actions, and some labels
     * ("± Jitter (s)") appear at both levels — so a card-scoped lookup has to go
     * through the card's own `.card-main`, which precedes `.group-children`.
     */
    ownField(card: Locator, label: string): Locator {
        return this.field(card.locator(".card-main").first(), label);
    }

    stepAction(card: Locator, title: string): Locator {
        return card.locator(".card-main").first().locator(`button[title="${title}"]`).first();
    }

    get timingSeed(): Locator {
        return this.page
            .locator(".designer-header label", { hasText: "Timing seed" })
            .locator("input");
    }

    /**
     * HTML5 drag-and-drop, dispatched synthetically.
     *
     * Playwright's `dragTo` does NOT drive the editor's dnd — it produces mouse
     * events, and the handlers listen for DragEvents. `new DataTransfer()` works
     * inside Chromium, which is what makes this possible at all.
     */
    async dragStepOntoStep(fromIndex: number, toIndex: number): Promise<void> {
        await this.page.evaluate(
            ({ fromIndex, toIndex }) => {
                const cards = document.querySelectorAll<HTMLElement>(
                    ".designer-body > .step-list > .step-card",
                );
                const handle = cards[fromIndex]?.querySelector<HTMLElement>(".drag-handle");
                const target = cards[toIndex];
                if (!handle || !target) {
                    throw new Error("drag source or target missing");
                }
                const dataTransfer = new DataTransfer();
                const base = { bubbles: true, cancelable: true, dataTransfer };
                handle.dispatchEvent(new DragEvent("dragstart", base));
                const rect = target.getBoundingClientRect();
                // Top half of the target card means "before it".
                target.dispatchEvent(
                    new DragEvent("dragover", {
                        ...base,
                        clientX: rect.left + 40,
                        clientY: rect.top + 4,
                    }),
                );
                target.dispatchEvent(new DragEvent("drop", base));
                handle.dispatchEvent(new DragEvent("dragend", base));
            },
            { fromIndex, toIndex },
        );
    }

    /** Drag a top-level step into the first repeat group's body. */
    async dragStepIntoGroup(fromIndex: number): Promise<void> {
        await this.page.evaluate((fromIndex) => {
            const cards = document.querySelectorAll<HTMLElement>(
                ".designer-body > .step-list > .step-card",
            );
            const handle = cards[fromIndex]?.querySelector<HTMLElement>(".drag-handle");
            const body = document.querySelector<HTMLElement>(".group-children");
            if (!handle || !body) {
                throw new Error("drag source or group body missing");
            }
            const dataTransfer = new DataTransfer();
            const base = { bubbles: true, cancelable: true, dataTransfer };
            handle.dispatchEvent(new DragEvent("dragstart", base));
            const rect = body.getBoundingClientRect();
            body.dispatchEvent(
                new DragEvent("dragover", {
                    ...base,
                    clientX: rect.left + 10,
                    clientY: rect.bottom - 8,
                }),
            );
            body.dispatchEvent(new DragEvent("drop", base));
            handle.dispatchEvent(new DragEvent("dragend", base));
        }, fromIndex);
    }

    async showCanvas(): Promise<Locator> {
        await this.page.click('button[role="tab"]:has-text("Canvas")');
        const canvas = this.page.locator(".protocol-canvas");
        await expect(canvas).toBeVisible();
        return canvas;
    }

    async close(): Promise<void> {
        await this.page.keyboard.press("Escape");
        await expect(this.panel).toBeHidden();
    }
}
