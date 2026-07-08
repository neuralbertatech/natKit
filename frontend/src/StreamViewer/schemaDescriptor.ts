import type {
  DataSchemaDescriptor,
  SchemaFieldDescriptor,
  SchemaFieldValueType,
  TransformCapability,
  TransformInputMapping,
} from "./types";

export interface DescriptorLeafOption {
  path: string;
  label: string;
  type: SchemaFieldDescriptor["type"];
  description?: string;
  unit?: string;
  optional: boolean;
}

const MAX_ARRAY_ITEMS_TO_EXPAND = 32;

function joinPath(prefix: string, segment: string): string {
  return prefix ? `${prefix}.${segment}` : segment;
}

function makeLeafLabel(prefix: string, field: SchemaFieldDescriptor): string {
  return prefix ? `${prefix} ${field.label}` : field.label;
}

function normalizeArrayPreviewItems(value: unknown): unknown[] | null {
  return Array.isArray(value) ? value : null;
}

function expandFieldLeaves(
  field: SchemaFieldDescriptor,
  path: string,
  labelPrefix: string,
  recordValue: unknown,
  leaves: DescriptorLeafOption[],
): void {
  if (field.type === "object") {
    const childFields = Object.values(field.fields ?? {});
    for (const childField of childFields) {
      const childValue =
        recordValue !== null &&
        typeof recordValue === "object" &&
        !Array.isArray(recordValue)
          ? (recordValue as Record<string, unknown>)[childField.id]
          : undefined;
      expandFieldLeaves(
        childField,
        joinPath(path, childField.id),
        makeLeafLabel(labelPrefix, childField),
        childValue,
        leaves,
      );
    }
    return;
  }

  if (field.type === "array") {
    const itemField = field.items;
    if (!itemField) {
      return;
    }

    const arrayItems = normalizeArrayPreviewItems(recordValue);
    if (!arrayItems || arrayItems.length === 0) {
      expandFieldLeaves(
        itemField,
        joinPath(path, "{index}"),
        `${labelPrefix} Item`,
        undefined,
        leaves,
      );
      return;
    }

    const itemCount = Math.min(arrayItems.length, MAX_ARRAY_ITEMS_TO_EXPAND);
    for (let index = 0; index < itemCount; index += 1) {
      expandFieldLeaves(
        itemField,
        joinPath(path, String(index)),
        `${labelPrefix} ${index + 1}`,
        arrayItems[index],
        leaves,
      );
    }
    return;
  }

  leaves.push({
    path,
    label: labelPrefix,
    type: field.type,
    description: field.description,
    unit: field.unit,
    optional: field.optional,
  });
}

export function getDescriptorLeafOptions(
  descriptor: DataSchemaDescriptor,
  recordValue?: unknown,
): DescriptorLeafOption[] {
  const leaves: DescriptorLeafOption[] = [];
  expandFieldLeaves(descriptor.root, "", "", recordValue, leaves);
  return leaves;
}

export function getValueAtSchemaPath(
  recordValue: unknown,
  path: string,
): unknown {
  if (!path) {
    return recordValue;
  }

  let currentValue: unknown = recordValue;
  for (const segment of path.split(".")) {
    if (currentValue === null || currentValue === undefined) {
      return undefined;
    }

    if (/^\d+$/.test(segment)) {
      if (!Array.isArray(currentValue)) {
        return undefined;
      }
      currentValue = currentValue[Number(segment)];
      continue;
    }

    if (Array.isArray(currentValue) || typeof currentValue !== "object") {
      return undefined;
    }
    currentValue = (currentValue as Record<string, unknown>)[segment];
  }

  return currentValue;
}

