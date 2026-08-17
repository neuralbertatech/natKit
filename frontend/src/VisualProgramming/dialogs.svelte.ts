// In-app dialogs, replacing window.confirm / window.alert / window.prompt.
//
// The native dialogs were used in ~20 places across the Visual Programming page.
// They are unstyled, break the page's visual language, cannot show anything
// richer than a string (so "is this name already taken?" was unanswerable), and
// they block the whole browser tab — which for a page holding live WebSocket
// streams is worse than cosmetic.
//
// The API is deliberately await-able so call sites read almost exactly like the
// natives they replaced:
//
//     if (!(await askConfirm({ title: "…", body: "…" }))) return;
//     const name = await askName({ title: "…", existing: […] });
//
// A single <DialogHost /> mounted once renders whatever is pending. Requests
// queue, so an alert raised while a confirm is open is shown afterwards rather
// than lost.

/** Body copy shared by every dialog kind. */
export interface DialogCopy {
    /** Blank lines separate paragraphs. */
    body?: string;
    /** Extra lines rendered as a bulleted list under the body. */
    points?: string[];
}

export interface DialogChoice {
    /** Shown as the primary button. */
    confirmLabel?: string;
    cancelLabel?: string;
    /** Style the primary action as destructive. */
    danger?: boolean;
}

export interface ConfirmOptions extends DialogChoice, DialogCopy {
    title: string;
}

export interface AlertOptions extends DialogCopy {
    title: string;
    confirmLabel?: string;
}

/** An existing name to show while typing, so collisions are visible. */
export interface NameSuggestion {
    name: string;
    /** Secondary text, e.g. where that experiment is bound. */
    hint?: string;
}

export interface NameOptions extends DialogChoice, DialogCopy {
    title: string;
    /** Field caption. */
    label: string;
    placeholder?: string;
    initial?: string;
    /** Names already in use — filtered as the user types. */
    existing?: NameSuggestion[];
    /** What the existing names are, for wording ("experiment", "profile"). */
    noun?: string;
}

interface BaseRequest {
    id: number;
}

export interface ConfirmRequest extends BaseRequest, ConfirmOptions {
    kind: "confirm";
    resolve: (confirmed: boolean) => void;
}

export interface AlertRequest extends BaseRequest, AlertOptions {
    kind: "alert";
    resolve: () => void;
}

export interface NameRequest extends BaseRequest, NameOptions {
    kind: "name";
    resolve: (value: string | null) => void;
}

export type DialogRequest = ConfirmRequest | AlertRequest | NameRequest;

let queue = $state<DialogRequest[]>([]);
let nextId = 0;

/** The dialog currently on screen, or null. */
export const dialogs = {
    get current(): DialogRequest | null {
        return queue[0] ?? null;
    },
    get pending(): number {
        return queue.length;
    },
};

function enqueue<T extends DialogRequest>(request: Omit<T, "id">): void {
    queue = [...queue, { ...request, id: (nextId += 1) } as T];
}

/** Settle the open dialog and show the next one. */
function shift(): void {
    queue = queue.slice(1);
}

export function askConfirm(options: ConfirmOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
        enqueue<ConfirmRequest>({
            kind: "confirm",
            ...options,
            resolve,
        });
    });
}

export function showAlert(options: AlertOptions): Promise<void> {
    return new Promise<void>((resolve) => {
        enqueue<AlertRequest>({
            kind: "alert",
            ...options,
            resolve,
        });
    });
}

/** Resolves to the trimmed name, or null if cancelled. */
export function askName(options: NameOptions): Promise<string | null> {
    return new Promise<string | null>((resolve) => {
        enqueue<NameRequest>({
            kind: "name",
            ...options,
            resolve,
        });
    });
}

/** Called by DialogHost when the user answers. */
export function settleDialog(request: DialogRequest, value: unknown): void {
    // Guard against a double-settle (Enter and a click landing together): only
    // the dialog still at the head of the queue may resolve.
    if (queue[0]?.id !== request.id) {
        return;
    }
    shift();
    if (request.kind === "confirm") {
        request.resolve(value === true);
    } else if (request.kind === "name") {
        request.resolve(typeof value === "string" ? value : null);
    } else {
        request.resolve();
    }
}

/**
 * Compare names the way a person would when asking "does this already exist?" —
 * case and surrounding whitespace are not meaningful differences.
 */
export function namesCollide(a: string, b: string): boolean {
    return a.trim().toLowerCase() === b.trim().toLowerCase();
}

/** Existing names worth showing for what has been typed so far. */
export function filterSuggestions(
    existing: NameSuggestion[],
    typed: string,
): NameSuggestion[] {
    const needle = typed.trim().toLowerCase();
    if (!needle) return existing;
    return existing.filter((entry) =>
        entry.name.toLowerCase().includes(needle),
    );
}
