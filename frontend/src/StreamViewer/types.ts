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
  // Frame version 2 onwards. The backend always emits this key, so it is not
  // optional -- but for a version 1 stream (anything recorded before 2026-08)
  // the values are zero and has_data.magnetometer is false. ⚠️ CHECK has_data,
  // not the numbers: (0,0,0) is a legitimate magnetic field reading in
  // principle, so a zero test cannot tell absent from measured.
  mag: ImuVector3;
}

export interface ImuAccuracies {
  accelerometer: number;
  gyroscope: number;
  rotation: number;
  magnetometer: number;
}

export interface ImuHasData {
  accelerometer: boolean;
  gyroscope: boolean;
  rotation: boolean;
  // False for every version 1 frame. See ImuData.mag.
  magnetometer: boolean;
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
// A model a train node produced (provenance edges, Phase 4). Stored on the
// train node's config so it round-trips through editor_metadata; a
// train→classify provenance edge lets a classify node pick from this list.
export interface TrainedModel {
  job_id: string;
  bundle_path: string | null;
  model_path: string | null;
  family: string | null;
  accuracy: number | null;
  completed_at_us: number;
}

export interface TrainNodeConfig {
  families: string[];
  // Run selectors ("<session_id>:<run_index>") — the Kafka-reconstruction dataset.
  // Kept because a session still inside retention can be trained on directly.
  train_runs: string[];
  eval_runs: string[];
  // Instance references (instance GRAPH ids) — the durable dataset
  // (experiment-history-snapshots-plan, Phase 6). Strictly better inputs: a fixed
  // window, materialized + checksummed files, a recorded label histogram, and
  // provenance back to the exact graph that produced them. The backend swaps these
  // for artifact paths when the job is submitted, so training never touches the
  // broker and works long after retention would have dropped the records.
  train_instances?: string[];
  eval_instances?: string[];
  selected_fields: string[];
  window_ms: number;
  hop_ms: number;
  vote_windows: number;
  confidence_threshold: number;
  min_hold_windows: number;
  rest_gesture: string;
  active_gesture: string;
  // Models this train node has produced (most-recent-appended). Populated on
  // each completed job; surfaced as the train→classify model dropdown.
  models?: TrainedModel[];
}

export type StreamGraphNodeKind =
  | "stream_source"
  | "transform"
  | "viewer"
  | "sink"
  | "combine"
  | "markers"
  // Retired in favour of "markers" + a stored Experiment
  // (experiment-history-snapshots-plan). Still in the union because old boards
  // are still parsed and rendered; nothing creates one any more.
  | "experiment"
  | "train"
  | "export";

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
  // ⚠️ OPTIONAL, because a source with no stream chosen yet is a real state — a
  // starter template on a rig that is not currently streaming, or a node dropped
  // before picking from the dropdown (TEC-NATKIT-66).
  //
  // This was `string`, which made `""` the only way to express "unbound" — and the
  // backend parses stream_id only if the key is PRESENT and then demands a
  // non-negative integer, so `""` silently made the whole board unsavable. The type
  // asserted something false and the bug followed from it.
  stream_id?: string;
  schema_name?: string;
  // Which body position this sensor is worn at (TEC-NATKIT-62). One of
  // SENSOR_POSITION_NAMES; absent or "N/A" means not stated.
  //
  // ⚠️ It belongs on the SOURCE, not on the calibration viewer that also carries
  // one: a position is a property of where the sensor IS, and it is the
  // stream↔limb pairing an exported file needs in order to say which signal came
  // from which arm. A board with no calibration node would otherwise have nowhere
  // to record placement at all.
  sensor_position?: string;
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
  // What this viewer draws. Absent = the schema-chosen renderer (waveform, IMU,
  // markers...). "imu_calibration" instead shows the per-sensor calibration
  // quality of the upstream IMU, mirroring the IMU Experiment tab's concept of
  // whether a board is calibrated while worn. Editor-only, rides editor_metadata.
  display_mode?: "imu_calibration";
  // Which body position this board is mounted at, so the readout is labelled the
  // way the person is set up. One of SENSOR_POSITION_NAMES.
  sensor_position?: string;
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

// The config-less marker source that replaced the experiment node
// (experiment-history-snapshots-plan, Phase 1). Markers are wired data — the
// viewer overlay, combine's marker lane and export's label join all consume
// them — so the wiring survives the experiment leaving the canvas. It resolves
// Marker/<experiment_id> from the GRAPH's bound experiment, so there is nothing
// to author on it and nothing to get wrong.
export interface StreamGraphMarkersNode extends StreamGraphBaseNode<"markers"> {
  kind: "markers";
  // Editor-only: render the participant-facing run panel for the board's bound
  // experiment directly on the node card (like a viewer's inline_graph). Persists
  // via editor_metadata; the backend ignores it.
  inline_experiment?: boolean;
}

// Submits a control-plane train_validate job (client-driven via the ML proxy);
// its output is a durable model artifact, not a stream. (Phase 5.)
export interface StreamGraphTrainNode extends StreamGraphBaseNode<"train"> {
  kind: "train";
  config: TrainNodeConfig;
}

// Writes its inputs to a durable dataset file via a control-plane export job
// (client-driven via the ML proxy, like train). Terminal: its artifact is a
// file, not a stream.
export interface ExportNodeConfig {
  // Only "parquet" ships in v1; kept as a field so a second writer (csv, hdf5)
  // is a config change rather than a new node kind.
  format: "parquet";
  // Column name for the cue class joined onto each frame.
  label_field: string;
  // Restrict to one run inside a multi-run session (1-based); null = whole session.
  run_index?: number | null;
}

export interface StreamGraphExportNode extends StreamGraphBaseNode<"export"> {
  kind: "export";
  config: ExportNodeConfig;
}

// Outcome of a parquet download, surfaced on the export node's inspector. The
// counts come back as X-Natkit-* response headers alongside the file itself.
export interface ExportDownloadResult {
  status: "downloading" | "downloaded" | "failed";
  message: string;
  fileName?: string;
  sessionId?: string;
  frameCount?: number | null;
  labelledFrameCount?: number | null;
  markerCount?: number | null;
  // The drain stopped on the backend's time budget, so the file is a prefix of
  // the stream rather than all of it.
  truncated?: boolean;
}

export type StreamGraphNode =
  | StreamGraphSourceNode
  | StreamGraphTransformNode
  | StreamGraphViewerNode
  | StreamGraphSinkNode
  | StreamGraphCombineNode
  | StreamGraphMarkersNode
  | StreamGraphExperimentNode
  | StreamGraphTrainNode
  | StreamGraphExportNode;

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
  // Provenance edges express data lineage / control wiring (source->experiment,
  // experiment->train, train->classify) rather than a streaming data path. They
  // persist with the graph but are EXCLUDED from the executed data-flow — they
  // resolve node configuration at author/submit time. "data" (default) is a
  // normal streaming edge; "provenance" is dropped by flattenGraph (like param
  // nodes) so the executed graph stays purely data edges.
  edge_kind?: "data" | "provenance";
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

