import { describe, it, expect } from "vitest";
import {
  channelKindFromTopics,
  dataTopicOfChannel,
  markerTopicOfChannel,
  type OutputChannelTopic,
} from "./types";

const data: OutputChannelTopic = { type: "Data", id: "7", schema: "NatSignalFrameDataSchemaV1" };
const marker: OutputChannelTopic = { type: "Marker", id: "7", schema: "MarkerEventV1" };

describe("channelKindFromTopics (topic-aware channels, Part A)", () => {
  it("returns empty for no topics", () => {
    expect(channelKindFromTopics(undefined)).toBe("empty");
    expect(channelKindFromTopics([])).toBe("empty");
  });

  it("classifies a single DATA topic as data", () => {
    expect(channelKindFromTopics([data])).toBe("data");
  });

  it("classifies a single MARKER topic as markers", () => {
    expect(channelKindFromTopics([marker])).toBe("markers");
  });

  it("classifies DATA + MARKER as a stream", () => {
    expect(channelKindFromTopics([data, marker])).toBe("stream");
    // order-independent
    expect(channelKindFromTopics([marker, data])).toBe("stream");
  });
});

describe("topic accessors", () => {
  it("finds the DATA topic of a stream channel", () => {
    expect(dataTopicOfChannel([data, marker])).toEqual(data);
    expect(dataTopicOfChannel([marker])).toBeUndefined();
  });

  it("finds the MARKER topic of a stream channel", () => {
    expect(markerTopicOfChannel([data, marker])).toEqual(marker);
    expect(markerTopicOfChannel([data])).toBeUndefined();
  });
});
