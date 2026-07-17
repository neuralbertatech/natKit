#include <atomic>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <inttypes.h>

#include "HandTrackingPacket.hpp"
#include "Bno08xProvider.hpp"
#include "TransportPublisher.hpp"

#include "esp_check.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"

namespace {

constexpr char kTag[] = "natkit-hand";

constexpr uint32_t kDefaultSampleRateHz = 200;
constexpr uint32_t kMaxSampleRateHz = 1000;
constexpr uint32_t kImuTareDurationMs = 2000;
constexpr uint32_t kEmgBaselineDurationMs = 3000;
constexpr uint32_t kPublishRateHz = 50;
constexpr TickType_t kPublishPeriodTicks = pdMS_TO_TICKS(1000 / kPublishRateHz);
constexpr uint32_t kCalibrationBlobVersion = 1;
constexpr auto kTransportType =
    nat::hand_tracking::transport::TransportType::LogOnly;

constexpr int kAdcMax = 4095;
constexpr int kAdcMidpoint = kAdcMax / 2;
constexpr uint8_t kCalibrationFlagImuTare = 0x01;
constexpr uint8_t kCalibrationFlagEmgBaseline = 0x02;
constexpr char kNvsNamespace[] = "natkit_ht";
constexpr char kNvsCalibrationKey[] = "calib_v1";

// ADC1 channels for classic ESP32:
// GPIO36 -> ADC1_CHANNEL_0, GPIO39 -> ADC1_CHANNEL_3, GPIO34 -> ADC1_CHANNEL_6
constexpr adc_channel_t kEmgChannel0 = ADC_CHANNEL_0;
constexpr adc_channel_t kEmgChannel1 = ADC_CHANNEL_3;
constexpr adc_channel_t kEmgChannel2 = ADC_CHANNEL_6;

std::atomic<uint32_t> g_sequence{0};
std::atomic<bool> g_has_sample{false};
std::atomic<bool> g_imu_ready{false};
std::atomic<bool> g_nvs_ready{false};
nat::hand_tracking::RawSamplePayloadV1 g_latest_sample{};
SemaphoreHandle_t g_sample_lock = nullptr;
adc_oneshot_unit_handle_t g_adc_handle = nullptr;
nat::hand_tracking::transport::ITransportPublisher* g_transport = nullptr;

struct __attribute__((packed)) CalibrationBlobV1 {
  uint32_t version;
  uint8_t flags;
  uint8_t reserved[3];
  float imu_tare_inverse[4];
  float emg_baseline_mean[3];
  float emg_baseline_std[3];
  uint64_t calibration_timestamp_us;
};

esp_err_t init_nvs_storage() {
  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES ||
      err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    err = nvs_flash_init();
  }
  return err;
}

esp_err_t load_calibration_blob(CalibrationBlobV1* out_blob) {
  if (out_blob == nullptr) {
    return ESP_ERR_INVALID_ARG;
  }

  nvs_handle_t nvs_handle = 0;
  esp_err_t err = nvs_open(kNvsNamespace, NVS_READONLY, &nvs_handle);
  if (err != ESP_OK) {
    return err;
  }

  size_t blob_size = sizeof(CalibrationBlobV1);
  err = nvs_get_blob(nvs_handle, kNvsCalibrationKey, out_blob, &blob_size);
  nvs_close(nvs_handle);
  if (err != ESP_OK) {
    return err;
  }
  if (blob_size != sizeof(CalibrationBlobV1)) {
    return ESP_ERR_INVALID_SIZE;
  }
  if (out_blob->version != kCalibrationBlobVersion) {
    return ESP_ERR_INVALID_VERSION;
  }
  return ESP_OK;
}

esp_err_t save_calibration_blob(const CalibrationBlobV1& blob) {
  nvs_handle_t nvs_handle = 0;
  esp_err_t err = nvs_open(kNvsNamespace, NVS_READWRITE, &nvs_handle);
  if (err != ESP_OK) {
    return err;
  }

  err = nvs_set_blob(nvs_handle, kNvsCalibrationKey, &blob, sizeof(blob));
  if (err == ESP_OK) {
    err = nvs_commit(nvs_handle);
  }
  nvs_close(nvs_handle);
  return err;
}