  // --- Experiment history (experiment-history-snapshots-plan) ---------------
  // A graph is one of three things:
  //   live board : experiment_id set (or not), instance_id absent  — editable
  //   recording  : instance_id set, immutable, origin "recording"
  //   fork       : instance_id set, editable, origin "fork", forked_from set
  // All of these are BACKEND-OWNED: handleSaveStreamGraph re-pins them from the
  // stored record, so a save can't launder a fork into a recording or re-parent
  // it. Read them; never author them.
  experiment_id?: string;
  // Which workspace this board is filed under, or absent for Unfiled
  // (TEC-NATKIT-56). A board carries its own so an unbound analysis board has
  // somewhere to live; once an experiment is bound, save_experiment stamps the
  // experiment's workspace here, because two halves of one binding in different
  // workspaces is a state no picker could show honestly.
  workspace_id?: string;
  instance_id?: string;
  immutable?: boolean;
  origin?: "recording" | "fork";
  forked_from?: string;
  recording?: InstanceRecording;
}

// The captured session behind an instance. A fork inherits this verbatim from
// its ancestor recording, so it points at the same materialized files — forking
// changes the pipeline, never the data. Written by the backend from Phase 2/3;
// read-only here.
export interface InstanceRecording {
  session_id: string;
  // WHO was recorded, and WHAT they were asked to do, captured when the instance
  // was created. Before this existed both were resolved at read time through the
  // live experiment's editable fields, so retyping the participant retroactively
  // reassigned every past run of that experiment while the artifact checksums
  // kept verifying. Read these; never author them.
  participant_id?: string;
  protocol?: unknown;
  // Set only on runs repaired by the one-time back-fill. Three states have to stay
  // distinguishable: captured at record time (neither flag), recovered from the
  // experiment record afterwards (`participant_backfilled` — a weaker claim), and
  // never entered by anyone (`participant_unrecorded` — no claim at all, which is
  // what every run made before the Record gate existed turns out to be).
  participant_backfilled?: boolean;
  participant_unrecorded?: boolean;
  protocol_backfilled?: boolean;
  // What was worn where, as recorded (TEC-NATKIT-62). Read; never author.
  sensor_positions?: { stream_id: string; position: string }[];
  // Present only on runs taken below the calibration minimum on purpose
  // (TEC-NATKIT-63), carrying the reason shown at the time. Its ABSENCE is the
  // claim that the run met the threshold, so it must never be written by anything
  // other than the gate.
  calibration_override?: string;
  window_start_us?: number;
  window_end_us?: number | null;
  streams?: {
    stream_id: string;
    schema_name?: string;
    role?: string;
    node_id?: string;
  }[];
  artifacts?: {
    directory?: string;
    markers?: string;
    markers_sha256?: string;
    total_rows?: number;
    data?: {
      stream_id: string;
      schema_name?: string;
      path: string;
      rows?: number;
      labelled_rows?: number;
      // Rows per cue class; "(unlabelled)" collects rows inside the window but
      // between cues. This is what tells you a run is unusable because one class
      // never fired, which a row count alone cannot.
      label_counts?: Record<string, number>;
      sha256?: string;
      checksum_error?: string;
      // The drain stopped on its budget, so the file is a prefix of the stream.
      truncated?: boolean;
    }[];
  };
  // recording -> materializing -> complete | failed. Only `complete` is sealed
  // (immutable); a failed instance stays editable so it can be retried or deleted,
  // because sealing an empty snapshot is the failure mode this guards against.
  status?: "recording" | "materializing" | "complete" | "failed";
  message?: string;
}

