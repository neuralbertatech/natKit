// Viewer registry (Phase 2 of the visual-programming rework).
//
// A viewer is chosen from a stream's DESCRIPTOR CAPABILITY plus the live frame
// shape — never from a sensor/schema name. This replaces the old
// "imu" | "muse" | "emg" ladder. Both the StreamViewer page and the graph
// editor's viewer nodes select their renderer through `chooseViewerRenderer`,
// so adding a sensor never means adding a viewer branch.

import type { DataSchemaDescriptor } from "./types";
import {
  descriptorLooksLikeMuse,
  descriptorSupportsNumericChannelFrames,
} from "./schemaDescriptor";

export type ViewerRendererKind =
  | "muse"
  | "imu"
  | "channel_frame"
  | "feature_vector"
  | "classification"
  | "marker"
  | "inspector";

// The schema name of the marker stream. A stream whose schema is MarkerEventV1
// gets the marker renderer (Phase 2). This is intentionally schema-name driven
// — markers are a first-class schema, not a channel-frame capability.
export const MARKER_SCHEMA_NAME = "MarkerEventV1";

// IMU streams carry a fixed accel/gyro/quaternion record rather than the generic
// channels[].samples[] channel-frame shape, so they get a dedicated renderer
// (scrolling accel/gyro/quat trace). Identified by schema name — same exception
// the marker renderer already makes — because there is no channel-frame
// capability to probe.
export const IMU_SCHEMA_NAMES = ["NatImuBulkDataSchema", "NatImuDataSchema"];

export function isImuStreamSchema(schemaName: string | undefined): boolean {
  return schemaName !== undefined && IMU_SCHEMA_NAMES.includes(schemaName);
}

// A marker stream is identified by its schema name (from the descriptor or a
// topic/message schema hint), not a channel-frame capability.
export function isMarkerStreamSchema(schemaName: string | undefined): boolean {
  return schemaName === MARKER_SCHEMA_NAME;
}

// The runtime shape of the latest frame on a channel-frame stream. The
// descriptor says a stream IS a channel frame; only a live frame reveals how
// many channels/samples it carries and its channel labels — which distinguish
// a rolling waveform from a per-window feature vector or a classifier readout.
export interface FrameShapeHint {
  n_channels?: number;
  samples_per_channel?: number;
  channel_labels?: string[];
}

// An lda_classify (or any classifier) output frame is a channel frame whose
// first channel is the predicted class index and whose remaining channels are
// per-class confidences ("confidence.<label>"). Detected by label shape, not
// schema name.
export function isClassificationFrameLabels(
  channelLabels: string[] | undefined,
): boolean {
  if (!channelLabels || channelLabels.length < 2) {
    return false;
  }
  return (
    channelLabels[0] === "predicted_class" &&
    channelLabels
      .slice(1)
      .every((label) => label.startsWith("confidence."))
  );
}

export function chooseViewerRenderer(
  descriptor: DataSchemaDescriptor | undefined,
  shape?: FrameShapeHint,
  schemaNameHint?: string,
): ViewerRendererKind {
  // Markers are schema-identified (MarkerEventV1) — check before the
  // channel-frame capability probes. The schema can come from the descriptor or
  // an explicit hint (a marker stream may have no channel-frame descriptor).
  if (
    isMarkerStreamSchema(descriptor?.schema_name) ||
    isMarkerStreamSchema(schemaNameHint)
  ) {
    return "marker";
  }

  if (descriptorLooksLikeMuse(descriptor)) {
    return "muse";
  }

  // IMU is schema-identified (accel/gyro/quaternion record), before the
  // channel-frame probes — it is not a channels[].samples[] frame.
  if (
    isImuStreamSchema(descriptor?.schema_name) ||
    isImuStreamSchema(schemaNameHint)
  ) {
    return "imu";
  }

  if (descriptorSupportsNumericChannelFrames(descriptor)) {
    if (isClassificationFrameLabels(shape?.channel_labels)) {
      return "classification";
    }
    // A per-window feature vector emits one scalar per channel (no waveform to
    // trace); anything with real time-series samples is a waveform.
    if (
      shape &&
      shape.samples_per_channel !== undefined &&
      shape.samples_per_channel <= 1 &&
      (shape.n_channels ?? 0) > 1
    ) {
      return "feature_vector";
    }
    return "channel_frame";
  }

  // IMU and any other self-describing record fall back to the generic
  // descriptor inspector until a capability-matched renderer exists.
  return "inspector";
}