struct Quaternion {
  float w;
  float x;
  float y;
  float z;
};

Quaternion normalize_quaternion(Quaternion q) {
  const float norm =
      std::sqrt((q.w * q.w) + (q.x * q.x) + (q.y * q.y) + (q.z * q.z));
  if (norm <= 1.0e-6f) {
    return Quaternion{1.0f, 0.0f, 0.0f, 0.0f};
  }
  const float inv = 1.0f / norm;
  q.w *= inv;
  q.x *= inv;
  q.y *= inv;
  q.z *= inv;
  return q;
}

Quaternion quaternion_conjugate(Quaternion q) {
  q.x = -q.x;
  q.y = -q.y;
  q.z = -q.z;
  return q;
}

Quaternion quaternion_multiply(const Quaternion& lhs, const Quaternion& rhs) {
  Quaternion out{};
  out.w = (lhs.w * rhs.w) - (lhs.x * rhs.x) - (lhs.y * rhs.y) - (lhs.z * rhs.z);
  out.x = (lhs.w * rhs.x) + (lhs.x * rhs.w) + (lhs.y * rhs.z) - (lhs.z * rhs.y);
  out.y = (lhs.w * rhs.y) - (lhs.x * rhs.z) + (lhs.y * rhs.w) + (lhs.z * rhs.x);
  out.z = (lhs.w * rhs.z) + (lhs.x * rhs.y) - (lhs.y * rhs.x) + (lhs.z * rhs.w);
  return out;
}

uint32_t sample_count_for_duration(uint32_t sample_rate_hz, uint32_t duration_ms) {
  uint32_t effective_rate_hz = sample_rate_hz;
  if (effective_rate_hz == 0U) {
    effective_rate_hz = kDefaultSampleRateHz;
  }
  if (effective_rate_hz > kMaxSampleRateHz) {
    effective_rate_hz = kMaxSampleRateHz;
  }
  const uint64_t count = (static_cast<uint64_t>(effective_rate_hz) * duration_ms) /
                         1000ULL;
  return static_cast<uint32_t>(count > 0U ? count : 1U);
}

uint32_t sanitize_sample_rate_hz(uint32_t sample_rate_hz) {
  if (sample_rate_hz == 0U) {
    return kDefaultSampleRateHz;
  }
  if (sample_rate_hz > kMaxSampleRateHz) {
    return kMaxSampleRateHz;
  }
  return sample_rate_hz;
}

TickType_t sample_period_ticks_for_rate(uint32_t sample_rate_hz) {
  const uint32_t effective_rate_hz = sanitize_sample_rate_hz(sample_rate_hz);
  uint32_t sample_period_ms = 1000U / effective_rate_hz;
  if (sample_period_ms == 0U) {
    sample_period_ms = 1U;
  }
  TickType_t sample_period_ticks = pdMS_TO_TICKS(sample_period_ms);
  if (sample_period_ticks == 0) {
    sample_period_ticks = 1;
  }
  return sample_period_ticks;
}

nat::hand_tracking::imu::Bno08xConfig make_imu_config() {
  auto config = nat::hand_tracking::imu::kDefaultConfig;
  // Edit these values for board-specific wiring/rates.
  config.report_interval_us = 20000;
  return config;
}

nat::hand_tracking::transport::TransportConfig make_transport_config() {
  auto config = nat::hand_tracking::transport::kDefaultTransportConfig;
  // Edit these values when using TransportType::MqttIp.
  config.mqtt.broker_uri = nullptr;
  config.mqtt.topic = "natKit/sending/hand-tracking/raw";
  config.mqtt.client_id = "natkit-hand-tracking";
  config.mqtt.qos = 0;
  config.mqtt.retain = false;

  // Edit these values when using TransportType::BleGatt.
  config.ble.device_name = "natKit Hand Tracking";
  config.ble.preferred_mtu = 185;
  config.ble.conn_interval_min_units = 12;  // 15 ms
  config.ble.conn_interval_max_units = 24;  // 30 ms
  config.ble.status_interval_ms = 1000;
  return config;
}

