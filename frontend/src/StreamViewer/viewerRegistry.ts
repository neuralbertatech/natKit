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
  | "channel_frame"
  | "feature_vector"
  | "classification"
  | "inspector";

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
): ViewerRendererKind {
  if (descriptorLooksLikeMuse(descriptor)) {
    return "muse";
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
