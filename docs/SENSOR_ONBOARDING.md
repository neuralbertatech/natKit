# Sensor Onboarding

_How to add a new sensor to natKit without touching the stream-viewer dispatch,
the frame formatter, or any TypeScript union._

As of the visual-programming rework (phases 0–3) a sensor is **data**: a schema +
a self-describing descriptor. If the descriptor matches the canonical numeric
channel-frame contract, the sensor plots, is transform-compatible (filters,
windows, features, classifiers), and can feed the graph editor — all with no
per-sensor code in the backend dispatch or the frontend.

## The canonical channel-frame contract

A record is treated as a numeric channel frame when its descriptor exposes:

| Field | Type |
|-------|------|
| `device_id` | string |
| `seq_no` | uint64 |
| `device_ts_us` | uint64 |
| `sample_rate_hz` | uint32 |
| `channels` | array of objects |
| `channels[].label` | string (optional) |
| `channels[].samples` | array of numeric (`int16`/`uint32`/`uint64`/`float32`/`float64`) |

This is exactly what `NatSignalFrameDataSchemaV1` already publishes, and what the
backend's `tryNormalizeNumericChannelFrame(record, descriptor)` reads generically.

## Checklist

1. **Publish the data.** Bridge the sensor onto Kafka. The simplest path is to
   publish `NatSignalFrameDataSchemaV1` frames (one channel per sensor axis, e.g.
   a 3-axis force plate → 3 channels labelled `fx`/`fy`/`fz`). No new schema class
   is needed in that case — you are done after step 4.
2. **(Only if you need a distinct schema)** Register a schema class + its
   `DataSchemaDescriptor` in the core registry
   (`nat::core::DataSchemaDescriptorRegistry`). Make the descriptor fields match
   the contract table above. No edit to `StreamViewerWebSocket.cpp`'s dispatch or
   formatters is required — the generic fallback
   (`formatNormalizedFrameAsJson`) projects any contract-matching record to one
   `frame` wire message.
3. **Nothing on the frontend.** The `frame` message is buffered as a channel
   frame; `chooseViewerRenderer(descriptor, shape)` (`viewerRegistry.ts`) picks a
   viewer from descriptor capability + live shape:
   - multi-sample frame → waveform (`ChannelFrameViewer`)
   - one sample per channel, many channels → `FeatureVectorViewer`
   - `predicted_class` + `confidence.*` labels → `ClassificationViewer`
   - otherwise → the generic `SchemaDescriptorInspector`
   The node palette and transform compatibility come from `list_node_catalog`
   and the descriptor probe `descriptorSupportsNumericChannelFrames`.
4. **Verify.** The stream appears as a source; drop it on a board (or open it in
   the Stream Viewer); it plots; a band-pass / RMS / feature transform accepts it
   because its descriptor satisfies the `canonical_channel_frame` input mapping.

## Sensors whose fields don't match the contract

If a sensor's record uses different field names/layout (e.g. Muse EEG, which
nests channels under `eeg.tp9`/`af7`/…), it needs an **alternate input mapping**
that projects its fields onto the channel-frame contract. Today those mappings
live in `getAlternateTransformInputMappings()` as a static C++ list (Muse is the
one built in). Making that list registrable/config-driven — so a non-canonical
sensor is mapped by data rather than code — is the remaining Phase-3 item and is
tracked separately. Until then, the zero-code path is: **publish the canonical
channel-frame layout.**
