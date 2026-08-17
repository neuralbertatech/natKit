import { writeManifest } from "./evidence";

/**
 * Turn the per-test ledger into the MANIFEST.md that makes the screenshot set
 * attachable evidence rather than a folder of pictures.
 */
export default async function globalTeardown(): Promise<void> {
    const { dir, shots, healthy } = writeManifest();
    console.log(`\n${shots} screenshot(s) + MANIFEST.md -> ${dir}`);
    console.log(healthy ? "run health: clean" : "run health: SEE MANIFEST — something was flagged");
}