// An experiment: the first-class object that owns a board and its recorded
// history (experiment-history-snapshots-plan). This is where the protocol,
// participant and notes moved when the experiment stopped being a node — the
// canvas keeps only a config-less `markers` source.
//
// The binding to a board is 1:1 and lives on both sides (`live_graph_id` here,
// `experiment_id` on the graph). save_experiment is the sole writer of the pair,
// so setting `live_graph_id` IS the bind action.
export interface Experiment {
  experiment_id: string;
  label: string;
  // Which workspace this experiment belongs to, or absent for Unfiled
  // (TEC-NATKIT-56). Scoping the picker to this is the point of the container.
  workspace_id?: string;
  // Declared as SessionProtocol, but a StepProtocol is equally legitimate here
  // and is what the step editor stores; `isStepProtocol` discriminates at the
  // read sites. Widening this union cascades through ExperimentPanel's
  // patch-a-protocol callbacks, so callers cast on the way in instead.
  protocol: SessionProtocol | null;
  // DEPRECATED (TEC-NATKIT-55): the participant belongs to a RUN, and is passed
  // with start_experiment_instance. Kept only so the stored value survives a
  // round trip — it is the one-time back-fill's only source for runs recorded
  // before the instance snapshotted its own participant. Do not read it, do not
  // offer it for editing.
  participant_id?: string;
  notes: string;
  live_graph_id: string;
  created_at_us: number;
  updated_at_us: number;
}