void sample_task(void* /*params*/) {
  uint32_t active_sample_rate_hz = kDefaultSampleRateHz;
  TickType_t sample_period_ticks = sample_period_ticks_for_rate(active_sample_rate_hz);
  bool imu_tare_valid = false;
  bool imu_tare_active = false;
  uint32_t imu_tare_target_samples = 0;
  uint32_t imu_tare_samples_remaining = 0;
  std::array<double, 4> imu_tare_sum{0.0, 0.0, 0.0, 0.0};
  Quaternion imu_tare_inverse{1.0f, 0.0f, 0.0f, 0.0f};

  bool emg_baseline_valid = false;
  bool emg_baseline_active = false;
  uint32_t emg_baseline_target_samples = 0;
  uint32_t emg_baseline_samples_remaining = 0;
  std::array<double, 3> emg_baseline_sum{0.0, 0.0, 0.0};
  std::array<double, 3> emg_baseline_sum_sq{0.0, 0.0, 0.0};
  std::array<float, 3> emg_baseline_mean{0.0f, 0.0f, 0.0f};
  std::array<float, 3> emg_baseline_std{0.0f, 0.0f, 0.0f};
  const auto sync_calibration_validity = [&]() {
    nat::hand_tracking::transport::set_calibration_validity(imu_tare_valid,
                                                            emg_baseline_valid);
  };
  sync_calibration_validity();

  if (g_nvs_ready.load(std::memory_order_acquire)) {
    CalibrationBlobV1 blob{};
    const esp_err_t load_err = load_calibration_blob(&blob);
    if (load_err == ESP_OK) {
      if ((blob.flags & kCalibrationFlagImuTare) != 0U) {
        imu_tare_inverse = normalize_quaternion(Quaternion{
            blob.imu_tare_inverse[0], blob.imu_tare_inverse[1],
            blob.imu_tare_inverse[2], blob.imu_tare_inverse[3]});
        imu_tare_valid = true;
      }
      if ((blob.flags & kCalibrationFlagEmgBaseline) != 0U) {
        for (size_t i = 0; i < emg_baseline_mean.size(); ++i) {
          emg_baseline_mean[i] = blob.emg_baseline_mean[i];
          emg_baseline_std[i] = blob.emg_baseline_std[i];
        }
        emg_baseline_valid = true;
      }

      ESP_LOGI(kTag, "loaded calibration flags=0x%02X ts=%" PRIu64 "us",
               static_cast<unsigned>(blob.flags), blob.calibration_timestamp_us);
      sync_calibration_validity();
    } else if (load_err == ESP_ERR_NVS_NOT_FOUND) {
      ESP_LOGI(kTag, "no persisted calibration found");
    } else {
      ESP_LOGW(kTag, "failed to load calibration: %s", esp_err_to_name(load_err));
    }
  }

  const auto persist_calibration = [&]() {
    if (!g_nvs_ready.load(std::memory_order_acquire)) {
      return;
    }

    CalibrationBlobV1 blob{};
    blob.version = kCalibrationBlobVersion;
    blob.flags = 0;
    blob.reserved[0] = 0;
    blob.reserved[1] = 0;
    blob.reserved[2] = 0;

    if (imu_tare_valid) {
      blob.flags = static_cast<uint8_t>(blob.flags | kCalibrationFlagImuTare);
      blob.imu_tare_inverse[0] = imu_tare_inverse.w;
      blob.imu_tare_inverse[1] = imu_tare_inverse.x;
      blob.imu_tare_inverse[2] = imu_tare_inverse.y;
      blob.imu_tare_inverse[3] = imu_tare_inverse.z;
    } else {
      blob.imu_tare_inverse[0] = 1.0f;
      blob.imu_tare_inverse[1] = 0.0f;
      blob.imu_tare_inverse[2] = 0.0f;
      blob.imu_tare_inverse[3] = 0.0f;
    }

    if (emg_baseline_valid) {
      blob.flags = static_cast<uint8_t>(blob.flags | kCalibrationFlagEmgBaseline);
      for (size_t i = 0; i < emg_baseline_mean.size(); ++i) {
        blob.emg_baseline_mean[i] = emg_baseline_mean[i];
        blob.emg_baseline_std[i] = emg_baseline_std[i];
      }
    } else {
      for (size_t i = 0; i < emg_baseline_mean.size(); ++i) {
        blob.emg_baseline_mean[i] = 0.0f;
        blob.emg_baseline_std[i] = 0.0f;
      }
    }

    blob.calibration_timestamp_us = static_cast<uint64_t>(esp_timer_get_time());

    const esp_err_t save_err = save_calibration_blob(blob);
    if (save_err != ESP_OK) {
      ESP_LOGW(kTag, "failed to persist calibration: %s", esp_err_to_name(save_err));
      return;
    }

    ESP_LOGI(kTag, "persisted calibration flags=0x%02X", blob.flags);
  };

  while (true) {
    const uint32_t requested_sample_rate_hz =
        nat::hand_tracking::transport::requested_sample_rate_hz();
    const uint32_t desired_sample_rate_hz =
        sanitize_sample_rate_hz(requested_sample_rate_hz);
    if (desired_sample_rate_hz != active_sample_rate_hz) {
      active_sample_rate_hz = desired_sample_rate_hz;
      sample_period_ticks = sample_period_ticks_for_rate(active_sample_rate_hz);
      ESP_LOGI(kTag, "sampling rate updated to %" PRIu32 " Hz", active_sample_rate_hz);
    }

    const bool imu_ready = g_imu_ready.load(std::memory_order_acquire);
    if (nat::hand_tracking::transport::consume_imu_tare_request()) {
      if (!imu_ready) {
        ESP_LOGW(kTag, "IMU tare command ignored: IMU not ready");
      } else {
        if (imu_tare_valid) {
          ESP_LOGI(kTag, "IMU tare recalibration requested");
        }
        imu_tare_valid = false;
        imu_tare_active = true;
        sync_calibration_validity();
        imu_tare_target_samples =
            sample_count_for_duration(active_sample_rate_hz, kImuTareDurationMs);
        imu_tare_samples_remaining = imu_tare_target_samples;
        imu_tare_sum = {0.0, 0.0, 0.0, 0.0};
        ESP_LOGI(kTag, "IMU tare started (%" PRIu32 " samples)",
                 imu_tare_target_samples);
      }
    }
    if (nat::hand_tracking::transport::consume_emg_baseline_request()) {
      if (emg_baseline_valid) {
        ESP_LOGI(kTag, "EMG baseline recalibration requested");
      }
      emg_baseline_valid = false;
      emg_baseline_active = true;
      sync_calibration_validity();
      emg_baseline_target_samples =
          sample_count_for_duration(active_sample_rate_hz, kEmgBaselineDurationMs);
      emg_baseline_samples_remaining = emg_baseline_target_samples;
      emg_baseline_sum = {0.0, 0.0, 0.0};
      emg_baseline_sum_sq = {0.0, 0.0, 0.0};
      ESP_LOGI(kTag, "EMG baseline started (%" PRIu32 " samples)",
               emg_baseline_target_samples);
    }

    if (imu_ready) {
      nat::hand_tracking::imu::service();
    }

    int emg0 = 0;
    int emg1 = 0;
    int emg2 = 0;
    adc_oneshot_read(g_adc_handle, kEmgChannel0, &emg0);
    adc_oneshot_read(g_adc_handle, kEmgChannel1, &emg1);
    adc_oneshot_read(g_adc_handle, kEmgChannel2, &emg2);

    nat::hand_tracking::RawSamplePayloadV1 sample{};
    sample.emg_ch0 = static_cast<int16_t>(emg0 - kAdcMidpoint);
    sample.emg_ch1 = static_cast<int16_t>(emg1 - kAdcMidpoint);
    sample.emg_ch2 = static_cast<int16_t>(emg2 - kAdcMidpoint);

    nat::hand_tracking::imu::ImuSample imu_sample{};
    const bool has_imu_sample =
        imu_ready && nat::hand_tracking::imu::get_latest(&imu_sample);
    if (has_imu_sample) {
      sample.quat_w = imu_sample.quat_w;
      sample.quat_x = imu_sample.quat_x;
      sample.quat_y = imu_sample.quat_y;
      sample.quat_z = imu_sample.quat_z;
      sample.accel_x = imu_sample.accel_x;
      sample.accel_y = imu_sample.accel_y;
      sample.accel_z = imu_sample.accel_z;
      sample.gyro_x = imu_sample.gyro_x;
      sample.gyro_y = imu_sample.gyro_y;
      sample.gyro_z = imu_sample.gyro_z;
      sample.imu_accuracy = imu_sample.accuracy;

      const Quaternion raw_quat{sample.quat_w, sample.quat_x, sample.quat_y,
                                sample.quat_z};
      if (imu_tare_active && (imu_tare_samples_remaining > 0U)) {
        imu_tare_sum[0] += raw_quat.w;
        imu_tare_sum[1] += raw_quat.x;
        imu_tare_sum[2] += raw_quat.y;
        imu_tare_sum[3] += raw_quat.z;
        --imu_tare_samples_remaining;

        if (imu_tare_samples_remaining == 0U && imu_tare_target_samples > 0U) {
          Quaternion avg{};
          const float inv_count =
              1.0f / static_cast<float>(imu_tare_target_samples);
          avg.w = static_cast<float>(imu_tare_sum[0]) * inv_count;
          avg.x = static_cast<float>(imu_tare_sum[1]) * inv_count;
          avg.y = static_cast<float>(imu_tare_sum[2]) * inv_count;
          avg.z = static_cast<float>(imu_tare_sum[3]) * inv_count;
          avg = normalize_quaternion(avg);
          imu_tare_inverse = quaternion_conjugate(avg);
          imu_tare_active = false;
          imu_tare_valid = true;
          sync_calibration_validity();
          ESP_LOGI(kTag, "IMU tare completed (inverse=%.5f, %.5f, %.5f, %.5f)",
                   imu_tare_inverse.w, imu_tare_inverse.x, imu_tare_inverse.y,
                   imu_tare_inverse.z);
          persist_calibration();
        }
      }

      if (imu_tare_valid) {
        const Quaternion corrected =
            normalize_quaternion(quaternion_multiply(imu_tare_inverse, raw_quat));
        sample.quat_w = corrected.w;
        sample.quat_x = corrected.x;
        sample.quat_y = corrected.y;
        sample.quat_z = corrected.z;
      }
    } else {
      sample.quat_w = 1.0f;
      sample.quat_x = 0.0f;
      sample.quat_y = 0.0f;
      sample.quat_z = 0.0f;
      sample.accel_x = 0.0f;
      sample.accel_y = 0.0f;
      sample.accel_z = 9.81f;
      sample.gyro_x = 0.0f;
      sample.gyro_y = 0.0f;
      sample.gyro_z = 0.0f;
      sample.imu_accuracy = 0;
    }

    if (emg_baseline_active && (emg_baseline_samples_remaining > 0U)) {
      const std::array<double, 3> emg_values{
          static_cast<double>(sample.emg_ch0), static_cast<double>(sample.emg_ch1),
          static_cast<double>(sample.emg_ch2)};
      for (size_t i = 0; i < emg_values.size(); ++i) {
        emg_baseline_sum[i] += emg_values[i];
        emg_baseline_sum_sq[i] += emg_values[i] * emg_values[i];
      }
      --emg_baseline_samples_remaining;

      if (emg_baseline_samples_remaining == 0U &&
          emg_baseline_target_samples > 0U) {
        const double inv_count =
            1.0 / static_cast<double>(emg_baseline_target_samples);
        for (size_t i = 0; i < emg_baseline_mean.size(); ++i) {
          const double mean = emg_baseline_sum[i] * inv_count;
          double variance = (emg_baseline_sum_sq[i] * inv_count) - (mean * mean);
          if (variance < 0.0) {
            variance = 0.0;
          }
          emg_baseline_mean[i] = static_cast<float>(mean);
          emg_baseline_std[i] = static_cast<float>(std::sqrt(variance));
        }

        emg_baseline_active = false;
        emg_baseline_valid = true;
        sync_calibration_validity();
        ESP_LOGI(kTag,
                 "EMG baseline completed mean=(%.2f, %.2f, %.2f) std=(%.2f, %.2f, %.2f)",
                 emg_baseline_mean[0], emg_baseline_mean[1], emg_baseline_mean[2],
                 emg_baseline_std[0], emg_baseline_std[1], emg_baseline_std[2]);
        persist_calibration();
      }
    }

    const bool emg0_sat = (emg0 <= 4) || (emg0 >= (kAdcMax - 4));
    const bool emg1_sat = (emg1 <= 4) || (emg1 >= (kAdcMax - 4));
    const bool emg2_sat = (emg2 <= 4) || (emg2 >= (kAdcMax - 4));
    sample.emg_saturation_mask = static_cast<uint8_t>(
        (emg0_sat ? 0x01 : 0x00) | (emg1_sat ? 0x02 : 0x00) |
        (emg2_sat ? 0x04 : 0x00));
    sample.reserved[0] = 0;
    sample.reserved[1] = 0;

    xSemaphoreTake(g_sample_lock, portMAX_DELAY);
    g_latest_sample = sample;
    xSemaphoreGive(g_sample_lock);
    g_has_sample.store(true, std::memory_order_release);

    vTaskDelay(sample_period_ticks);
  }
}

