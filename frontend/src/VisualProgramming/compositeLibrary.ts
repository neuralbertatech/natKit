// Browser-side persistence for composites and editor-level graphs.
//
// Two concerns live here, both backed by localStorage:
//   1. The reusable composite template *library* (personal, per-browser).
//   2. The editor-level version of each graph (with composites still collapsed),
//      because the backend graph store is lossy and drops composite metadata.
//
// This module owns the side effects (localStorage, file download/upload); the
// pure logic lives in composites.ts.
import {
    createCompositeId,
    parseCompositeExportFile,
    serializeCompositeExport,
    type CompositeTemplate,
    type EditorGraphDefinition,
} from "./composites";
import { DEFAULT_COMPOSITES } from "./defaultComposites";

const COMPOSITE_KEY = "natkit.streamviewer.composites.v1";
const EDITOR_GRAPH_KEY = "natkit.streamviewer.editorGraphs.v1";

function readJson<T>(key: string, fallback: T): T {
    if (typeof localStorage === "undefined") {
        return fallback;
    }
    try {
        const raw = localStorage.getItem(key);
        if (!raw) {
            return fallback;
        }
        return JSON.parse(raw) as T;
    } catch {
        return fallback;
    }
}

function writeJson(key: string, value: unknown): void {
    if (typeof localStorage === "undefined") {
        return;
    }
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // Ignore quota / serialization failures — persistence is best-effort.
    }
}

// --- Composite library -----------------------------------------------------

export function loadCompositeLibrary(): Record<string, CompositeTemplate> {
    return readJson<Record<string, CompositeTemplate>>(COMPOSITE_KEY, {});
}

// Built-in composites (see defaultComposites.ts) merged with the user's
// personal library — a saved template with the same composite_id overrides
// the built-in default.
function mergedCompositeLibrary(): Record<string, CompositeTemplate> {
    const merged: Record<string, CompositeTemplate> = {};
    for (const template of DEFAULT_COMPOSITES) {
        merged[template.composite_id] = template;
    }
    Object.assign(merged, loadCompositeLibrary());
    return merged;
}

export function listCompositeTemplates(): CompositeTemplate[] {
    return Object.values(mergedCompositeLibrary()).sort((left, right) =>
        left.label.localeCompare(right.label),
    );
}

export function resolveCompositeTemplate(
    compositeId: string,
): CompositeTemplate | undefined {
    return mergedCompositeLibrary()[compositeId];
}

export function saveCompositeTemplate(template: CompositeTemplate): void {
    const library = loadCompositeLibrary();
    library[template.composite_id] = template;
    writeJson(COMPOSITE_KEY, library);
}

export function deleteCompositeTemplate(compositeId: string): void {
    const library = loadCompositeLibrary();
    delete library[compositeId];
    writeJson(COMPOSITE_KEY, library);
}

// Merge imported templates, regenerating ids on collision so nothing is clobbered.
export function importCompositeTemplates(
    templates: CompositeTemplate[],
): CompositeTemplate[] {
    const library = loadCompositeLibrary();
    const added: CompositeTemplate[] = [];
    for (const template of templates) {
        const next = { ...template };
        if (library[next.composite_id]) {
            next.composite_id = createCompositeId();
        }
        library[next.composite_id] = next;
        added.push(next);
    }
    writeJson(COMPOSITE_KEY, library);
    return added;
}

// --- File export / import --------------------------------------------------

export function downloadCompositeFile(templates: CompositeTemplate[]): void {
    if (typeof document === "undefined" || templates.length === 0) {
        return;
    }
    const payload = serializeCompositeExport(templates);
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    const baseName =
        templates.length === 1
            ? templates[0].label.replace(/[^A-Za-z0-9_-]+/g, "-")
            : "composites";
    anchor.download = `${baseName || "composites"}.natkit-composite.json`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
}

export async function readCompositeFile(
    file: File,
): Promise<{ templates: CompositeTemplate[]; errors: string[] }> {
    const text = await file.text();
    return parseCompositeExportFile(text);
}

// --- Editor-level graph persistence ---------------------------------------

export function loadEditorGraph(
    graphId: string,
): EditorGraphDefinition | undefined {
    const store = readJson<Record<string, EditorGraphDefinition>>(
        EDITOR_GRAPH_KEY,
        {},
    );
    return store[graphId];
}

export function saveEditorGraph(graph: EditorGraphDefinition): void {
    if (!graph.graph_id) {
        return;
    }
    const store = readJson<Record<string, EditorGraphDefinition>>(
        EDITOR_GRAPH_KEY,
        {},
    );
    store[graph.graph_id] = graph;
    writeJson(EDITOR_GRAPH_KEY, store);
}