// --- Workspaces (TEC-NATKIT-56) -------------------------------------------
//
// A selectable container, so picking an experiment is not picking from every
// experiment ever made. Cohorts are the motivation: one workspace per study, with
// its experiments, boards and participant roster inside it.
//
// It is a container and nothing more — the 1:1 experiment↔board binding is
// untouched, boards do not inherit the workspace's experiment, and protocols are
// not shared by reference.
//
// Membership lives on the MEMBER (`workspace_id` on experiments, boards and
// profiles) and is deliberately not mirrored into a list here: two copies of the
// same fact drift the first time something is deleted while a client holds a
// stale list.
export interface Workspace {
  workspace_id: string;
  label: string;
  notes: string;
  created_at_us: number;
  updated_at_us: number;
}

export interface WorkspaceListMessage {
  type: "workspace_list";
  request_id: string;
  workspaces: Workspace[];
}

export interface WorkspaceSavedMessage {
  type: "workspace_saved";
  request_id: string;
  workspace_id: string;
  workspace: Workspace;
}

export interface WorkspaceDeletedMessage {
  type: "workspace_deleted";
  request_id: string;
  workspace_id: string;
}

export interface ListWorkspacesAction {
  action: "list_workspaces";
  request_id: string;
}

export interface SaveWorkspaceAction {
  action: "save_workspace";
  request_id: string;
  workspace: Workspace;
}

// ⚠️ Deleting a workspace does NOT delete its contents: experiments, boards and
// profiles survive with an empty `workspace_id`, which puts them in Unfiled. The
// affordance that empties a filing cabinet reads as tidying up, so it must never
// destroy a cohort's recorded history.
export interface DeleteWorkspaceAction {
  action: "delete_workspace";
  request_id: string;
  workspace_id: string;
}

export interface ExperimentListMessage {
  type: "experiment_list";
  request_id: string;
  experiments: Experiment[];
}

export interface ExperimentSavedMessage {
  type: "experiment_saved";
  request_id: string;
  experiment_id: string;
  experiment: Experiment;
}

export interface ExperimentDeletedMessage {
  type: "experiment_deleted";
  request_id: string;
  experiment_id: string;
}

// An instance's state, sent in reply to start/finish and BROADCAST when
// materialization finishes (which can be long after the request that started it).
export interface ExperimentInstanceMessage {
  type: "experiment_instance";
  request_id: string;
  graph_id: string;
  instance_id: string;
  graph: StreamGraphDefinition;
}

export interface StreamGraphDeletedMessage {
  type: "stream_graph_deleted";
  request_id: string;
  graph_id: string;
}

// A fork: an instance that happens to be editable. It INHERITS the ancestor's
// `recording`, so it points at the same materialized files — forking changes the
// pipeline, never the data.
export interface StreamGraphForkedMessage {
  type: "stream_graph_forked";
  request_id: string;
  graph: StreamGraphDefinition;
}

// A replay session: an instance's Parquet streamed back onto SCRATCH Kafka topics.
// Sent in reply to start/stop and broadcast as progress lands (the replay runs on
// its own thread and finishes long after the request).
export interface InstanceReplayMessage {
  type: "instance_replay";
  request_id: string;
  replay_id: string;
  graph_id: string;
  state: "started" | "running" | "stopping" | "stopped" | "finished" | "failed";
  // Maps each recorded source's ORIGINAL stream id to the scratch topic replaying
  // it. start_stream_graph does the same rebinding server-side from `replay_id`.
  bindings: {
    original_stream_id: string;
    replay_stream_id: string;
    topic: string;
    frame_count: number;
    channel_labels: string[];
  }[];
  marker_stream_id: string;
  marker_count: number;
  total_frames: number;
  // The ORIGINAL device timestamps — replay never restamps them.
  first_ts_us: number;
  last_ts_us: number;
  frames_published: number;
  markers_published: number;
  last_published_ts_us: number;
  error?: string;
}

// Re-check of an instance's artifacts against their recorded checksums.
export interface ExperimentInstanceVerificationMessage {
  type: "experiment_instance_verification";
  request_id: string;
  graph_id: string;
  instance_id: string;
  ok: boolean;
  artifacts: {
    path: string;
    ok: boolean;
    size?: number;
    expected_sha256?: string;
    actual_sha256?: string;
    problem?: string;
  }[];
}

