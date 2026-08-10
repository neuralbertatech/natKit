import type { FullConfig } from "@playwright/test";
import { prepareEvidenceDir } from "./evidence";

/**
 * Fail fast with a useful message if the dev stack is not up, and prepare the
 * evidence directory. Nothing here creates data.
 */
export default async function globalSetup(config: FullConfig): Promise<void> {
    const baseURL = config.projects[0]?.use.baseURL ?? "http://localhost:8080";
    const viewport = config.projects[0]?.use.viewport;

    let response: Response;
    try {
        response = await fetch(baseURL, { signal: AbortSignal.timeout(10_000) });
    } catch (error) {
        throw new Error(
            `The natKit dev stack is not answering at ${baseURL} ` +
                `(${(error as Error).message}). Bring it up with ` +
                `\`podman-compose -f docker-compose.dev.yml up -d\`, or point ` +
                `NATKIT_E2E_BASE_URL somewhere else.`,
        );
    }
    if (!response.ok) {
        throw new Error(`${baseURL} answered ${response.status}`);
    }

    const { dir, replaced } = prepareEvidenceDir({
        baseURL,
        viewport: viewport ? `${viewport.width}x${viewport.height} @2x` : "default",
        startedAt: new Date().toISOString(),
    });
    console.log(`evidence -> ${dir}`);
    if (replaced > 0) {
        console.log(`  (replaced ${replaced} artifact(s) from a previous run at this sha)`);
    }
}
