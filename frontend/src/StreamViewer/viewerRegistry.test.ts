import { describe, it, expect } from "vitest";
import type { DataSchemaDescriptor, SchemaFieldDescriptor } from "./types";
import {
  chooseViewerRenderer,
  isClassificationFrameLabels,
  isMarkerStreamSchema,
  MARKER_SCHEMA_NAME,
} from "./viewerRegistry";

function field(
  id: string,
  type: SchemaFieldDescriptor["type"],
  extra: Partial<SchemaFieldDescriptor> = {},
): SchemaFieldDescriptor {
  return { id, label: id, type, optional: false, ...extra };
}

function obj(
  id: string,
  fields: Record<string, SchemaFieldDescriptor>,
): SchemaFieldDescriptor {
  return field(id, "object", { fields });
}

// A canonical numeric channel frame descriptor (device_id/seq_no/… + channels[].samples[]).
function channelFrameDescriptor(): DataSchemaDescriptor {
  return {
    schema_name: "SomeSensorFrameV1",
    descriptor_version: 1,
    root: obj("root", {
      device_id: field("device_id", "string"),
      seq_no: field("seq_no", "uint64"),
      device_ts_us: field("device_ts_us", "uint64"),
      sample_rate_hz: field("sample_rate_hz", "uint32"),
      channels: field("channels", "array", {
        items: obj("channel", {
          samples: field("samples", "array", {
            items: field("sample", "float32"),
          }),
        }),
      }),
    }),
  };
}

function museDescriptor(): DataSchemaDescriptor {
  const band = () =>
    field("band", "array", { items: field("v", "float32") });
  return {
    schema_name: "SomeEegSchema",
    descriptor_version: 1,
    root: obj("root", {
      eeg: obj("eeg", {
        tp9: band(),
        af7: band(),
        af8: band(),
        tp10: band(),
      }),
    }),
  };
}

// An IMU-shaped record — NOT a channel frame, NOT muse.
function imuDescriptor(): DataSchemaDescriptor {
  return {
    schema_name: "SomeImuSchema",
    descriptor_version: 1,
    root: obj("root", {
      accel: obj("accel", {
        x: field("x", "float64"),
        y: field("y", "float64"),
        z: field("z", "float64"),
      }),
    }),
  };
}

describe("chooseViewerRenderer", () => {
  it("routes a muse-shaped descriptor to the muse renderer", () => {
    expect(chooseViewerRenderer(museDescriptor())).toBe("muse");
  });

  it("routes a multi-sample channel frame to the waveform renderer", () => {
    expect(
      chooseViewerRenderer(channelFrameDescriptor(), {
        n_channels: 8,
        samples_per_channel: 64,
      }),
    ).toBe("channel_frame");
  });

  it("routes a per-window feature vector to the feature-vector renderer", () => {
    expect(
      chooseViewerRenderer(channelFrameDescriptor(), {
        n_channels: 27,
        samples_per_channel: 1,
      }),
    ).toBe("feature_vector");
  });

  it("routes a classifier output frame to the classification renderer", () => {
    expect(
      chooseViewerRenderer(channelFrameDescriptor(), {
        n_channels: 4,
        samples_per_channel: 1,
        channel_labels: [
          "predicted_class",
          "confidence.rest",
          "confidence.flex",
          "confidence.extend",
        ],
      }),
    ).toBe("classification");
  });

  it("defaults a channel frame with no shape hint to the waveform renderer", () => {
    // Without a live frame we cannot tell waveform from feature vector, so we
    // default to the waveform renderer (safe for the common case).
    expect(chooseViewerRenderer(channelFrameDescriptor())).toBe("channel_frame");
  });

  it("falls back to the inspector for an unknown non-channel-frame descriptor", () => {
    expect(chooseViewerRenderer(imuDescriptor())).toBe("inspector");
  });

  it("falls back to the inspector for an undefined descriptor", () => {
    expect(chooseViewerRenderer(undefined)).toBe("inspector");
  });

  it("selects the imu renderer for the NatImu* schemas (descriptor or hint)", () => {
    expect(
      chooseViewerRenderer({
        ...imuDescriptor(),
        schema_name: "NatImuBulkDataSchema",
      }),
    ).toBe("imu");
    expect(
      chooseViewerRenderer(undefined, undefined, "NatImuDataSchema"),
    ).toBe("imu");
  });
});

describe("marker renderer selection", () => {
  it("picks the marker renderer from a MarkerEventV1 descriptor schema", () => {
    const descriptor = {
      schema_name: MARKER_SCHEMA_NAME,
      fields: {},
    } as unknown as DataSchemaDescriptor;
    expect(chooseViewerRenderer(descriptor)).toBe("marker");
  });

  it("picks the marker renderer from an explicit schema-name hint", () => {
    expect(chooseViewerRenderer(undefined, undefined, MARKER_SCHEMA_NAME)).toBe(
      "marker",
    );
  });

  it("does not pick marker for a non-marker schema hint", () => {
    expect(
      chooseViewerRenderer(undefined, undefined, "ExgPillEmgDataSchemaV1"),
    ).toBe("inspector");
  });

  it("isMarkerStreamSchema only matches MarkerEventV1", () => {
    expect(isMarkerStreamSchema(MARKER_SCHEMA_NAME)).toBe(true);
    expect(isMarkerStreamSchema("SomethingElse")).toBe(false);
    expect(isMarkerStreamSchema(undefined)).toBe(false);
  });
});

describe("isClassificationFrameLabels", () => {
  it("detects the predicted_class + confidence.* label shape", () => {
    expect(
      isClassificationFrameLabels([
        "predicted_class",
        "confidence.a",
        "confidence.b",
      ]),
    ).toBe(true);
  });

  it("rejects ordinary channel labels", () => {
    expect(isClassificationFrameLabels(["ch0", "ch1", "ch2"])).toBe(false);
  });

  it("rejects undefined / too-short label lists", () => {
    expect(isClassificationFrameLabels(undefined)).toBe(false);
    expect(isClassificationFrameLabels(["predicted_class"])).toBe(false);
  });
});