// One record a device emitted on its LOGGING_LOG topic while running a command.
export interface DeviceLogRecord {
  schema_version?: string;
  source?: string;
  command_id?: string;
  command?: string;
  level?: string;
  ok?: boolean;
  terminal?: boolean;
  message?: string;
  emitted_at_us?: number;
}

// Result of a command sent to a device on its EXECUTION_COMMAND topic. The
// backend waits for the device's correlated answer, so `records` is what the
// device actually said -- `timed_out` means it said nothing at all.
export interface DeviceCommandResultMessage {
  type: "device_command_result";
  request_id: string;
  stream_id: string;
  command: string;
  command_id: string;
  ok: boolean;
  timed_out: boolean;
  error?: string;
  records: DeviceLogRecord[];
}

// --- device health (TEC-NATKIT-33) ----------------------------------------
//
// The rig's own health, pushed once a second while subscribed. Every figure in
// `fields` is CUMULATIVE SINCE THE DEVICE BOOTED, which is why `rates` exists
// separately: the backend differences two samples over at least 5 s of the
// DEVICE's clock and reports per-second figures.
//
// ⚠️ `rates` is null when there is no rate to report, and that is not the same as
// a rate of zero. Render a dash. The difference matters most in exactly the
// moment somebody is staring at this panel to work out what is wrong.
export type DeviceRateStatus =
  | "available"
  | "first_sample"
  | "rebooted"
  | "clock_not_advanced"
  | "window_too_short";

export interface DeviceHealthEntry {
  /** A string, not a number: these ids exceed 2^53 and would round. */
  device_id: string;
  role: "hub" | "leaf";
  /**
   * Milliseconds since the BACKEND last received a frame from this device.
   * ⚠️ The only field that can say a device has gone silent -- the frame itself
   * cannot, because a device that stops sending leaves a last frame that looks
   * healthy forever.
   */
  age_ms: number;
  quiet: boolean;
  /** The latest frame, keyed exactly as the schema descriptor names its fields. */
  fields: Record<string, unknown>;
  rate_status: DeviceRateStatus;
  /** Per-second rates, or null. Null is not zero. */
  rates: Record<string, number> | null;
  /** How much device clock the rates span, so the figure can be weighed. */
  rate_interval_us?: number;
}