export function formatSchemaValue(value: unknown): string {
  if (value === undefined) {
    return "Unavailable";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  if (
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  return JSON.stringify(value);
}

function findFieldByPath(
  root: SchemaFieldDescriptor,
  path: string,
): SchemaFieldDescriptor | undefined {
  const segments = path.split(".");
  let current: SchemaFieldDescriptor | undefined = root;
  for (const segment of segments) {
    if (!current) {
      return undefined;
    }

    if (/^\d+$/.test(segment)) {
      if (current.type !== "array" || !current.items) {
        return undefined;
      }
      current = current.items;
      continue;
    }

    if (current.type !== "object") {
      return undefined;
    }
    current = current.fields?.[segment];
  }
  return current;
}

export function descriptorSupportsNumericChannelFrames(
  descriptor: DataSchemaDescriptor | undefined,
): boolean {
  if (!descriptor) {
    return false;
  }

  const expectOneOf = (
    path: string,
    allowedTypes: SchemaFieldValueType[],
  ): boolean => {
    const field = findFieldByPath(descriptor.root, path);
    return !!field && allowedTypes.includes(field.type);
  };

  return (
    expectOneOf("device_id", ["string"]) &&
    expectOneOf("seq_no", ["uint64"]) &&
    expectOneOf("device_ts_us", ["uint64"]) &&
    expectOneOf("sample_rate_hz", ["uint32"]) &&
    expectOneOf("channels", ["array"]) &&
    expectOneOf("channels.0.samples", ["array"]) &&
    expectOneOf("channels.0.samples.0", [
      "int16",
      "uint32",
      "uint64",
      "float32",
      "float64",
    ])
  );
}

// Descriptor-shape probe for a Muse-like EEG record: a multi-band EEG object
// with the four canonical channels. Identifies the renderer by structure, NOT
// by schema_name (Phase 2 of the visual-programming rework), so any record with
// this shape gets the MuseViewer.
export function descriptorLooksLikeMuse(
  descriptor: DataSchemaDescriptor | undefined,
): boolean {
  if (!descriptor) {
    return false;
  }
  const hasArray = (path: string): boolean => {
    const field = findFieldByPath(descriptor.root, path);
    return !!field && field.type === "array";
  };
  return (
    hasArray("eeg.tp9") &&
    hasArray("eeg.af7") &&
    hasArray("eeg.af8") &&
    hasArray("eeg.tp10")
  );
}

function descriptorSupportsExplicitInputMapping(
  descriptor: DataSchemaDescriptor,
  mapping: TransformInputMapping,
): boolean {
  if (mapping.mode !== "explicit_channel_paths") {
    return false;
  }
  if (mapping.schema_name && descriptor.schema_name !== mapping.schema_name) {
    return false;
  }

  const expectPath = (
    path: string | undefined,
    allowedTypes: SchemaFieldValueType[],
  ): boolean => {
    if (!path) {
      return true;
    }
    const field = findFieldByPath(descriptor.root, path);
    return !!field && allowedTypes.includes(field.type);
  };

  const channels = mapping.channels ?? [];
  if (channels.length === 0) {
    return false;
  }

  if (
    !expectPath(mapping.seq_no_path, ["uint32", "uint64"]) ||
    !expectPath(mapping.device_ts_us_path, ["uint64"]) ||
    !(
      mapping.sample_rate_hz_value !== undefined ||
      expectPath(mapping.sample_rate_hz_path, [
        "uint32",
        "uint64",
        "float32",
        "float64",
      ])
    )
  ) {
    return false;
  }

  return channels.every((channel) => {
    const arrayField = findFieldByPath(descriptor.root, channel.sample_array_path);
    const sampleField = findFieldByPath(
      descriptor.root,
      `${channel.sample_array_path}.0`,
    );
    return (
      !!arrayField &&
      arrayField.type === "array" &&
      !!sampleField &&
      ["int16", "uint32", "uint64", "float32", "float64"].includes(
        sampleField.type,
      )
    );
  });
}

export function descriptorSupportsAnyTransformCapability(
  descriptor: DataSchemaDescriptor | undefined,
  capabilities: TransformCapability[],
): boolean {
  if (!descriptor) {
    return false;
  }

  return capabilities.some((capability) =>
    capability.input_mappings.some((mapping) => {
      if (mapping.mode === "canonical_channel_frame") {
        return descriptorSupportsNumericChannelFrames(descriptor);
      }
      return descriptorSupportsExplicitInputMapping(descriptor, mapping);
    }),
  );
}

export function findCompatibleTransformInputMappingId(
  descriptor: DataSchemaDescriptor | undefined,
  capability: TransformCapability | undefined,
): string | undefined {
  if (!descriptor || !capability) {
    return undefined;
  }

  for (const mapping of capability.input_mappings) {
    if (
      mapping.mode === "canonical_channel_frame" &&
      descriptorSupportsNumericChannelFrames(descriptor)
    ) {
      return mapping.id;
    }
    if (
      mapping.mode === "explicit_channel_paths" &&
      descriptorSupportsExplicitInputMapping(descriptor, mapping)
    ) {
      return mapping.id;
    }
  }

  return undefined;
}