void publish_task(void* /*params*/) {
  auto active_transport_mode = nat::hand_tracking::transport::TransportMode::Raw;

  while (true) {
    if (g_transport != nullptr) {
      g_transport->loop();
    }

    const auto current_transport_mode = nat::hand_tracking::transport::transport_mode();
    if (current_transport_mode != active_transport_mode) {
      active_transport_mode = current_transport_mode;
      ESP_LOGI(kTag, "transport mode changed to %u (raw payload pipeline active)",
               static_cast<unsigned>(active_transport_mode));
    }

    if (!nat::hand_tracking::transport::stream_enabled()) {
      vTaskDelay(kPublishPeriodTicks);
      continue;
    }

    if (g_has_sample.load(std::memory_order_acquire)) {
      const uint32_t sequence = g_sequence.fetch_add(1, std::memory_order_relaxed);
      const uint64_t timestamp_us = static_cast<uint64_t>(esp_timer_get_time());

      nat::hand_tracking::RawSamplePayloadV1 sample{};
      xSemaphoreTake(g_sample_lock, portMAX_DELAY);
      sample = g_latest_sample;
      xSemaphoreGive(g_sample_lock);

      const auto header = nat::hand_tracking::make_header(
          nat::hand_tracking::PayloadType::RawSample, sequence, timestamp_us,
          static_cast<uint16_t>(sizeof(nat::hand_tracking::RawSamplePayloadV1)));

      uint8_t packet[sizeof(header) + sizeof(sample)];
      std::memcpy(packet, &header, sizeof(header));
      std::memcpy(packet + sizeof(header), &sample, sizeof(sample));

      if (g_transport != nullptr) {
        const esp_err_t publish_err = g_transport->publish(
            packet, sizeof(packet), sequence, timestamp_us);
        if (publish_err != ESP_OK && (sequence % 10U) == 0U) {
          ESP_LOGW(kTag, "transport publish failed: %s", esp_err_to_name(publish_err));
        }
      } else if ((sequence % 10U) == 0U) {
        ESP_LOGW(kTag, "no transport configured, dropping packet");
      }
    }

    vTaskDelay(kPublishPeriodTicks);
  }
}

