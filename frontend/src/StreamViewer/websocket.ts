// WebSocket connection manager for Stream Viewer

import type {
  WebSocketMessage,
  ClientAction,
  StreamListMessage,
  StatusMessage,
  PublishResultMessage,
  TransformCapabilitiesMessage,
  NodeCatalogMessage,
  EmgTransformResultMessage,
  EmgTransformListMessage,
  EmgTransformStoppedMessage,
  ImuDataMessage,
  ImuBulkDataMessage,
  MuseDataMessage,
  MuseBulkDataMessage,
  EmgDataMessage,
  MarkerMessage,
  StreamTimeMessage,
  TransformProvenanceMessage,
  ErrorMessage,
  StreamGraphListMessage,
  StreamGraphSavedMessage,
  ProfileListMessage,
  ProfileSavedMessage,
  ProfileDeletedMessage,
  ExperimentListMessage,
  WorkspaceListMessage,
  WorkspaceSavedMessage,
  WorkspaceDeletedMessage,
  ExperimentSavedMessage,
  ExperimentDeletedMessage,
  ExperimentInstanceMessage,
  StreamGraphDeletedMessage,
  StreamGraphForkedMessage,
  ExperimentInstanceVerificationMessage,
  InstanceReplayMessage,
  DeviceCommandResultMessage,
  DeviceHealthMessage,
  StreamAliasesMessage,
  LogStreamListMessage,
  LogRecordsMessage,
  StreamGraphValidationMessage,
  StreamGraphStatusMessage,
  StreamGraphStartedMessage,
  StreamGraphStoppedMessage,
} from "./types";

export type ConnectionState = "disconnected" | "connecting" | "connected";

