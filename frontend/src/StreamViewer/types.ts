// Types for Stream Viewer WebSocket communication

export interface StreamTopic {
  schema_name: string;
  type: "Data" | "Meta";
  serialization_type: string;
  descriptor?: DataSchemaDescriptor;
}

export interface StreamInfo {
  topics: StreamTopic[];
}

export type SchemaFieldValueType =
  | "bool"
  | "int16"
  | "uint32"
  | "uint64"
  | "float32"
  | "float64"
  | "string"
  | "enum"
  | "object"
  | "array"
  | "unknown";

export interface SchemaFieldDescriptor {
  id: string;
  label: string;
  type: SchemaFieldValueType;
  description?: string;
  unit?: string;
  optional: boolean;
  enum_values?: string[];
  fields?: Record<string, SchemaFieldDescriptor>;
  items?: SchemaFieldDescriptor;
}

export interface DataSchemaDescriptor {
  schema_name: string;
  descriptor_version: number;
  root: SchemaFieldDescriptor;
}

export interface StreamListMessage {
  type: "stream_list";
  streams: Record<string, StreamInfo>;
}

export interface StatusMessage {
  type: "status";
  connected: boolean;
  subscribed_streams: string[];
}

export interface ErrorMessage {
  type: "error";
  message: string;
}

export interface PublishResultMessage {
  type: "publish_result";
  request_id: string;
  session_id: string;
  published_meta_records: number;
  published_marker_events: number;
}

export interface TransformCapabilityConfigField {
  id: string;
  label: string;
  type: "number" | "enum" | "string";
  required: boolean;
  min?: number;
  step?: number;
  default_value?: number;
  default_option?: string;
  options?: string[];
}

// The transform kinds compiled into the backend today. Kept for reference /
// autocomplete only — NOT a closed contract. Adding a transform in C++ must
// never require editing this file; the palette and inspector render from the
// runtime node catalog (list_node_catalog), so `TransformKind` is an open
// string. (Phase 1 of the visual-programming rework.)
export type KnownTransformKind =
  | "rectify"
  | "lowpass_envelope"
  | "bandpass_iir"
  | "notch_iir"
  | "rms_window"
  | "sliding_window"
  | "highpass_iir"
  | "mav"
  | "rms"
  | "wl"
  | "zc"
  | "ssc"
  | "ar_coeffs"
  | "lda_classify"
  | "channel_select";

// Open node_type for transform nodes. Any string the backend catalog advertises
// is valid; KnownTransformKind documents the built-ins.
export type TransformKind = KnownTransformKind | (string & {});

export interface TransformInputChannelMapping {
  label: string;
  sample_array_path: string;
}

export interface TransformInputMapping {
  id: string;
  label: string;
  mode: "canonical_channel_frame" | "explicit_channel_paths";
  schema_name?: string;
  required_descriptor_paths: string[];
  seq_no_path?: string;
  device_ts_us_path?: string;
  sample_rate_hz_path?: string;
  sample_rate_hz_value?: number;
  channels?: TransformInputChannelMapping[];
}

export interface TransformCapability {
  kind: TransformKind;
  label: string;
  description: string;
  input_descriptor_paths: string[];
  input_mappings: TransformInputMapping[];
  output_schema_name: string;
  config_fields: TransformCapabilityConfigField[];
}

export interface TransformCapabilitiesMessage {
  type: "transform_capabilities";
  request_id: string;
  transforms: TransformCapability[];
}

// --- Node catalog (Phase 1) --------------------------------------------------
// The backend advertises every node type it supports. The frontend palette and
// node inspector render purely from this — adding a node type is a data change
// on the backend, never a TypeScript union edit.

export type NodeCategory = "source" | "transform" | "viewer" | "sink";

export interface NodePortTemplate {
  id: string;
  label: string;
  descriptor?: DataSchemaDescriptor;
}

export interface NodeCatalogEntry {
  // Unique id. For transform nodes this equals the transform_kind.
  node_type: string;
  // Coarse structural kind the backend runtime validates.
  kind: StreamGraphNodeKind;
  category: NodeCategory;
  runner: string;
  label: string;
  description: string;
  config_fields: TransformCapabilityConfigField[];
  input_ports: NodePortTemplate[];
  output_ports: NodePortTemplate[];
  variadic_inputs: boolean;
  // Transform-only fields (carried through from the transform capability).
  input_mappings?: TransformInputMapping[];
  input_descriptor_paths?: string[];
  output_schema_name?: string;
}