esp_err_t init_adc() {
  adc_oneshot_unit_init_cfg_t unit_cfg{};
  unit_cfg.unit_id = ADC_UNIT_1;
  unit_cfg.ulp_mode = ADC_ULP_MODE_DISABLE;
  ESP_RETURN_ON_ERROR(adc_oneshot_new_unit(&unit_cfg, &g_adc_handle), kTag,
                      "adc_oneshot_new_unit failed");

  adc_oneshot_chan_cfg_t chan_cfg{};
  chan_cfg.atten = ADC_ATTEN_DB_12;
  chan_cfg.bitwidth = ADC_BITWIDTH_12;
  ESP_RETURN_ON_ERROR(adc_oneshot_config_channel(g_adc_handle, kEmgChannel0, &chan_cfg),
                      kTag, "config channel0 failed");
  ESP_RETURN_ON_ERROR(adc_oneshot_config_channel(g_adc_handle, kEmgChannel1, &chan_cfg),
                      kTag, "config channel1 failed");
  ESP_RETURN_ON_ERROR(adc_oneshot_config_channel(g_adc_handle, kEmgChannel2, &chan_cfg),
                      kTag, "config channel2 failed");
  return ESP_OK;
}

}  // namespace

extern "C" void app_main(void) {
  ESP_LOGI(kTag, "natKit hand tracking firmware bootstrap");
  ESP_LOGI(kTag, "protocol v%u | header=%u | raw=%u",
           static_cast<unsigned>(nat::hand_tracking::kProtocolVersion),
           static_cast<unsigned>(sizeof(nat::hand_tracking::PacketHeaderV1)),
           static_cast<unsigned>(sizeof(nat::hand_tracking::RawSamplePayloadV1)));

  const esp_err_t nvs_err = init_nvs_storage();
  if (nvs_err == ESP_OK) {
    g_nvs_ready.store(true, std::memory_order_release);
  } else {
    ESP_LOGW(kTag, "NVS init failed, calibration persistence disabled: %s",
             esp_err_to_name(nvs_err));
  }

  g_sample_lock = xSemaphoreCreateMutex();
  if (g_sample_lock == nullptr) {
    ESP_LOGE(kTag, "failed to create sample mutex");
    return;
  }

  if (init_adc() != ESP_OK) {
    ESP_LOGE(kTag, "ADC initialization failed");
    return;
  }

  const auto imu_config = make_imu_config();
  if (nat::hand_tracking::imu::init(imu_config) == ESP_OK) {
    g_imu_ready.store(true, std::memory_order_release);
    ESP_LOGI(kTag,
             "BNO086 SPI IMU initialized (SCK=%d MISO=%d MOSI=%d CS=%d INT=%d RST=%d interval_us=%" PRIu32 ")",
             imu_config.pin_spi_sck, imu_config.pin_spi_miso,
             imu_config.pin_spi_mosi, imu_config.pin_spi_cs,
             imu_config.pin_imu_int, imu_config.pin_imu_reset,
             imu_config.report_interval_us);
  } else {
    ESP_LOGW(kTag, "BNO086 SPI init failed, using placeholder IMU values");
  }

  const auto transport_config = make_transport_config();
  g_transport = nat::hand_tracking::transport::create_publisher(kTransportType,
                                                                transport_config);
  if (g_transport == nullptr) {
    ESP_LOGE(kTag, "failed to create transport publisher");
    return;
  }

  ESP_LOGI(kTag, "transport selected: %s",
           nat::hand_tracking::transport::to_string(kTransportType));
  esp_err_t transport_connect_err = g_transport->connect();
  if (transport_connect_err != ESP_OK) {
    ESP_LOGW(kTag, "transport connect failed: %s", esp_err_to_name(transport_connect_err));
    if (kTransportType != nat::hand_tracking::transport::TransportType::LogOnly) {
      g_transport = nat::hand_tracking::transport::create_publisher(
          nat::hand_tracking::transport::TransportType::LogOnly);
      if (g_transport != nullptr) {
        (void)g_transport->connect();
      }
    }
  }

  xTaskCreate(sample_task, "SampleTask", 4096, nullptr, 5, nullptr);
  xTaskCreate(publish_task, "PublishTask", 4096, nullptr, 4, nullptr);
}
