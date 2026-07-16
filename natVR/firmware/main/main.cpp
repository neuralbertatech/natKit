#include <array>
#include <atomic>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "cJSON.h"
#include "esp_adc/adc_continuous.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "networking.hpp"

#if __has_include("DevConfig.hpp")
#include "DevConfig.hpp"
#else
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define MQTT_BROKER_HOST "192.168.1.100"
#define MQTT_BROKER_PORT 1883
#define NATVR_EMG_DEVICE_ID "emg01"
#define NATVR_STATUS_DEVICE_ID "emg01-fw"
#define NATVR_ADC_CHANNEL_COUNT 1
#define NATVR_NTP_SERVER "pool.ntp.org"
#endif

#if !CONFIG_IDF_TARGET_ESP32 && !CONFIG_IDF_TARGET_ESP32C3
#error "natVR firmware currently supports classic ESP32 and ESP32-C3 targets only"
#endif

// Transport selection: 0 = WiFi/MQTT (default), 1 = USB-serial backup.
// Build the serial-backup image with -DNATVR_TRANSPORT_SERIAL=1 (or define it in
// DevConfig.hpp). In serial mode the firmware writes the *same* newline-delimited
// JSON frames to the USB serial console instead of publishing over MQTT, and WiFi
// / NTP / MQTT are never brought up. A host shim (natvr-serial-bridge) reads the
// lines and republishes them verbatim onto the standard MQTT topics, so the
// bridge -> Kafka path is byte-identical to the WiFi transport.
#ifndef NATVR_TRANSPORT_SERIAL
#define NATVR_TRANSPORT_SERIAL 0
#endif

