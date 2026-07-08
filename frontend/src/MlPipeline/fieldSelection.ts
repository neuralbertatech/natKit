import type {
  DataSchemaDescriptor,
  SchemaFieldDescriptor,
} from "../StreamViewer/types";

// Minimal, sensor-agnostic view of a canonical numeric channel frame. Any
// record whose descriptor matches the channel-frame contract exposes these
// fields (EMG, IMU-as-frame, a new sensor, a transform output, …). Field
// selection walks these — it must never depend on a specific sensor's message
// type. Structurally satisfied by EmgDataMessage and friends.
export interface ChannelFramePreview {
  n_channels: number;
  samples_per_channel: number;
  sample_rate_hz: number;
  channel_labels: string[];
}

export interface ChannelFieldOption {
  path: string;
  label: string;
  description: string;
}

function getField(
  field: SchemaFieldDescriptor | undefined,
  key: string,
): SchemaFieldDescriptor | undefined {
  return field?.fields?.[key];
}

export function getChannelFieldOptions(
  descriptor: DataSchemaDescriptor | undefined,
  preview: ChannelFramePreview | null,
): ChannelFieldOption[] {
  if (!descriptor || !preview) {
    return [];
  }

  const channelsField = getField(descriptor.root, "channels");
  const channelItemField = channelsField?.items;
  const samplesField = getField(channelItemField, "samples");
  if (
    channelsField?.type !== "array" ||
    channelItemField?.type !== "object" ||
    samplesField?.type !== "array"
  ) {
    return [];
  }

  return Array.from({ length: preview.n_channels }, (_, index) => {
    const label = preview.channel_labels[index]?.trim() || `Channel ${index + 1}`;
    return {
      path: `channels.${index}.samples`,
      label,
      description: `${preview.samples_per_channel} samples per frame at ${preview.sample_rate_hz} Hz`,
    };
  });
}

// Backward-compatible aliases (EMG-specific names retired in Phase 0).
export type EmgChannelFieldOption = ChannelFieldOption;
export const getEmgChannelFieldOptions = getChannelFieldOptions;