export interface NodeCatalogMessage {
  type: "node_catalog";
  request_id: string;
  nodes: NodeCatalogEntry[];
}

export interface TransformResultMessage {
  type: "transform_result" | "emg_transform_result";
  request_id: string;
  source_stream_id: string;
  output_stream_id: string;
  output_identifier: string;
  transform_kind: TransformKind;
  input_mapping_id?: string;
  topic: string;
  worker_id: string;
  thread_slot_id: string;
  slot_capacity: number;
  active_count: number;
  already_exists: boolean;
}

export interface TransformSummary {
  source_stream_id: string;
  output_stream_id: string;
  output_identifier: string;
  transform_kind: TransformKind;
  input_mapping_id?: string;
  topic: string;
  worker_id: string;
  slot_index: number;
  thread_slot_id: string;
  status: "running";
  started_at_us: number;
  last_frame_at_us: number;
  frames_processed: number;
}

export interface TransformListMessage {
  type: "transform_list" | "emg_transform_list";
  request_id: string;
  worker_id: string;
  slot_capacity: number;
  active_count: number;
  available_slot_count: number;
  utilization_ratio: number;
  last_heartbeat_us: number;
  worker_status: "idle" | "live" | "stalled";
  transforms: TransformSummary[];
}

export interface TransformStoppedMessage {
  type: "transform_stopped" | "emg_transform_stopped";
  request_id: string;
  output_stream_id: string;
  worker_id: string;
  active_count: number;
  slot_capacity: number;
}

export type EmgTransformResultMessage = TransformResultMessage;
export type EmgTransformSummary = TransformSummary;
export type EmgTransformListMessage = TransformListMessage;
export type EmgTransformStoppedMessage = TransformStoppedMessage;

export interface ImuVector3 {
  x: number;
  y: number;
  z: number;
}

export interface ImuQuaternion {
  real: number;
  i: number;
  j: number;
  k: number;
}

export interface ImuData {
  accel: ImuVector3;
  gyro: ImuVector3;
  quat: ImuQuaternion;
}

export interface ImuAccuracies {
  accelerometer: number;
  gyroscope: number;
  rotation: number;
}

export interface ImuHasData {
  accelerometer: boolean;
  gyroscope: boolean;
  rotation: boolean;
}

export interface EncodingInfo {
  type: string;
  size: number;
}

export interface ImuDataMessage {
  type: "imu_data";
  stream_id: string;
  timestamp: number;
  encoding: EncodingInfo;
  data: ImuData;
  accuracies: ImuAccuracies;
  has_data: ImuHasData;
}

export interface ImuSample {
  timestamp: number;
  data: ImuData;
  accuracies: ImuAccuracies;
  has_data: ImuHasData;
}

export interface ImuBulkDataMessage {
  type: "imu_bulk_data";
  stream_id: string;
  encoding: EncodingInfo;
  samples: ImuSample[];
}

// Muse EEG data types
export interface MuseEegData {
  tp9: number[]; // 12 samples - left ear
  af7: number[]; // 12 samples - left forehead
  af8: number[]; // 12 samples - right forehead
  tp10: number[]; // 12 samples - right ear
}

export interface MusePpgData {
  ppg0: number[]; // 6 samples
  ppg1: number[]; // 6 samples
  ppg2: number[]; // 6 samples
}

export interface MuseHasData {
  eeg: boolean;
  accel: boolean;
  gyro: boolean;
  ppg: boolean;
}

export interface MuseSample {
  timestamp: number;
  eeg_sequence: number;
  motion_sequence: number;
  eeg: MuseEegData;
  accel: ImuVector3[]; // 3 motion samples
  gyro: ImuVector3[]; // 3 motion samples
  ppg: MusePpgData;
  has_data: MuseHasData;
}

export interface MuseDataMessage {
  type: "muse_data";
  stream_id: string;
  timestamp: number;
  eeg_sequence: number;
  motion_sequence: number;
  encoding: EncodingInfo;
  eeg: MuseEegData;
  accel: ImuVector3[];
  gyro: ImuVector3[];
  ppg: MusePpgData;
  has_data: MuseHasData;
}

export interface MuseBulkDataMessage {
  type: "muse_bulk_data";
  stream_id: string;
  encoding: EncodingInfo;
  samples: MuseSample[];
}

export interface EmgSample {
  schema_version: string;
  device_id: string;
  seq_no: number;
  device_ts_us: number;
  n_channels: number;
  samples_per_channel: number;
  sample_rate_hz: number;
  channel_labels: string[];
  payload: number[][];
}

