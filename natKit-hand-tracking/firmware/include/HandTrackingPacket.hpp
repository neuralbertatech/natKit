#pragma once

#include <cstddef>
#include <cstdint>

namespace nat::hand_tracking {

constexpr uint8_t kProtocolVersion = 1;

enum class PayloadType : uint8_t {
  RawSample = 0x01,
  FeatureVector = 0x02,
  GestureOutput = 0x03,
  Heartbeat = 0xF0,
  Diagnostic = 0xFF,
};

enum class GestureId : uint8_t {
  Rest = 0,
  Open = 1,
  Fist = 2,
  Pinch = 3,
  Point = 4,
};

#pragma pack(push, 1)

struct PacketHeaderV1 {
  uint8_t version;
  uint8_t payload_type;
  uint16_t header_bytes;
  uint32_t sequence;
  uint64_t timestamp_us;
  uint16_t payload_bytes;
  uint16_t flags;
};

struct RawSamplePayloadV1 {
  int16_t emg_ch0;
  int16_t emg_ch1;
  int16_t emg_ch2;

  float quat_w;
  float quat_x;
  float quat_y;
  float quat_z;

  float accel_x;
  float accel_y;
  float accel_z;

  float gyro_x;
  float gyro_y;
  float gyro_z;

  uint8_t imu_accuracy;
  uint8_t emg_saturation_mask;
  uint8_t reserved[2];
};

struct GestureOutputPayloadV1 {
  uint8_t gesture_id;
  float confidence;
  uint16_t model_version;
  uint8_t reserved;
};

#pragma pack(pop)

static_assert(sizeof(PacketHeaderV1) == 20, "PacketHeaderV1 must be 20 bytes");
static_assert(sizeof(RawSamplePayloadV1) == 50, "RawSamplePayloadV1 must be 50 bytes");
static_assert(sizeof(GestureOutputPayloadV1) == 8, "GestureOutputPayloadV1 must be 8 bytes");

inline PacketHeaderV1 make_header(PayloadType payload_type, uint32_t sequence,
                                  uint64_t timestamp_us,
                                  uint16_t payload_bytes) {
  PacketHeaderV1 header{};
  header.version = kProtocolVersion;
  header.payload_type = static_cast<uint8_t>(payload_type);
  header.header_bytes = static_cast<uint16_t>(sizeof(PacketHeaderV1));
  header.sequence = sequence;
  header.timestamp_us = timestamp_us;
  header.payload_bytes = payload_bytes;
  header.flags = 0;
  return header;
}

}  // namespace nat::hand_tracking