export interface DeviceHealthMessage {
  type: "device_health";
  wall_ms: number;
  quiet_after_ms: number;
  /**
   * How many status topics the backend is tailing. Distinguishes "the rig has
   * never published" (0) from "every board went silent" (>0 with everything
   * quiet), which look identical from the devices list alone.
   */
  topics_tailed: number;
  devices: DeviceHealthEntry[];
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
  // Which workspace's roster this participant is on, or absent for Unfiled.
  // ⚠️ ONE workspace: the same person cannot yet appear in two cohorts.
  workspace_id?: string;
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
  | ProfileDeletedMessage
  | WorkspaceListMessage
  | WorkspaceSavedMessage
  | WorkspaceDeletedMessage
  | ExperimentListMessage
  | ExperimentSavedMessage
  | ExperimentDeletedMessage
  | ExperimentInstanceMessage
  | StreamGraphDeletedMessage
  | StreamGraphForkedMessage
  | ExperimentInstanceVerificationMessage
  | InstanceReplayMessage
  | DeviceCommandResultMessage
  | DeviceHealthMessage;

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
  // Optional historical start: -1 live (default), -2 beginning, >=0 a concrete
  // offset (from a query_stream_time offset_for_timestamp). Only the graph's root
  // sources seek to it; the re-run chain feeds downstream live.
  start_offset?: number;
  // Run this graph against a REPLAY instead of live topics: every stream_source
  // whose recorded stream the replay covers is rebound to that replay's scratch
  // topic for this run. The stored graph keeps its recorded ids — that is
  // provenance, not configuration.
  replay_id?: string;
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

export interface ListExperimentsAction {
  action: "list_experiments";
  request_id: string;
}

// Also the bind action: `live_graph_id` is the board this experiment records
// with, and the backend stamps `experiment_id` onto that graph (clearing it from
// any other live board) so the 1:1 pair can't drift.
export interface SaveExperimentAction {
  action: "save_experiment";
  request_id: string;
  experiment: Experiment;
}

export interface DeleteExperimentAction {
  action: "delete_experiment";
  request_id: string;
  experiment_id: string;
}

// Mint an instance: snapshot the experiment's live board and open the recording
// window. The reply carries the instance graph, whose graph_id the client hands
// back to finish_experiment_instance when the run ends.
export interface StartExperimentInstanceAction {
  action: "start_experiment_instance";
  request_id: string;
  experiment_id: string;
  // WHO this run is of. Per run, not per experiment: one experiment records a
  // whole cohort, so the procedure cannot name the person. Omitted or empty is
  // recorded by the backend as explicitly unattributed rather than inherited.
  participant_id?: string;
  // The stream↔limb mapping at the moment of recording (TEC-NATKIT-62). Snapshotted
  // per run because the same board records different participants with the sensors
  // physically re-placed each time — a mapping that lives only on the board is not
  // evidence about any particular run.
  sensor_positions?: { stream_id: string; position: string }[];
  // Set when the operator recorded through the calibration gate (TEC-NATKIT-63).
  // The value is the reason they were shown, so the run says WHAT was overridden.
  calibration_override?: string;
  window_start_us?: number;
}

// Close the window and materialize. `completed: false` records that the operator
// stopped early, so the window is a partial run.
export interface FinishExperimentInstanceAction {
  action: "finish_experiment_instance";
  request_id: string;
  graph_id: string;
  window_end_us?: number;
  completed?: boolean;
}

// Delete a board or a fork. A sealed instance needs force: true — deleting one
// destroys recorded history along with its artifacts.
// Fork an instance into an editable copy nested under the same experiment.
export interface ForkStreamGraphAction {
  action: "fork_stream_graph";
  request_id: string;
  source_graph_id: string;
  label?: string;
}

// Review = paced from the original device_ts_us deltas (watch it back like a
// video). Recompute = unpaced, for re-running a fork's pipeline or training, where
// nobody is watching frames go by.
export interface StartInstanceReplayAction {
  action: "start_instance_replay";
  request_id: string;
  graph_id: string;
  mode: "review" | "recompute";
  speed?: number;
}

export interface StopInstanceReplayAction {
  action: "stop_instance_replay";
  request_id: string;
  replay_id: string;
}

export interface VerifyExperimentInstanceAction {
  action: "verify_experiment_instance";
  request_id: string;
  graph_id: string;
}

export interface DeleteStreamGraphAction {
  action: "delete_stream_graph";
  request_id: string;
  graph_id: string;
  force?: boolean;
}

// Ask a device to run a command on its EXECUTION_COMMAND topic. The reply is a
// DeviceCommandResultMessage carrying what the device said on its log channel.
export interface SendDeviceCommandAction {
  action: "send_device_command";
  request_id: string;
  stream_id: string;
  command: string;
  target?: "sensor" | "server";
  args?: Record<string, unknown>;
  timeout_ms?: number;
}

// Start / stop the device_health push. The rig's status topics are LOGGING_LOG,
// which the stream list does not carry, so this is the only way to reach them.
export interface SubscribeDeviceHealthAction {
  action: "subscribe_device_health";
  interval_ms?: number;
  quiet_after_ms?: number;
}

export interface UnsubscribeDeviceHealthAction {
  action: "unsubscribe_device_health";
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
  | ListWorkspacesAction
  | SaveWorkspaceAction
  | DeleteWorkspaceAction
  | ListExperimentsAction
  | SaveExperimentAction
  | DeleteExperimentAction
  | StartExperimentInstanceAction
  | FinishExperimentInstanceAction
  | ForkStreamGraphAction
  | StartInstanceReplayAction
  | StopInstanceReplayAction
  | VerifyExperimentInstanceAction
  | DeleteStreamGraphAction
  | ListProfilesAction
  | SaveProfileAction
  | DeleteProfileAction
  | SendDeviceCommandAction
  | SubscribeDeviceHealthAction
  | UnsubscribeDeviceHealthAction;
