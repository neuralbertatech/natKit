import type {
  ErrorMessage,
  HelloMessage,
  JobAcceptedMessage,
  JobListMessage,
  JobStatusMessage,
  MlControlPlaneAction,
  MlControlPlaneMessage,
  RecordedRunsMessage,
  ThreadSlotsMessage,
  WorkersMessage,
} from "./types";

export type ConnectionState = "disconnected" | "connecting" | "connected";

export interface MlControlPlaneCallbacks {
  onConnectionChange?: (state: ConnectionState) => void;
  onHello?: (message: HelloMessage) => void;
  onRecordedRuns?: (message: RecordedRunsMessage) => void;
  onWorkers?: (message: WorkersMessage) => void;
  onThreadSlots?: (message: ThreadSlotsMessage) => void;
  onJobList?: (message: JobListMessage) => void;
  onJobAccepted?: (message: JobAcceptedMessage) => void;
  onJobStatus?: (message: JobStatusMessage) => void;
  onError?: (message: ErrorMessage) => void;
}

export class MlControlPlaneWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: MlControlPlaneCallbacks;
  private connectionState: ConnectionState = "disconnected";

  constructor(url: string, callbacks: MlControlPlaneCallbacks = {}) {
    this.url = url;
    this.callbacks = callbacks;
  }

  setUrl(url: string): void {
    this.url = url;
  }

  connect(): void {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    this.setConnectionState("connecting");
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => this.setConnectionState("connected");
    this.ws.onclose = () => this.setConnectionState("disconnected");
    this.ws.onerror = () => this.setConnectionState("disconnected");
    this.ws.onmessage = (event) => this.handleMessage(event.data);
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setConnectionState("disconnected");
  }

  send(action: MlControlPlaneAction): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(action));
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState === state) {
      return;
    }
    this.connectionState = state;
    this.callbacks.onConnectionChange?.(state);
  }

  private handleMessage(raw: string): void {
    const message = JSON.parse(raw) as MlControlPlaneMessage;
    switch (message.type) {
      case "hello":
        this.callbacks.onHello?.(message);
        break;
      case "recorded_runs":
        this.callbacks.onRecordedRuns?.(message);
        break;
      case "workers":
        this.callbacks.onWorkers?.(message);
        break;
      case "thread_slots":
        this.callbacks.onThreadSlots?.(message);
        break;
      case "job_list":
        this.callbacks.onJobList?.(message);
        break;
      case "job_accepted":
        this.callbacks.onJobAccepted?.(message);
        break;
      case "job_status":
        this.callbacks.onJobStatus?.(message);
        break;
      case "error":
        this.callbacks.onError?.(message);
        break;
    }
  }
}
