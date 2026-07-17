#pragma once

#include <cstddef>
#include <cstdint>

#include "esp_err.h"

namespace nat::hand_tracking::transport {

enum class TransportType : uint8_t {
  LogOnly = 0,
  MqttIp = 1,
  BleGatt = 2,
};

enum class TransportMode : uint8_t {
  Raw = 0,
  Features = 1,
  Gestures = 2,
};

struct MqttTransportConfig {
  const char* broker_uri;
  const char* topic;
  const char* client_id;
  int qos;
  bool retain;
};

struct BleTransportConfig {
  const char* device_name;
  uint16_t preferred_mtu;
  uint16_t conn_interval_min_units;
  uint16_t conn_interval_max_units;
  uint32_t status_interval_ms;
};

struct TransportConfig {
  MqttTransportConfig mqtt;
  BleTransportConfig ble;
};

constexpr TransportConfig kDefaultTransportConfig{
    .mqtt =
        {
            .broker_uri = nullptr,
            .topic = "natKit/sending/hand-tracking/raw",
            .client_id = "natkit-hand-tracking",
            .qos = 0,
            .retain = false,
        },
    .ble =
        {
            .device_name = "natKit Hand Tracking",
            .preferred_mtu = 185,
            .conn_interval_min_units = 12,  // 15 ms
            .conn_interval_max_units = 24,  // 30 ms
            .status_interval_ms = 1000,
        },
};

class ITransportPublisher {
 public:
  virtual ~ITransportPublisher() = default;

  virtual esp_err_t connect() = 0;
  virtual bool is_connected() const = 0;
  virtual esp_err_t publish(const uint8_t* packet, size_t packet_len,
                            uint32_t sequence, uint64_t timestamp_us) = 0;
  virtual void loop() = 0;
  virtual TransportType type() const = 0;
};

const char* to_string(TransportType type);
ITransportPublisher* create_publisher(TransportType type);
ITransportPublisher* create_publisher(TransportType type,
                                      const TransportConfig& config);

void set_stream_enabled(bool enabled);
bool stream_enabled();

void set_requested_sample_rate_hz(uint32_t hz);
uint32_t requested_sample_rate_hz();

void set_transport_mode(TransportMode mode);
TransportMode transport_mode();

void request_imu_tare();
bool consume_imu_tare_request();

void request_emg_baseline();
bool consume_emg_baseline_request();

void set_calibration_validity(bool imu_tare_valid, bool emg_baseline_valid);
bool imu_tare_calibration_valid();
bool emg_baseline_calibration_valid();

}  // namespace nat::hand_tracking::transport