namespace {

constexpr char kTag[] = "natvr-emg-fw";

#if CONFIG_IDF_TARGET_ESP32
constexpr uint32_t kMaxSupportedChannels = 4;
#elif CONFIG_IDF_TARGET_ESP32C3
constexpr uint32_t kMaxSupportedChannels = 3;
#endif
constexpr uint32_t kChannelCount = NATVR_ADC_CHANNEL_COUNT;
constexpr uint32_t kSampleRateHzPerChannel = 1000;
constexpr uint32_t kSamplesPerChannelPerFrame = 50;
constexpr uint32_t kFrameQueueDepth = 40;
constexpr uint32_t kMaxFrameAgeUs = 2'000'000;
constexpr uint32_t kHeartbeatIntervalMs = 1000;
constexpr uint32_t kMqttPayloadBufferSize = 12288;
constexpr size_t kAdcReadBufferBytes = 512;

constexpr adc_atten_t kAdcAtten = ADC_ATTEN_DB_12;
constexpr adc_bitwidth_t kAdcBitWidth = ADC_BITWIDTH_12;
static_assert(kChannelCount >= 1 && kChannelCount <= kMaxSupportedChannels,
              "NATVR_ADC_CHANNEL_COUNT exceeds the selected target's supported range");

struct ChannelConfig {
  adc_unit_t unit;
  adc_channel_t channel;
  const char* label;
};

#if CONFIG_IDF_TARGET_ESP32
constexpr ChannelConfig kChannels[kMaxSupportedChannels] = {
    {ADC_UNIT_1, ADC_CHANNEL_6, "flexor_a"},    // GPIO34 / A2
    {ADC_UNIT_1, ADC_CHANNEL_3, "flexor_b"},    // GPIO39 / A3
    {ADC_UNIT_1, ADC_CHANNEL_0, "extensor_a"},  // GPIO36 / A4
    {ADC_UNIT_1, ADC_CHANNEL_1, "extensor_b"},  // GPIO37 / D37
};
constexpr char kTargetName[] = "ESP32";
constexpr char kAdcOrderDescription[] =
    "ADC1 channel order: [0]=A2(GPIO34) [1]=A3(GPIO39) [2]=A4(GPIO36) [3]=D37(GPIO37)";
#elif CONFIG_IDF_TARGET_ESP32C3
constexpr ChannelConfig kChannels[kMaxSupportedChannels] = {
    {ADC_UNIT_1, ADC_CHANNEL_4, "flexor_a"},  // GPIO4
    {ADC_UNIT_1, ADC_CHANNEL_3, "flexor_b"},  // GPIO3
    {ADC_UNIT_1, ADC_CHANNEL_1, "extensor_a"},  // GPIO1
};
constexpr char kTargetName[] = "ESP32-C3";
constexpr char kAdcOrderDescription[] =
    "ADC1 channel order: [0]=GPIO4 [1]=GPIO3 [2]=GPIO1";
#endif

struct EmgFrameBuffer {
  uint32_t seq_no;
  uint64_t device_ts_us;
  int16_t channels[kChannelCount][kSamplesPerChannelPerFrame];
};

struct DeviceCounters {
  std::atomic<uint32_t> last_seq_no{0};
  std::atomic<uint64_t> frames_captured{0};
  std::atomic<uint64_t> frames_published{0};
  std::atomic<uint64_t> frames_dropped_queue{0};
  std::atomic<uint64_t> frames_dropped_stale{0};
  std::atomic<uint64_t> mqtt_publish_failures{0};
};

struct FrameBuilder {
  bool active = false;
  uint32_t sample_index = 0;
  uint32_t next_channel_idx = 0;
  uint64_t first_sample_ts_us = 0;
  int16_t channels[kChannelCount][kSamplesPerChannelPerFrame]{};
};

QueueHandle_t g_frame_queue = nullptr;
adc_continuous_handle_t g_adc_handle = nullptr;
DeviceCounters g_counters;

char g_mqtt_topic[128];
char g_status_topic[128];
char g_client_id[64];

int channel_to_index(adc_unit_t unit, adc_channel_t channel) {
  for (size_t idx = 0; idx < kChannelCount; ++idx) {
    if (kChannels[idx].unit == unit && kChannels[idx].channel == channel) {
      return static_cast<int>(idx);
    }
  }
  return -1;
}

int16_t to_signed_sample(uint32_t raw) {
  constexpr int32_t kMidpoint = 2048;
  const int32_t centered = static_cast<int32_t>(raw & 0x0FFFU) - kMidpoint;
  return static_cast<int16_t>(centered);
}

bool serialize_frame_json(const EmgFrameBuffer& frame, char** out_json) {
  cJSON* root = cJSON_CreateObject();
  if (root == nullptr) {
    return false;
  }

  cJSON_AddStringToObject(root, "schema_version", "exg.pill.emg.data.v1");
  cJSON_AddStringToObject(root, "device_id", NATVR_EMG_DEVICE_ID);
  cJSON_AddNumberToObject(root, "seq_no", static_cast<double>(frame.seq_no));
  cJSON_AddNumberToObject(root, "device_ts_us",
                          static_cast<double>(frame.device_ts_us));
  cJSON_AddNumberToObject(root, "n_channels", kChannelCount);
  cJSON_AddNumberToObject(root, "samples_per_channel",
                          kSamplesPerChannelPerFrame);
  cJSON_AddNumberToObject(root, "sample_rate_hz", kSampleRateHzPerChannel);

  cJSON* labels = cJSON_AddArrayToObject(root, "channel_labels");
  for (size_t idx = 0; idx < kChannelCount; ++idx) {
    cJSON_AddItemToArray(labels, cJSON_CreateString(kChannels[idx].label));
  }

  cJSON* payload = cJSON_AddArrayToObject(root, "payload");
  for (size_t channel_idx = 0; channel_idx < kChannelCount; ++channel_idx) {
    cJSON* channel = cJSON_CreateArray();
    for (size_t sample_idx = 0; sample_idx < kSamplesPerChannelPerFrame;
         ++sample_idx) {
      cJSON_AddItemToArray(
          channel,
          cJSON_CreateNumber(frame.channels[channel_idx][sample_idx]));
    }
    cJSON_AddItemToArray(payload, channel);
  }

  *out_json = cJSON_PrintUnformatted(root);
  cJSON_Delete(root);
  return *out_json != nullptr;
}

#if NATVR_TRANSPORT_SERIAL
// Writes one newline-delimited JSON frame to the USB serial console. puts() emits
// the string plus a trailing '\n' in a single locked stdio call, so frames from
// the publish and heartbeat tasks never interleave mid-line, and the host shim
// (natvr-serial-bridge) can read one JSON object per line.
void emit_serial_line(const char* json) {
  puts(json);
  fflush(stdout);
}
#endif

bool serialize_status_json(char** out_json) {
  cJSON* root = cJSON_CreateObject();
  if (root == nullptr) {
    return false;
  }

  cJSON_AddStringToObject(root, "schema_version", "device.firmware.status.v1");
  cJSON_AddStringToObject(root, "device_id", NATVR_EMG_DEVICE_ID);
  cJSON_AddStringToObject(root, "status_device_id", NATVR_STATUS_DEVICE_ID);
  cJSON_AddNumberToObject(root, "sample_rate_hz", kSampleRateHzPerChannel);
  cJSON_AddNumberToObject(root, "samples_per_channel",
                          kSamplesPerChannelPerFrame);
  cJSON_AddNumberToObject(root, "queue_depth",
                          static_cast<double>(uxQueueMessagesWaiting(g_frame_queue)));
  cJSON_AddNumberToObject(root, "queue_capacity", kFrameQueueDepth);
  cJSON_AddNumberToObject(root, "frames_captured",
                          static_cast<double>(g_counters.frames_captured.load()));
  cJSON_AddNumberToObject(root, "frames_published",
                          static_cast<double>(g_counters.frames_published.load()));
  cJSON_AddNumberToObject(
      root, "frames_dropped_queue",
      static_cast<double>(g_counters.frames_dropped_queue.load()));
  cJSON_AddNumberToObject(
      root, "frames_dropped_stale",
      static_cast<double>(g_counters.frames_dropped_stale.load()));
  cJSON_AddNumberToObject(
      root, "mqtt_publish_failures",
      static_cast<double>(g_counters.mqtt_publish_failures.load()));
  cJSON_AddNumberToObject(root, "last_seq_no",
                          static_cast<double>(g_counters.last_seq_no.load()));
  cJSON_AddBoolToObject(root, "wifi_connected",
                        networking_wifi_is_connected());
  cJSON_AddBoolToObject(root, "mqtt_connected",
                        networking_mqtt_is_connected());
  cJSON_AddBoolToObject(root, "ntp_synced", networking_ntp_is_synced());
  cJSON_AddNumberToObject(root, "rssi_dbm",
                          static_cast<double>(networking_wifi_rssi_dbm()));
  cJSON_AddNumberToObject(
      root, "uptime_ms",
      static_cast<double>(esp_timer_get_time() / 1000ULL));
  cJSON_AddNumberToObject(
      root, "emitted_at_us",
      static_cast<double>(networking_get_time_us()));

  *out_json = cJSON_PrintUnformatted(root);
  cJSON_Delete(root);
  return *out_json != nullptr;
}

void publish_task(void* /*param*/) {
  while (true) {
#if !NATVR_TRANSPORT_SERIAL
    if (!networking_mqtt_is_connected()) {
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
#endif

    EmgFrameBuffer frame{};
    if (xQueuePeek(g_frame_queue, &frame, pdMS_TO_TICKS(100)) != pdTRUE) {
      continue;
    }

    const uint64_t age_us = networking_get_time_us() - frame.device_ts_us;
    if (age_us > kMaxFrameAgeUs) {
      (void)xQueueReceive(g_frame_queue, &frame, 0);
      g_counters.frames_dropped_stale.fetch_add(1);
      continue;
    }

    char* json = nullptr;
    if (!serialize_frame_json(frame, &json)) {
      ESP_LOGE(kTag, "failed to serialize frame seq=%" PRIu32, frame.seq_no);
      (void)xQueueReceive(g_frame_queue, &frame, 0);
      g_counters.mqtt_publish_failures.fetch_add(1);
      continue;
    }

#if NATVR_TRANSPORT_SERIAL
    emit_serial_line(json);
    cJSON_free(json);
#else
    const int result = networking_mqtt_publish(
        g_mqtt_topic, reinterpret_cast<const uint8_t*>(json), std::strlen(json),
        0, false);
    cJSON_free(json);

    if (result != 0) {
      g_counters.mqtt_publish_failures.fetch_add(1);
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }
#endif

    (void)xQueueReceive(g_frame_queue, &frame, 0);
    g_counters.frames_published.fetch_add(1);
  }
}

void heartbeat_task(void* /*param*/) {
  while (true) {
    vTaskDelay(pdMS_TO_TICKS(kHeartbeatIntervalMs));
#if !NATVR_TRANSPORT_SERIAL
    if (!networking_mqtt_is_connected()) {
      continue;
    }
#endif

    char* json = nullptr;
    if (!serialize_status_json(&json)) {
      ESP_LOGE(kTag, "failed to serialize status");
      continue;
    }

#if NATVR_TRANSPORT_SERIAL
    emit_serial_line(json);
    cJSON_free(json);
#else
    const int result = networking_mqtt_publish(
        g_status_topic, reinterpret_cast<const uint8_t*>(json),
        std::strlen(json), 0, false);
    cJSON_free(json);
    if (result != 0) {
      g_counters.mqtt_publish_failures.fetch_add(1);
    }
#endif
  }
}

void push_completed_frame(FrameBuilder* builder) {
  EmgFrameBuffer frame{};
  frame.seq_no = g_counters.last_seq_no.fetch_add(1) + 1;
  frame.device_ts_us = builder->first_sample_ts_us;
  for (size_t channel_idx = 0; channel_idx < kChannelCount; ++channel_idx) {
    std::memcpy(frame.channels[channel_idx], builder->channels[channel_idx],
                sizeof(frame.channels[channel_idx]));
  }

  if (xQueueSendToBack(g_frame_queue, &frame, 0) != pdTRUE) {
    EmgFrameBuffer dropped{};
    (void)xQueueReceive(g_frame_queue, &dropped, 0);
    if (xQueueSendToBack(g_frame_queue, &frame, 0) != pdTRUE) {
      g_counters.frames_dropped_queue.fetch_add(1);
      return;
    }
    g_counters.frames_dropped_queue.fetch_add(1);
  }

  g_counters.frames_captured.fetch_add(1);
  builder->active = false;
  builder->sample_index = 0;
  builder->next_channel_idx = 0;
  builder->first_sample_ts_us = 0;
}

void sampling_task(void* /*param*/) {
  FrameBuilder builder{};
  uint8_t result[kAdcReadBufferBytes];
  adc_continuous_data_t parsed_data[kAdcReadBufferBytes / SOC_ADC_DIGI_RESULT_BYTES];

  while (true) {
    uint32_t bytes_read = 0;
    const esp_err_t err = adc_continuous_read(
        g_adc_handle, result, sizeof(result), &bytes_read, pdMS_TO_TICKS(1000));
    if (err == ESP_ERR_TIMEOUT) {
      continue;
    }
    ESP_ERROR_CHECK(err);

    uint32_t sample_count = 0;
    ESP_ERROR_CHECK(adc_continuous_parse_data(g_adc_handle, result, bytes_read,
                                              parsed_data, &sample_count));

    for (uint32_t sample_idx = 0; sample_idx < sample_count; ++sample_idx) {
      const auto& sample = parsed_data[sample_idx];
      if (!sample.valid) {
        continue;
      }

      const int channel_idx = channel_to_index(
          static_cast<adc_unit_t>(sample.unit),
          static_cast<adc_channel_t>(sample.channel));
      if (channel_idx < 0) {
        continue;
      }

      if (!builder.active) {
        if (channel_idx != 0) {
          continue;
        }
        builder.active = true;
        builder.sample_index = 0;
        builder.next_channel_idx = 0;
        builder.first_sample_ts_us = networking_get_time_us();
      }

      if (static_cast<uint32_t>(channel_idx) != builder.next_channel_idx) {
        builder.active = false;
        builder.sample_index = 0;
        builder.next_channel_idx = 0;
        if (channel_idx != 0) {
          continue;
        }
        builder.active = true;
        builder.first_sample_ts_us = networking_get_time_us();
      }

      builder.channels[channel_idx][builder.sample_index] =
          to_signed_sample(sample.raw_data);

      if (channel_idx == static_cast<int>(kChannelCount - 1)) {
        builder.next_channel_idx = 0;
        ++builder.sample_index;
        if (builder.sample_index >= kSamplesPerChannelPerFrame) {
          push_completed_frame(&builder);
        }
      } else {
        ++builder.next_channel_idx;
      }
    }
  }
}

void configure_topics() {
  std::snprintf(g_client_id, sizeof(g_client_id), "natvr-emg-%s",
                NATVR_EMG_DEVICE_ID);
  std::snprintf(g_mqtt_topic, sizeof(g_mqtt_topic),
                "natKit/sending/emg/raw/emg.raw.%s", NATVR_EMG_DEVICE_ID);
  std::snprintf(g_status_topic, sizeof(g_status_topic),
                "natKit/sending/emg/status/device.status.%s",
                NATVR_STATUS_DEVICE_ID);
}

void init_adc() {
  adc_continuous_handle_cfg_t handle_cfg{};
  handle_cfg.max_store_buf_size = 4096;
  handle_cfg.conv_frame_size = 256;
  ESP_ERROR_CHECK(adc_continuous_new_handle(&handle_cfg, &g_adc_handle));

  std::array<adc_digi_pattern_config_t, kChannelCount> patterns{};
  for (size_t idx = 0; idx < kChannelCount; ++idx) {
    patterns[idx].atten = kAdcAtten;
    patterns[idx].channel = kChannels[idx].channel;
    patterns[idx].unit = kChannels[idx].unit;
    patterns[idx].bit_width = kAdcBitWidth;
  }

  adc_continuous_config_t adc_config{};
  adc_config.sample_freq_hz = kSampleRateHzPerChannel * kChannelCount;
  adc_config.conv_mode = ADC_CONV_SINGLE_UNIT_1;
  adc_config.format = ADC_DIGI_OUTPUT_FORMAT_TYPE1;
  adc_config.pattern_num = kChannelCount;
  adc_config.adc_pattern = patterns.data();

  ESP_ERROR_CHECK(adc_continuous_config(g_adc_handle, &adc_config));
  ESP_ERROR_CHECK(adc_continuous_start(g_adc_handle));
}

}  // namespace

extern "C" void app_main(void) {
  ESP_LOGI(kTag, "natVR EMG firmware starting");
  configure_topics();

#if NATVR_TRANSPORT_SERIAL
  // Serial backup transport: no WiFi / NTP / MQTT. Quiet the logs so the JSON
  // frame stream on the USB serial console stays clean for the host shim
  // (error-level diagnostics still print; the shim skips any non-JSON line).
  // Timestamps come from the local monotonic clock (gettimeofday, unsynced) —
  // fine for a single-device serial capture where alignment is intra-session.
  esp_log_level_set("*", ESP_LOG_ERROR);
#else
  ESP_ERROR_CHECK(networking_init() == 0 ? ESP_OK : ESP_FAIL);
  ESP_ERROR_CHECK(networking_wifi_connect(WIFI_SSID, WIFI_PASSWORD, 30000) == 0
                      ? ESP_OK
                      : ESP_FAIL);
  ESP_ERROR_CHECK(networking_ntp_init(NATVR_NTP_SERVER) == 0 ? ESP_OK
                                                             : ESP_FAIL);
  if (networking_ntp_wait_sync(60000) != 0) {
    ESP_LOGW(kTag, "NTP sync timed out; continuing with local clock");
  }

  ESP_ERROR_CHECK(networking_mqtt_init(MQTT_BROKER_HOST, MQTT_BROKER_PORT,
                                       g_client_id, kMqttPayloadBufferSize) == 0
                      ? ESP_OK
                      : ESP_FAIL);
  if (networking_mqtt_connect(30000) != 0) {
    ESP_LOGW(kTag, "MQTT connect timed out; background reconnect will continue");
  }
#endif

  g_frame_queue = xQueueCreate(kFrameQueueDepth, sizeof(EmgFrameBuffer));
  if (g_frame_queue == nullptr) {
    ESP_LOGE(kTag, "failed to create frame queue");
    return;
  }

  init_adc();

  xTaskCreate(sampling_task, "natvr_sample", 8192, nullptr, 8, nullptr);
  xTaskCreate(publish_task, "natvr_publish", 8192, nullptr, 6, nullptr);
  xTaskCreate(heartbeat_task, "natvr_status", 6144, nullptr, 4, nullptr);

  ESP_LOGI(kTag, "sampling %u channels at %u Hz/channel -> topic %s",
           static_cast<unsigned>(kChannelCount),
           static_cast<unsigned>(kSampleRateHzPerChannel), g_mqtt_topic);
  ESP_LOGI(kTag, "target=%s", kTargetName);
  ESP_LOGI(kTag, "%s", kAdcOrderDescription);
}