export interface BufferedEmgSample extends EmgSample {
  received_at_ms: number;
  frame_duration_ms: number;
}

export interface EmgDataMessage extends EmgSample {
  // "frame" is the generic descriptor-driven channel-frame message (Phase 3);
  // "emg_data" is the legacy per-sensor alias. Same payload shape.
  type: "emg_data" | "frame";
  stream_id: string;
  encoding: EncodingInfo;
  schema_name?: string;
}

export interface TransformProvenanceMessage {
  type: "transform_provenance";
  stream_id: string;
  encoding: EncodingInfo;
  output_identifier: string;
  output_stream_id: string;
  output_schema_name: string;
  output_topic: string;
  source_stream_id: string;
  source_schema_name: string;
  source_topic: string;
  transform_kind: TransformKind;
  input_mapping_id: string;
  config_json: string;
  created_at_us: number;
}

export interface StreamGraphPosition {
  x: number;
  y: number;
}

export interface StreamGraphViewport {
  x: number;
  y: number;
  zoom: number;
}

export type StreamGraphNodeKind =
  | "stream_source"
  | "transform"
  | "viewer"
  | "sink"
  | "combine";

export interface StreamGraphBaseNode<K extends StreamGraphNodeKind = StreamGraphNodeKind> {
  id: string;
  kind: K;
  label: string;
  position: StreamGraphPosition;
  input_port_ids?: string[];
  output_port_ids?: string[];
}

export interface StreamGraphSourceNode extends StreamGraphBaseNode<"stream_source"> {
  kind: "stream_source";
  stream_id: string;
  schema_name?: string;
}

export interface StreamGraphTransformNode extends StreamGraphBaseNode<"transform"> {
  kind: "transform";
  transform_kind: TransformKind;
  input_mapping_id?: string;
  config: Record<string, number | string | boolean>;
  output_identifier?: string;
  output_stream_id?: string;
}

export interface StreamGraphViewerNode extends StreamGraphBaseNode<"viewer"> {
  kind: "viewer";
}

export interface StreamGraphSinkNode extends StreamGraphBaseNode<"sink"> {
  kind: "sink";
}

// Fans in >=2 upstream streams (e.g. several feature-extraction transforms)
// into one flattened feature-vector stream. Backend-only node kind — no
// transform_kind/config, since it has no per-kind parameters of its own.
export interface StreamGraphCombineNode extends StreamGraphBaseNode<"combine"> {
  kind: "combine";
  output_identifier?: string;
  output_stream_id?: string;
}

export type StreamGraphNode =
  | StreamGraphSourceNode
  | StreamGraphTransformNode
  | StreamGraphViewerNode
  | StreamGraphSinkNode
  | StreamGraphCombineNode;

export interface StreamGraphEdge {
  id: string;
  source_node_id: string;
  source_port: string;
  target_node_id: string;
  target_port: string;
}

export interface StreamGraphDefinition {
  graph_version: 1;
  graph_id: string;
  label: string;
  description?: string;
  created_at_us?: number;
  updated_at_us?: number;
  ui?: {
    viewport?: StreamGraphViewport;
    selected_node_id?: string | null;
  };
  nodes: StreamGraphNode[];
  edges: StreamGraphEdge[];
  notes?: string[];
}

export interface StreamGraphDiagnostic {
  severity: "error" | "warning";
  code: string;
  message: string;
}

export interface StreamGraphNodeStatus {
  state:
    | "draft"
    | "valid"
    | "starting"
    | "running"
    | "stalled"
    | "stopped"
    | "blocked"
    | "error";
  output_stream_id?: string;
  worker_id?: string;
  thread_slot_id?: string;
  frames_processed?: number;
  last_frame_at_us?: number;
  message?: string;
}

export interface StreamGraphStatusSummary {
  graph_id: string;
  run_state:
    | "draft"
    | "valid"
    | "starting"
    | "running"
    | "stalled"
    | "stopped"
    | "error";
  active_run_id: string | null;
  node_statuses: Record<string, StreamGraphNodeStatus>;
}

export interface StreamGraphListMessage {
  type: "stream_graph_list";
  request_id: string;
  graphs: StreamGraphDefinition[];
  statuses: Record<string, StreamGraphStatusSummary>;
}

export interface StreamGraphSavedMessage {
  type: "stream_graph_saved";
  request_id: string;
  graph_id: string;
  graph: StreamGraphDefinition;
}

