/**
 * Screenshot evidence, written outside the repo tree.
 *
 * Verification of this UI happens by a human looking at it, so the suite emits
 * the evidence rather than leaving it to be re-captured by hand. Conventions,
 * all of them paid for by earlier hand-captured sets:
 *
 * - element-scoped shots, so a shot reads on its own in a ticket comment;
 * - `<ticket>-<nn>-<slug>.png`, numbered per ticket, so one run drops a
 *   ready-ordered set per ticket;
 * - a MANIFEST.md with a caption per shot — a screenshot without a caption is
 *   not evidence;
 * - the run's health (native dialogs, console errors, store restoration) in the
 *   manifest, because a clean-looking set from a run that leaked data is a lie.
 *
 * Written to `~/natkit-verification/<sha>/` and NOT into the repo: `~/code` is
 * Syncthing-synced and these are run artifacts, not source.
 */
import { execFileSync } from "node:child_process";
import {
    appendFileSync,
    existsSync,
    mkdirSync,
    readdirSync,
    readFileSync,
    rmSync,
    writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export interface ShotRecord {
    ticket: string;
    seq: number;
    name: string;
    caption: string;
    test: string;
}

export interface HealthRecord {
    test: string;
    nativeDialogs: string[];
    consoleErrors: string[];
    /** null when a test did not touch the stores. */
    storesRestored: boolean | null;
    leftoversCleaned: string[];
}

const LEDGER = ".evidence.jsonl";
const HEALTH = ".health.jsonl";
const RUN_META = ".run.json";

/** Artifacts this suite owns and may therefore replace on a re-run. */
const OWNED = /^(\d+-\d{2}-[a-z0-9-]+\.png|MANIFEST\.md|\.evidence\.jsonl|\.health\.jsonl|\.run\.json)$/;

function git(...args: string[]): string {
    try {
        return execFileSync("git", args, { encoding: "utf8" }).trim();
    } catch {
        return "";
    }
}

/**
 * `~/natkit-verification/<sha>/`, with `-dirty` appended when the tree has
 * uncommitted changes — a set captured from a dirty tree does not describe the
 * commit and must not be filed as though it did.
 */
export function evidenceDir(): string {
    const override = process.env.NATKIT_EVIDENCE_DIR;
    if (override) {
        return override;
    }
    const sha = git("rev-parse", "--short", "HEAD") || "working-tree";
    const dirty = git("status", "--porcelain").length > 0;
    return join(homedir(), "natkit-verification", dirty ? `${sha}-dirty` : sha);
}

export interface RunMeta {
    sha: string;
    dirty: boolean;
    baseURL: string;
    viewport: string;
    startedAt: string;
}

export function prepareEvidenceDir(meta: Omit<RunMeta, "sha" | "dirty">): {
    dir: string;
    replaced: number;
} {
    const dir = evidenceDir();
    mkdirSync(dir, { recursive: true });
    // A re-run regenerates the whole set, so its own artifacts are replaced.
    // Anything else in the directory is left strictly alone.
    let replaced = 0;
    for (const entry of readdirSync(dir)) {
        if (OWNED.test(entry)) {
            rmSync(join(dir, entry));
            replaced += 1;
        }
    }
    const runMeta: RunMeta = {
        sha: git("rev-parse", "--short", "HEAD") || "working-tree",
        dirty: git("status", "--porcelain").length > 0,
        ...meta,
    };
    writeFileSync(join(dir, RUN_META), `${JSON.stringify(runMeta, null, 2)}\n`);
    return { dir, replaced };
}

function readJsonl<T>(path: string): T[] {
    if (!existsSync(path)) {
        return [];
    }
    return readFileSync(path, "utf8")
        .split("\n")
        .filter((line) => line.trim().length > 0)
        .map((line) => JSON.parse(line) as T);
}

/** Anything with a `screenshot()` — a Page or a Locator. */
interface Shootable {
    screenshot(options: {
        path: string;
        animations?: "disabled" | "allow";
        caret?: "hide" | "initial";
    }): Promise<Buffer>;
}

export class Evidence {
    private readonly dir = evidenceDir();

    constructor(private readonly testTitle: string) {}

    /**
     * Capture one shot and record its caption.
     *
     * Returns the absolute path, so a test can assert on the bytes: some
     * invariants (a seeded schedule recompiling identically) are proven by image
     * equality more convincingly than by any DOM assertion.
     */
    async shot(
        target: Shootable,
        ticket: string,
        slug: string,
        caption: string,
    ): Promise<string> {
        const ledgerPath = join(this.dir, LEDGER);
        const seq = readJsonl<ShotRecord>(ledgerPath).filter((entry) => entry.ticket === ticket).length + 1;
        const name = `${ticket}-${String(seq).padStart(2, "0")}-${slug}.png`;
        const path = join(this.dir, name);
        await target.screenshot({
            path,
            // Both matter for image equality: a running transition or a blinking
            // caret would make two shots of an identical state differ.
            animations: "disabled",
            caret: "hide",
        });
        const record: ShotRecord = { ticket, seq, name, caption, test: this.testTitle };
        appendFileSync(ledgerPath, `${JSON.stringify(record)}\n`);
        return path;
    }

    recordHealth(record: HealthRecord): void {
        appendFileSync(join(this.dir, HEALTH), `${JSON.stringify(record)}\n`);
    }
}

export function writeManifest(): { dir: string; shots: number; healthy: boolean } {
    const dir = evidenceDir();
    const shots = readJsonl<ShotRecord>(join(dir, LEDGER));
    const health = readJsonl<HealthRecord>(join(dir, HEALTH));
    const meta = existsSync(join(dir, RUN_META))
        ? (JSON.parse(readFileSync(join(dir, RUN_META), "utf8")) as RunMeta)
        : null;

    const natives = health.flatMap((entry) => entry.nativeDialogs);
    const consoleErrors = health.flatMap((entry) => entry.consoleErrors);
    const notRestored = health.filter((entry) => entry.storesRestored === false);
    const leftovers = health.flatMap((entry) => entry.leftoversCleaned);
    const healthy = natives.length === 0 && consoleErrors.length === 0 && notRestored.length === 0;

    const byTicket = new Map<string, ShotRecord[]>();
    for (const shot of shots) {
        const list = byTicket.get(shot.ticket) ?? [];
        list.push(shot);
        byTicket.set(shot.ticket, list);
    }

    let md = `# natKit Visual Programming — UI verification${meta ? ` (${meta.sha}${meta.dirty ? ", dirty tree" : ""})` : ""}\n\n`;
    if (meta) {
        md += `Captured by \`npm run test:e2e\` against ${meta.baseURL}, viewport ${meta.viewport}.\n`;
        md += `Run started ${meta.startedAt}.\n`;
        if (meta.dirty) {
            md += `\n> **The working tree was dirty.** This set describes uncommitted work, not commit ${meta.sha}.\n`;
        }
    }
    md += `\nEvery test creates its own scratch board + experiment and deletes them again.\n\n`;
    md += `## Run health\n\n`;
    md += `- Screenshots: **${shots.length}** across ${byTicket.size} ticket(s), from ${health.length} test(s)\n`;
    md += `- Native browser dialogs raised: **${natives.length === 0 ? "none" : natives.join(" · ")}**\n`;
    md += `- Console errors: **${consoleErrors.length === 0 ? "none" : consoleErrors.length}**\n`;
    for (const error of consoleErrors) {
        md += `  - ${error}\n`;
    }
    md += `- Stores restored exactly: **${notRestored.length === 0 ? "yes" : `NO — ${notRestored.map((e) => e.test).join(", ")}`}**\n`;
    if (leftovers.length > 0) {
        md += `- Scratch leftovers cleaned from an earlier run: ${leftovers.join(", ")}\n`;
    }

    for (const ticket of [...byTicket.keys()].sort()) {
        md += `\n## Ticket #${ticket}\n\n`;
        for (const shot of byTicket.get(ticket) ?? []) {
            md += `### ${shot.name}\n\n${shot.caption}\n\n<sub>${shot.test}</sub>\n\n`;
        }
    }
    writeFileSync(join(dir, "MANIFEST.md"), md);
    return { dir, shots: shots.length, healthy };
}
