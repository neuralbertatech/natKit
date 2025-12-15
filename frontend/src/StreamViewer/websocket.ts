// WebSocket connection manager for Stream Viewer

import type {
  WebSocketMessage,
  ClientAction,
  StreamListMessage,
  StatusMessage,
  ImuDataMessage,
  ImuBulkDataMessage,
  MuseDataMessage,
  MuseBulkDataMessage,
  ErrorMessage,
} from "./types";

export type ConnectionState = "disconnected" | "connecting" | "connected";

export interface StreamViewerCallbacks {
  onConnectionChange?: (state: ConnectionState) => void;
  onStreamList?: (message: StreamListMessage) => void;
  onStatus?: (message: StatusMessage) => void;
  onImuData?: (message: ImuDataMessage) => void;
  onImuBulkData?: (message: ImuBulkDataMessage) => void;
  onMuseData?: (message: MuseDataMessage) => void;
  onMuseBulkData?: (message: MuseBulkDataMessage) => void;
  onError?: (message: ErrorMessage) => void;
}

export class StreamViewerWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: StreamViewerCallbacks;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private connectionState: ConnectionState = "disconnected";

  constructor(url: string, callbacks: StreamViewerCallbacks = {}) {
    this.url = url;
    this.callbacks = callbacks;
  }

  connect(): void {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.CONNECTING ||
        this.ws.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    this.setConnectionState("connecting");

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log("StreamViewer WebSocket connected");
        this.reconnectAttempts = 0;
        this.setConnectionState("connected");
        // Request stream list on connect
        this.send({ action: "get_streams" });
      };

      this.ws.onclose = (event) => {
        console.log("StreamViewer WebSocket closed", event.code, event.reason);
        this.setConnectionState("disconnected");
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("StreamViewer WebSocket error:", error);
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      this.setConnectionState("disconnected");
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setConnectionState("disconnected");
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.callbacks.onConnectionChange?.(state);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log("Max reconnect attempts reached");
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;

    console.log(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`,
    );
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private handleMessage(data: string): void {
    try {
      const message: WebSocketMessage = JSON.parse(data);

      switch (message.type) {
        case "stream_list":
          this.callbacks.onStreamList?.(message);
          break;
        case "status":
          this.callbacks.onStatus?.(message);
          break;
        case "imu_data":
          this.callbacks.onImuData?.(message);
          break;
        case "imu_bulk_data":
          this.callbacks.onImuBulkData?.(message);
          break;
        case "muse_data":
          this.callbacks.onMuseData?.(message);
          break;
        case "muse_bulk_data":
          this.callbacks.onMuseBulkData?.(message);
          break;
        case "error":
          this.callbacks.onError?.(message);
          break;
        default:
          console.warn("Unknown message type:", message);
      }
    } catch (error) {
      console.error("Failed to parse WebSocket message:", error, data);
    }
  }

  send(action: ClientAction): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(action));
    } else {
      console.warn("WebSocket not connected, cannot send:", action);
    }
  }

  subscribe(streamIds: number[]): void {
    this.send({ action: "subscribe", stream_ids: streamIds });
  }

  unsubscribe(streamIds: number[]): void {
    this.send({ action: "unsubscribe", stream_ids: streamIds });
  }

  requestStreamList(): void {
    this.send({ action: "get_streams" });
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }
}