export interface StreamGraphValidationMessage {
  type: "stream_graph_validation";
  request_id: string;
  graph_id: string;
  valid: boolean;
  graph_diagnostics?: StreamGraphDiagnostic[];
  node_diagnostics: Record<string, StreamGraphDiagnostic[]>;
  edge_diagnostics: Record<string, StreamGraphDiagnostic[]>;
}

export interface StreamGraphStatusMessage {
  type: "stream_graph_status";
  request_id: string;
  graph_id: string;
  status: StreamGraphStatusSummary;
}

export interface StreamGraphStartedMessage {
  type: "stream_graph_started";
  request_id: string;
  graph_id: string;
  graph_run_id: string;
  node_statuses: Record<string, StreamGraphNodeStatus>;
}

export interface StreamGraphStoppedMessage {
  type: "stream_graph_stopped";
  request_id: string;
  graph_id: string;
  graph_run_id: string | null;
  node_statuses: Record<string, StreamGraphNodeStatus>;
}

export type WebSocketMessage =
  | StreamListMessage
  | StatusMessage
  | ErrorMessage
  | PublishResultMessage
  | TransformCapabilitiesMessage
  | NodeCatalogMessage
  | TransformResultMessage
  | TransformListMessage
  | TransformStoppedMessage
  | ImuDataMessage
  | ImuBulkDataMessage
  | MuseDataMessage
  | MuseBulkDataMessage
  | EmgDataMessage
  | TransformProvenanceMessage
  | StreamGraphListMessage
  | StreamGraphSavedMessage
  | StreamGraphValidationMessage
  | StreamGraphStatusMessage
  | StreamGraphStartedMessage
  | StreamGraphStoppedMessage;

// Client-to-server messages
export interface SubscribeAction {
  action: "subscribe";
  stream_ids: string[];
}

export interface UnsubscribeAction {
  action: "unsubscribe";
  stream_ids: string[];
}

export interface GetStreamsAction {
  action: "get_streams";
}

export interface ListTransformCapabilitiesAction {
  action: "list_transform_capabilities";
  request_id: string;
}

export interface ListNodeCatalogAction {
  action: "list_node_catalog";
  request_id: string;
}

export interface PublishSessionBundleAction {
  action: "publish_session_bundle";
  request_id: string;
  session_id: string;
  meta_records: unknown[];
  marker_events: unknown[];
}

export interface CreateTransformAction {
  action: "create_transform" | "create_emg_transform";
  request_id: string;
  source_stream_id: string;
  output_identifier: string;
  transform_kind: TransformKind;
  input_mapping_id?: string;
  config: {
    cutoff_hz?: number;
    low_cutoff_hz?: number;
    high_cutoff_hz?: number;
    notch_hz?: number;
    notch_q?: number;
    iir_method?: "butterworth" | "biquad";
    butterworth_order?: number;
    biquad_q?: number;
    harmonic_count?: number;
    window_samples?: number;
    step_samples?: number;
  };
}

export interface ListTransformsAction {
  action: "list_transforms" | "list_emg_transforms";
  request_id: string;
}

export interface StopTransformAction {
  action: "stop_transform" | "stop_emg_transform";
  request_id: string;
  output_stream_id: string;
}

export interface ListStreamGraphsAction {
  action: "list_stream_graphs";
  request_id: string;
}

export interface SaveStreamGraphAction {
  action: "save_stream_graph";
  request_id: string;
  graph: StreamGraphDefinition;
}

export interface ValidateStreamGraphAction {
  action: "validate_stream_graph";
  request_id: string;
  graph: StreamGraphDefinition;
}

export interface GetStreamGraphStatusAction {
  action: "get_stream_graph_status";
  request_id: string;
  graph_id: string;
}

export interface StartStreamGraphAction {
  action: "start_stream_graph";
  request_id: string;
  graph_id: string;
}

export interface StopStreamGraphAction {
  action: "stop_stream_graph";
  request_id: string;
  graph_id: string;
}

export type CreateEmgTransformAction = CreateTransformAction;
export type ListEmgTransformsAction = ListTransformsAction;
export type StopEmgTransformAction = StopTransformAction;

export type ClientAction =
  | SubscribeAction
  | UnsubscribeAction
  | GetStreamsAction
  | ListTransformCapabilitiesAction
  | ListNodeCatalogAction
  | PublishSessionBundleAction
  | CreateTransformAction
  | ListTransformsAction
  | StopTransformAction
  | ListStreamGraphsAction
  | SaveStreamGraphAction
  | ValidateStreamGraphAction
  | GetStreamGraphStatusAction
  | StartStreamGraphAction
  | StopStreamGraphAction;
