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

// The backend proxies the ML control plane over this connection (Phase 5,
// decision #3): a control-plane message arrives wrapped so it can't collide
// with stream_viewer's own message types. `message` is an MlControlPlaneMessage
// (typed in MlPipeline/types.ts); kept as unknown here to avoid a dependency
// cycle from the shared base module up into MlPipeline.
export interface MlControlPlaneEnvelopeMessage {
  type: "ml_control_plane";
  message: unknown;
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

// A MarkerEventV1 record forwarded from a marker stream (Phase 2). Cue/session
// events for one session_id — rendered as ticks/regions + data-chart overlays.
export interface MarkerMessage {
  type: "marker";
  stream_id: string;
  schema_name?: string;
  encoding: EncodingInfo;
  session_id: string;
  marker_type: string;
  marker_id: string;
  event: string;
  label: string;
  // Canonical marker time axis (microseconds). Mirrored as `timestamp` too.
  emitted_at_us: number;
  timestamp?: number;
  attributes: Record<string, unknown>;
}

// A marker event buffered client-side for rendering (adds arrival time).
export interface BufferedMarkerEvent {
  session_id: string;
  marker_type: string;
  marker_id: string;
  event: string;
  label: string;
  emitted_at_us: number;
  attributes: Record<string, unknown>;
  received_at_ms: number;
}

// Reply to query_stream_time (Phase 3): a stream's retained offset bounds and,
// if a timestamp was queried, the offset at/after it. Offsets: -1 = end/none,
// -2 = beginning, >=0 concrete.
export interface StreamTimeMessage {
  type: "stream_time";
  request_id?: string;
  stream_id: string;
  valid: boolean;
  earliest_offset?: number;
  latest_offset?: number;
  offset_for_timestamp?: number;
  reason?: string;
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

// Per-stream live buffers, so any number of viewers can be inspected at once
// (keyed by stream id). deviceName is the latest device_id seen on a frame — the
// human name a source node prefers over its raw stream id.
export interface LiveStreamData {
  streamType: "imu" | "muse" | "emg" | null;
  emgSamples: BufferedEmgSample[];
  museSamples: MuseSample[];
  imuSamples: ImuSample[];
  // Markers accumulate here for streams whose schema is MarkerEventV1 (Phase 2).
  markers: BufferedMarkerEvent[];
  deviceName?: string;
}

export interface StreamGraphViewport {
  x: number;
  y: number;
  zoom: number;
}

// A generic, sensor-agnostic recording protocol (Phase 4). Generalizes the EMG
// gesture experiment into a reusable definition any classification task can use:
// an ordered class vocabulary, per-class hold/rest timing, a run/repetition
// count, and protocol metadata. The cue engine (experiment.ts) is driven from
// this — no gesture-specific hardcoding. Lives here (the shared types module) so
// both the session node and the cue engine can reference it without a cycle.
export interface SessionProtocol {
  protocol_id: string;
  label: string;
  // Ordered class vocabulary; each hold cue draws its label from here.
  classes: string[];
  // Filler/idle class for lead-in, inter-cue rest, and tail-rest phases.
  rest_class: string;
  repetitions: number;
  hold_s: number;
  rest_s: number;
  lead_in_s: number;
  tail_rest_s: number;
  seed: number;
}

// Config for a train node (Phase 5): mirrors the control-plane
// start_train_validate_job payload. The dataset is selected by run selectors
// ("<session_id>:<run_index>"); field selection is descriptor channel paths.
export interface TrainNodeConfig {
  families: string[];
  train_runs: string[];
  eval_runs: string[];
  selected_fields: string[];
  window_ms: number;
  hop_ms: number;
  vote_windows: number;
  confidence_threshold: number;
  min_hold_windows: number;
  rest_gesture: string;
  active_gesture: string;
}

export type StreamGraphNodeKind =
  | "stream_source"
  | "transform"
  | "viewer"
  | "sink"
  | "combine"
  | "experiment"
  | "train";

export interface StreamGraphBaseNode<K extends StreamGraphNodeKind = StreamGraphNodeKind> {
  id: string;
  kind: K;
  label: string;
  position: StreamGraphPosition;
  input_port_ids?: string[];
  output_port_ids?: string[];
  // Optional editor-only manual size overrides (from the resize handle). Persist
  // via editor_metadata; the backend ignores them.
  width?: number;
  height?: number;
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
  // When true the live chart renders directly on the node in the editor instead
  // of only in the click-to-open overlay. Persists via the editor_metadata
  // round-trip; the backend never interprets it.
  inline_graph?: boolean;
  // Topic-aware channels (Part D): when the incoming channel carries markers, a
  // phantom "markers" input appears on the node; enabling it (this flag) overlays
  // the markers on the waveform. Editor-only, rides editor_metadata.
  show_markers?: boolean;
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

// Records N upstream sensor streams under one protocol/marker timeline and
// publishes a labeled session bundle (client-driven, via publish_session_bundle).
// Exposes a single `markers` output — the MarkerEventV1 stream for its
// `experiment_id` (used verbatim as the recording session_id), which downstream
// marker-aware nodes subscribe to. The protocol + metadata live in `config` so
// they round-trip through the backend's generic node config.
// (Formerly the "session" node — Phase 4 / experiments-and-time Phase 1.)
export interface ExperimentNodeConfig {
  protocol: SessionProtocol;
  // Stable identifier for this experiment; used verbatim as the recording
  // session_id and as the key of the Marker/<experiment_id> topic the `markers`
  // output resolves to. Generated once when the node is created.
  experiment_id: string;
  participant_id?: string;
  notes?: string;
}

export interface StreamGraphExperimentNode extends StreamGraphBaseNode<"experiment"> {
  kind: "experiment";
  config: ExperimentNodeConfig;
  // Editor-only: render the participant-facing run panel directly on the node
  // card (like a viewer's inline_graph). Persists via editor_metadata; the
  // backend ignores it.
  inline_experiment?: boolean;
}

// Backward-compat aliases (the node kind was renamed session -> experiment).
export type SessionNodeConfig = ExperimentNodeConfig;
export type StreamGraphSessionNode = StreamGraphExperimentNode;

// Submits a control-plane train_validate job (client-driven via the ML proxy);
// its output is a durable model artifact, not a stream. (Phase 5.)
export interface StreamGraphTrainNode extends StreamGraphBaseNode<"train"> {
  kind: "train";
  config: TrainNodeConfig;
}

export type StreamGraphNode =
  | StreamGraphSourceNode
  | StreamGraphTransformNode
  | StreamGraphViewerNode
  | StreamGraphSinkNode
  | StreamGraphCombineNode
  | StreamGraphExperimentNode
  | StreamGraphTrainNode;

export interface StreamGraphEdge {
  id: string;
  source_node_id: string;
  source_port: string;
  target_node_id: string;
  target_port: string;
  // Topic-aware channels: StreamType strings ("Data" | "Marker" | "Meta") hidden
  // on this link, so they don't reach the target node. Empty/absent = the whole
  // channel flows. Toggled from the edge topic badge; honored by the target's
  // input resolution (viewer overlay, combine merge lanes).
  hidden_topic_types?: string[];
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
  // Opaque frontend-only metadata (Phase 7): the unflattened composite editor
  // tree (an EditorGraphDefinition). The backend stores + returns it verbatim so
  // a composite graph reloads from the backend alone; typed `unknown` here to
  // avoid a dependency cycle with the editor's composite types.
  editor_metadata?: unknown;
}

export interface StreamGraphDiagnostic {
  severity: "error" | "warning";
  code: string;
  message: string;
}

// One topic carried by a node's output channel (topic-aware channels, Part A).
// `type` is the StreamType string ("Data" | "Marker" | "Meta"); `id` is the
// stableStreamId of the full topic (stringified uint64).
export interface OutputChannelTopic {
  type: string;
  id: string;
  schema: string;
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
  // The node's output channel: a topic set, at most one per type. Absent on old
  // backends / nodes with no output; when present it includes the DATA topic
  // whose id equals output_stream_id for the one-topic (backward-compat) case.
  output_topics?: OutputChannelTopic[];
  worker_id?: string;
  thread_slot_id?: string;
  frames_processed?: number;
  last_frame_at_us?: number;
  message?: string;
}

// The kind of a channel, derived from its topic set (Part A). Input ports
// relabel themselves with these; the edge badge and viewer phantom input read
// them too.
export type ChannelKind = "data" | "markers" | "stream" | "empty";

export function channelKindFromTopics(
  topics: OutputChannelTopic[] | undefined,
): ChannelKind {
  if (!topics || topics.length === 0) return "empty";
  const hasData = topics.some((t) => t.type === "Data");
  const hasMarker = topics.some((t) => t.type === "Marker");
  if (hasData && hasMarker) return "stream";
  if (hasMarker) return "markers";
  return "data";
}

// The MARKER topic in a channel, if any (used to route markers + reveal the
// viewer's phantom markers input).
export function markerTopicOfChannel(
  topics: OutputChannelTopic[] | undefined,
): OutputChannelTopic | undefined {
  return topics?.find((t) => t.type === "Marker");
}

// The DATA topic in a channel, if any.
export function dataTopicOfChannel(
  topics: OutputChannelTopic[] | undefined,
): OutputChannelTopic | undefined {
  return topics?.find((t) => t.type === "Data");
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

// Individual profiles (Phase 4): a person persisted so they can walk up later
// and resume live classifying in one click. Thin pointer — the trained bundle
// path is baked into the referenced classify graph (graph_id).
export interface Profile {
  participant_id: string;
  display_name: string;
  model_path: string;
  graph_id: string;
  protocol_id: string;
  device_id: string;
  session_ids: string[];
  best_accuracy: number;
  created_at_us: number;
  updated_at_us: number;
}

export interface ProfileListMessage {
  type: "profile_list";
  request_id: string;
  profiles: Profile[];
}

export interface ProfileSavedMessage {
  type: "profile_saved";
  request_id: string;
  participant_id: string;
  profile: Profile;
}

export interface ProfileDeletedMessage {
  type: "profile_deleted";
  request_id: string;
  participant_id: string;
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
  | MlControlPlaneEnvelopeMessage
  | TransformResultMessage
  | TransformListMessage
  | TransformStoppedMessage
  | ImuDataMessage
  | ImuBulkDataMessage
  | MuseDataMessage
  | MuseBulkDataMessage
  | EmgDataMessage
  | MarkerMessage
  | StreamTimeMessage
  | TransformProvenanceMessage
  | StreamGraphListMessage
  | StreamGraphSavedMessage
  | StreamGraphValidationMessage
  | StreamGraphStatusMessage
  | StreamGraphStartedMessage
  | StreamGraphStoppedMessage
  | ProfileListMessage
  | ProfileSavedMessage
  | ProfileDeletedMessage;

// Client-to-server messages
export interface SubscribeAction {
  action: "subscribe";
  stream_ids: string[];
  // Optional historical start (Phase 3): -1 live tail (default), -2 beginning,
  // >=0 a concrete offset (e.g. from a query_stream_time offset_for_timestamp).
  start_offset?: number;
}

// Ask the backend for a stream's retained offset bounds and, when timestamp_us
// is given, the offset at/after that time (offsets_for_times) — so the UI knows
// the available history extent and can map a scrubbed timestamp to an offset.
export interface QueryStreamTimeAction {
  action: "query_stream_time";
  request_id?: string;
  stream_id: string;
  timestamp_us?: number;
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

// Wraps an ML control-plane action for the backend to forward upstream (Phase 5).
export interface MlProxyAction {
  action: "ml_proxy";
  message: unknown;
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
  // Optional replay start (Phase 5): -1 live (default), -2 beginning, >=0 a
  // concrete offset (from a query_stream_time offset_for_timestamp). Only the
  // graph's root sources seek to it; the re-run chain feeds downstream live.
  start_offset?: number;
}

export interface StopStreamGraphAction {
  action: "stop_stream_graph";
  request_id: string;
  graph_id: string;
}

// Incremental reactivity (Phase 7): restart one node + its downstream subgraph
// in a running graph after its config was saved.
export interface RestartStreamGraphNodeAction {
  action: "restart_stream_graph_node";
  request_id: string;
  graph_id: string;
  node_id: string;
}

export interface ListProfilesAction {
  action: "list_profiles";
  request_id: string;
}

export interface SaveProfileAction {
  action: "save_profile";
  request_id: string;
  profile: Profile;
}

export interface DeleteProfileAction {
  action: "delete_profile";
  request_id: string;
  participant_id: string;
}

export type CreateEmgTransformAction = CreateTransformAction;
export type ListEmgTransformsAction = ListTransformsAction;
export type StopEmgTransformAction = StopTransformAction;

export type ClientAction =
  | SubscribeAction
  | UnsubscribeAction
  | QueryStreamTimeAction
  | GetStreamsAction
  | ListTransformCapabilitiesAction
  | ListNodeCatalogAction
  | MlProxyAction
  | PublishSessionBundleAction
  | CreateTransformAction
  | ListTransformsAction
  | StopTransformAction
  | ListStreamGraphsAction
  | SaveStreamGraphAction
  | ValidateStreamGraphAction
  | GetStreamGraphStatusAction
  | StartStreamGraphAction
  | StopStreamGraphAction
  | RestartStreamGraphNodeAction
  | ListProfilesAction
  | SaveProfileAction
  | DeleteProfileAction;
