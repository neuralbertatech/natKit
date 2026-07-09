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
    dispatchMlControlPlaneMessage(message, this.callbacks);
  }
}

// Shared dispatch of a control-plane message to the callback set.
function dispatchMlControlPlaneMessage(
  message: MlControlPlaneMessage,
  callbacks: MlControlPlaneCallbacks,
): void {
  switch (message.type) {
    case "hello":
      callbacks.onHello?.(message);
      break;
    case "recorded_runs":
      callbacks.onRecordedRuns?.(message);
      break;
    case "workers":
      callbacks.onWorkers?.(message);
      break;
    case "thread_slots":
      callbacks.onThreadSlots?.(message);
      break;
    case "job_list":
      callbacks.onJobList?.(message);
      break;
    case "job_accepted":
      callbacks.onJobAccepted?.(message);
      break;
    case "job_status":
      callbacks.onJobStatus?.(message);
      break;
    case "error":
      callbacks.onError?.(message);
      break;
  }
}

// Phase 5, decision #3: the control plane is reached THROUGH the backend's
// /ws/stream_viewer connection (the browser no longer talks to :8786 directly).
// This adapter presents the MlControlPlaneWebSocket surface the MlPipeline page
// uses, but rides on a StreamViewerWebSocket: actions are wrapped as ml_proxy
// and sent over it; proxied "ml_control_plane" messages are fed back in via
// handleMessage(). Connection lifecycle is owned by the StreamViewerWebSocket,
// so connect()/disconnect() are no-ops here.
export class ProxiedMlControlPlane {
  private send_: (action: MlControlPlaneAction) => void;
  private callbacks: MlControlPlaneCallbacks;

  constructor(
    sendMlAction: (action: MlControlPlaneAction) => void,
    callbacks: MlControlPlaneCallbacks = {},
  ) {
    this.send_ = sendMlAction;
    this.callbacks = callbacks;
  }

  // Called by the StreamViewerWebSocket's onMlControlPlane callback.
  handleMessage(message: unknown): void {
    dispatchMlControlPlaneMessage(message as MlControlPlaneMessage, this.callbacks);
  }

  // Called by the StreamViewerWebSocket's onConnectionChange callback.
  setConnectionState(state: ConnectionState): void {
    this.callbacks.onConnectionChange?.(state);
  }

  send(action: MlControlPlaneAction): void {
    this.send_(action);
  }

  connect(): void {}
  disconnect(): void {}
  setUrl(_url: string): void {}
}
