/**
 * A tiny client for the backend's `stream_viewer` WebSocket protocol.
 *
 * The e2e suite needs this for two things the UI is a bad tool for: taking a
 * census of the board/experiment stores before a test, and guaranteeing the
 * scratch data a test created is gone afterwards even if the browser died
 * mid-flow. Every throwaway verification script re-implemented it with a fixed
 * `setTimeout` per request; this correlates on `request_id` instead, because the
 * socket also carries broadcasts nobody asked for.
 */

export interface GraphRecord {
    graph_id: string;
    label?: string;
    /** Set only on recorded snapshots and forks — those are history, not boards. */
    instance_id?: string;
    experiment_id?: string;
    immutable?: boolean;
}

export interface ExperimentRecord {
    experiment_id: string;
    label?: string;
    live_graph_id?: string;
    /** Opaque to the backend; the frontend owns its shape. */
    protocol?: unknown;
}

export interface StoreCensus {
    graphs: GraphRecord[];
    experiments: ExperimentRecord[];
}

type Json = Record<string, unknown>;

interface Pending {
    resolve: (value: Json) => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
}

const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;

export class ViewerSocket {
    private nextId = 1;
    private readonly pending = new Map<string, Pending>();
    private closed = false;

    private constructor(private readonly socket: WebSocket) {
        this.socket.addEventListener("message", (event) => this.onMessage(event));
        this.socket.addEventListener("close", () => {
            this.closed = true;
            for (const [, entry] of this.pending) {
                clearTimeout(entry.timer);
                entry.reject(new Error("stream_viewer socket closed"));
            }
            this.pending.clear();
        });
    }

    static open(url: string, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<ViewerSocket> {
        return new Promise((resolve, reject) => {
            const socket = new WebSocket(url);
            const timer = setTimeout(
                () => reject(new Error(`timed out connecting to ${url}`)),
                timeoutMs,
            );
            socket.addEventListener("open", () => {
                clearTimeout(timer);
                resolve(new ViewerSocket(socket));
            });
            socket.addEventListener("error", () => {
                clearTimeout(timer);
                reject(new Error(`failed to connect to ${url} — is the dev stack up?`));
            });
        });
    }

    private onMessage(event: MessageEvent): void {
        let message: Json;
        try {
            message = JSON.parse(String(event.data)) as Json;
        } catch {
            return;
        }
        const requestId = message["request_id"];
        if (typeof requestId !== "string") {
            return;
        }
        const entry = this.pending.get(requestId);
        if (!entry) {
            return;
        }
        this.pending.delete(requestId);
        clearTimeout(entry.timer);
        if (message["type"] === "error") {
            entry.reject(new Error(String(message["message"] ?? "stream_viewer error")));
            return;
        }
        entry.resolve(message);
    }

    request(action: string, payload: Json = {}, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<Json> {
        if (this.closed) {
            return Promise.reject(new Error("stream_viewer socket is closed"));
        }
        const requestId = `e2e-${this.nextId++}`;
        return new Promise<Json>((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(requestId);
                reject(new Error(`no answer to ${action} (request ${requestId})`));
            }, timeoutMs);
            this.pending.set(requestId, { resolve, reject, timer });
            this.socket.send(JSON.stringify({ ...payload, action, request_id: requestId }));
        });
    }

    async listGraphs(): Promise<GraphRecord[]> {
        const message = await this.request("list_stream_graphs");
        return (message["graphs"] as GraphRecord[] | undefined) ?? [];
    }

    async listExperiments(): Promise<ExperimentRecord[]> {
        const message = await this.request("list_experiments");
        return (message["experiments"] as ExperimentRecord[] | undefined) ?? [];
    }

    async census(): Promise<StoreCensus> {
        // Sequential on purpose: one socket, and the answers are cheap.
        const graphs = await this.listGraphs();
        const experiments = await this.listExperiments();
        return { graphs, experiments };
    }

    async deleteGraph(graphId: string, force = false): Promise<void> {
        await this.request("delete_stream_graph", { graph_id: graphId, force });
    }

    async deleteExperiment(experimentId: string): Promise<void> {
        await this.request("delete_experiment", { experiment_id: experimentId });
    }

    /**
     * Wait until a board id is actually in the store. A board created in the UI
     * only reaches the backend through the editor's debounced auto-save, and an
     * experiment cannot bind to a board the backend has never seen — so this
     * replaces the "sleep 3s and hope" every script used to do.
     */
    async waitForGraph(graphId: string, timeoutMs = 15_000): Promise<void> {
        const deadline = Date.now() + timeoutMs;
        for (;;) {
            const graphs = await this.listGraphs();
            if (graphs.some((graph) => graph.graph_id === graphId)) {
                return;
            }
            if (Date.now() > deadline) {
                throw new Error(`board ${graphId} never reached the backend store`);
            }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
    }

    /** One board record, as the store holds it. */
    async getGraph(graphId: string): Promise<Record<string, unknown> | undefined> {
        const graphs = (await this.listGraphs()) as unknown as Record<string, unknown>[];
        return graphs.find((graph) => graph["graph_id"] === graphId);
    }

    async saveGraph(graph: Record<string, unknown>): Promise<void> {
        await this.request("save_stream_graph", { graph });
    }

    /**
     * Device ids that are publishing a clock fit right now.
     *
     * ⚠️ DISCOVERED, never hardcoded. These are hardware ids: they change when a
     * board is swapped, and a test that pins one passes until the day somebody
     * replaces a leaf and then fails for a reason that looks nothing like the
     * cause. Empty when the rig is off, which callers should SKIP on rather than
     * fail — "no hardware attached" is not a regression.
     */
    async devicesWithClockFit(): Promise<string[]> {
        const message = await this.request("list_log_streams");
        const topics = (message["topics"] as Record<string, unknown>[] | undefined) ?? [];
        const ids = topics
            .filter((topic) => topic["schema_name"] === "NatKitNodeStatusV1")
            .map((topic) => String(topic["stream_id"]));
        return [...new Set(ids)];
    }

    close(): void {
        this.closed = true;
        try {
            this.socket.close();
        } catch {
            // Already gone; nothing to do.
        }
    }
}