export interface StreamViewerCallbacks {
  onConnectionChange?: (state: ConnectionState) => void;
  onStreamList?: (message: StreamListMessage) => void;
  onStatus?: (message: StatusMessage) => void;
  onPublishResult?: (message: PublishResultMessage) => void;
  onTransformCapabilities?: (message: TransformCapabilitiesMessage) => void;
  onNodeCatalog?: (message: NodeCatalogMessage) => void;
  // A control-plane message proxied by the backend (Phase 5). The inner
  // MlControlPlaneMessage is passed through untyped (see types.ts).
  onMlControlPlane?: (message: unknown) => void;
  onEmgTransformResult?: (message: EmgTransformResultMessage) => void;
  onEmgTransformList?: (message: EmgTransformListMessage) => void;
  onEmgTransformStopped?: (message: EmgTransformStoppedMessage) => void;
  onImuData?: (message: ImuDataMessage) => void;
  onImuBulkData?: (message: ImuBulkDataMessage) => void;
  onMuseData?: (message: MuseDataMessage) => void;
  onMuseBulkData?: (message: MuseBulkDataMessage) => void;
  onEmgData?: (message: EmgDataMessage) => void;
  onMarker?: (message: MarkerMessage) => void;
  onStreamTime?: (message: StreamTimeMessage) => void;
  onTransformProvenance?: (message: TransformProvenanceMessage) => void;
  onStreamGraphList?: (message: StreamGraphListMessage) => void;
  onStreamGraphSaved?: (message: StreamGraphSavedMessage) => void;
  onStreamGraphValidation?: (message: StreamGraphValidationMessage) => void;
  onStreamGraphStatus?: (message: StreamGraphStatusMessage) => void;
  onStreamGraphStarted?: (message: StreamGraphStartedMessage) => void;
  onStreamGraphStopped?: (message: StreamGraphStoppedMessage) => void;
  onProfileList?: (message: ProfileListMessage) => void;
  onProfileSaved?: (message: ProfileSavedMessage) => void;
  onProfileDeleted?: (message: ProfileDeletedMessage) => void;
  onWorkspaceList?: (message: WorkspaceListMessage) => void;
  onWorkspaceSaved?: (message: WorkspaceSavedMessage) => void;
  onWorkspaceDeleted?: (message: WorkspaceDeletedMessage) => void;
  onExperimentList?: (message: ExperimentListMessage) => void;
  onExperimentSaved?: (message: ExperimentSavedMessage) => void;
  onExperimentDeleted?: (message: ExperimentDeletedMessage) => void;
  onExperimentInstance?: (message: ExperimentInstanceMessage) => void;
  onStreamGraphDeleted?: (message: StreamGraphDeletedMessage) => void;
  onStreamGraphForked?: (message: StreamGraphForkedMessage) => void;
  onExperimentInstanceVerification?: (
    message: ExperimentInstanceVerificationMessage,
  ) => void;
  onInstanceReplay?: (message: InstanceReplayMessage) => void;
  onDeviceCommandResult?: (message: DeviceCommandResultMessage) => void;
  onDeviceHealth?: (message: DeviceHealthMessage) => void;
  onStreamAliases?: (message: StreamAliasesMessage) => void;
  onLogStreamList?: (message: LogStreamListMessage) => void;
  onLogRecords?: (message: LogRecordsMessage) => void;
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
        case "publish_result":
          this.callbacks.onPublishResult?.(message);
          break;
        case "transform_capabilities":
          this.callbacks.onTransformCapabilities?.(message);
          break;
        case "node_catalog":
          this.callbacks.onNodeCatalog?.(message);
          break;
        case "ml_control_plane":
          this.callbacks.onMlControlPlane?.(message.message);
          break;
        case "transform_result":
        case "emg_transform_result":
          this.callbacks.onEmgTransformResult?.(message);
          break;
        case "transform_list":
        case "emg_transform_list":
          this.callbacks.onEmgTransformList?.(message);
          break;
        case "transform_stopped":
        case "emg_transform_stopped":
          this.callbacks.onEmgTransformStopped?.(message);
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
        // "frame" is the generic descriptor-driven channel-frame message
        // (Phase 3). It has the same shape as the legacy per-sensor "emg_data"
        // message, so it rides the same callback; "emg_data" is kept as an alias.
        case "frame":
        case "emg_data":
          this.callbacks.onEmgData?.(message);
          break;
        case "marker":
          this.callbacks.onMarker?.(message);
          break;
        case "stream_time":
          this.callbacks.onStreamTime?.(message);
          break;
        case "transform_provenance":
          this.callbacks.onTransformProvenance?.(message);
          break;
        case "stream_graph_list":
          this.callbacks.onStreamGraphList?.(message);
          break;
        case "stream_graph_saved":
          this.callbacks.onStreamGraphSaved?.(message);
          break;
        case "stream_graph_validation":
          this.callbacks.onStreamGraphValidation?.(message);
          break;
        case "stream_graph_status":
          this.callbacks.onStreamGraphStatus?.(message);
          break;
        case "stream_graph_started":
          this.callbacks.onStreamGraphStarted?.(message);
          break;
        case "stream_graph_stopped":
          this.callbacks.onStreamGraphStopped?.(message);
          break;
        case "profile_list":
          this.callbacks.onProfileList?.(message);
          break;
        case "profile_saved":
          this.callbacks.onProfileSaved?.(message);
          break;
        case "profile_deleted":
          this.callbacks.onProfileDeleted?.(message);
          break;
        case "workspace_list":
          this.callbacks.onWorkspaceList?.(message);
          break;
        case "workspace_saved":
          this.callbacks.onWorkspaceSaved?.(message);
          break;
        case "workspace_deleted":
          this.callbacks.onWorkspaceDeleted?.(message);
          break;
        case "experiment_list":
          this.callbacks.onExperimentList?.(message);
          break;
        case "experiment_saved":
          this.callbacks.onExperimentSaved?.(message);
          break;
        case "experiment_deleted":
          this.callbacks.onExperimentDeleted?.(message);
          break;
        case "experiment_instance":
          this.callbacks.onExperimentInstance?.(message);
          break;
        case "stream_graph_deleted":
          this.callbacks.onStreamGraphDeleted?.(message);
          break;
        case "stream_graph_forked":
          this.callbacks.onStreamGraphForked?.(message);
          break;
        case "experiment_instance_verification":
          this.callbacks.onExperimentInstanceVerification?.(message);
          break;
        case "instance_replay":
          this.callbacks.onInstanceReplay?.(message);
          break;
        case "device_command_result":
          this.callbacks.onDeviceCommandResult?.(message);
          break;
        case "device_health":
          this.callbacks.onDeviceHealth?.(message);
          break;
        case "stream_aliases":
          this.callbacks.onStreamAliases?.(message);
          break;
        case "log_stream_list":
          this.callbacks.onLogStreamList?.(message);
          break;
        case "log_records":
          this.callbacks.onLogRecords?.(message);
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

  // Forward an ML control-plane action to the backend proxy (Phase 5). The
  // backend relays it to the control plane and re-broadcasts responses as
  // "ml_control_plane" messages (→ onMlControlPlane).
  sendMlAction(action: unknown): void {
    this.send({ action: "ml_proxy", message: action });
  }

  // startOffset (Phase 3): -1 live tail (default), -2 beginning, >=0 a concrete
  // offset for historical reads.
  subscribe(streamIds: string[], startOffset?: number): void {
    this.send({
      action: "subscribe",
      stream_ids: streamIds,
      ...(startOffset !== undefined ? { start_offset: startOffset } : {}),
    });
  }

  unsubscribe(streamIds: string[]): void {
    this.send({ action: "unsubscribe", stream_ids: streamIds });
  }

  // Query a stream's retained offset bounds and (optionally) the offset for a
  // timestamp — the reply arrives via onStreamTime.
  queryStreamTime(
    streamId: string,
    timestampUs?: number,
    requestId?: string,
  ): void {
    this.send({
      action: "query_stream_time",
      stream_id: streamId,
      ...(timestampUs !== undefined ? { timestamp_us: timestampUs } : {}),
      ...(requestId !== undefined ? { request_id: requestId } : {}),
    });
  }

  requestStreamList(): void {
    this.send({ action: "get_streams" });
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }
}
