#include "TransportPublisher.hpp"

#include <algorithm>
#include <atomic>
#include <cstring>
#include <inttypes.h>
#include <new>

#include "esp_log.h"
#include "esp_timer.h"
#include "mqtt_client.h"

#if CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED

extern "C" {
#include "host/ble_att.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "host/ble_hs.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "nvs_flash.h"
#include "os/os_mbuf.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
void ble_store_config_init(void);
}

#endif  // CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED

namespace nat::hand_tracking::transport {
namespace {

constexpr char kTag[] = "natkit-transport";

std::atomic<bool> g_runtime_stream_enabled{true};
std::atomic<uint32_t> g_runtime_sample_rate_hz{0};
std::atomic<uint8_t> g_runtime_transport_mode{
    static_cast<uint8_t>(TransportMode::Raw)};
std::atomic<bool> g_runtime_imu_tare_pending{false};
std::atomic<bool> g_runtime_emg_baseline_pending{false};
std::atomic<bool> g_runtime_imu_tare_valid{false};
std::atomic<bool> g_runtime_emg_baseline_valid{false};

class LogTransportPublisher final : public ITransportPublisher {
 public:
  esp_err_t connect() override {
    connected_ = true;
    ESP_LOGI(kTag, "Transport connected: %s", to_string(type()));
    return ESP_OK;
  }

  bool is_connected() const override { return connected_; }

  esp_err_t publish(const uint8_t* packet, size_t packet_len, uint32_t sequence,
                    uint64_t timestamp_us) override {
    if (!connected_) {
      return ESP_ERR_INVALID_STATE;
    }
    if (packet == nullptr || packet_len == 0U) {
      return ESP_ERR_INVALID_ARG;
    }

    if ((sequence % 10U) == 0U) {
      ESP_LOGI(kTag, "LOG transport seq=%" PRIu32 " ts=%" PRIu64
                     "us bytes=%u",
               sequence, timestamp_us, static_cast<unsigned>(packet_len));
    }
    return ESP_OK;
  }

  void loop() override {}

  TransportType type() const override { return TransportType::LogOnly; }

 private:
  bool connected_ = false;
};

class UnsupportedTransportPublisher final : public ITransportPublisher {
 public:
  explicit UnsupportedTransportPublisher(TransportType type) : type_(type) {}

  esp_err_t connect() override {
    ESP_LOGW(kTag, "Transport not implemented yet: %s", to_string(type_));
    return ESP_ERR_NOT_SUPPORTED;
  }

  bool is_connected() const override { return false; }

  esp_err_t publish(const uint8_t* /*packet*/, size_t /*packet_len*/,
                    uint32_t /*sequence*/, uint64_t /*timestamp_us*/) override {
    return ESP_ERR_NOT_SUPPORTED;
  }

  void loop() override {}

  TransportType type() const override { return type_; }

 private:
  TransportType type_;
};

class MqttTransportPublisher final : public ITransportPublisher {
 public:
  explicit MqttTransportPublisher(MqttTransportConfig config) : config_(config) {}
  ~MqttTransportPublisher() override {
    if (client_ != nullptr) {
      (void)esp_mqtt_client_stop(client_);
      (void)esp_mqtt_client_destroy(client_);
      client_ = nullptr;
    }
  }

  esp_err_t connect() override {
    if (config_.broker_uri == nullptr || config_.topic == nullptr) {
      ESP_LOGW(kTag, "MQTT config missing broker URI or topic");
      return ESP_ERR_INVALID_ARG;
    }

    if (client_ != nullptr) {
      return ESP_OK;
    }

    esp_mqtt_client_config_t mqtt_cfg{};
    mqtt_cfg.broker.address.uri = config_.broker_uri;
    mqtt_cfg.credentials.client_id = config_.client_id;
    mqtt_cfg.network.disable_auto_reconnect = false;

    client_ = esp_mqtt_client_init(&mqtt_cfg);
    if (client_ == nullptr) {
      ESP_LOGE(kTag, "esp_mqtt_client_init failed");
      return ESP_FAIL;
    }

    esp_err_t err = esp_mqtt_client_register_event(
        client_, MQTT_EVENT_ANY, &MqttTransportPublisher::on_event_static, this);
    if (err != ESP_OK) {
      ESP_LOGE(kTag, "esp_mqtt_client_register_event failed: %s",
               esp_err_to_name(err));
      return err;
    }

    err = esp_mqtt_client_start(client_);
    if (err != ESP_OK) {
      ESP_LOGE(kTag, "esp_mqtt_client_start failed: %s", esp_err_to_name(err));
      return err;
    }

    ESP_LOGI(kTag, "MQTT transport starting uri=%s topic=%s", config_.broker_uri,
             config_.topic);
    return ESP_OK;
  }

  bool is_connected() const override {
    return connected_.load(std::memory_order_acquire);
  }

  esp_err_t publish(const uint8_t* packet, size_t packet_len, uint32_t sequence,
                    uint64_t timestamp_us) override {
    if (packet == nullptr || packet_len == 0U) {
      return ESP_ERR_INVALID_ARG;
    }
    if (client_ == nullptr) {
      return ESP_ERR_INVALID_STATE;
    }
    if (!is_connected()) {
      return ESP_ERR_INVALID_STATE;
    }

    const int msg_id = esp_mqtt_client_publish(
        client_, config_.topic, reinterpret_cast<const char*>(packet),
        static_cast<int>(packet_len), config_.qos, config_.retain ? 1 : 0);
    if (msg_id < 0) {
      return ESP_FAIL;
    }

    if ((sequence % 10U) == 0U) {
      ESP_LOGI(kTag,
               "MQTT transport seq=%" PRIu32 " ts=%" PRIu64 "us bytes=%u msg_id=%d",
               sequence, timestamp_us, static_cast<unsigned>(packet_len), msg_id);
    }
    return ESP_OK;
  }

  void loop() override {}

  TransportType type() const override { return TransportType::MqttIp; }

  void on_event(esp_mqtt_event_handle_t event) {
    if (event == nullptr) {
      return;
    }

    switch (event->event_id) {
      case MQTT_EVENT_CONNECTED:
        connected_.store(true, std::memory_order_release);
        ESP_LOGI(kTag, "MQTT connected");
        break;

      case MQTT_EVENT_DISCONNECTED:
        connected_.store(false, std::memory_order_release);
        ESP_LOGW(kTag, "MQTT disconnected");
        break;

      case MQTT_EVENT_ERROR:
        connected_.store(false, std::memory_order_release);
        ESP_LOGW(kTag, "MQTT error event");
        break;

      default:
        break;
    }
  }

  static void on_event_static(void* handler_args, esp_event_base_t /*base*/,
                              int32_t /*event_id*/, void* event_data) {
    auto* self = static_cast<MqttTransportPublisher*>(handler_args);
    if (self == nullptr) {
      return;
    }
    self->on_event(static_cast<esp_mqtt_event_handle_t>(event_data));
  }

 private:
  MqttTransportConfig config_{};
  esp_mqtt_client_handle_t client_ = nullptr;
  std::atomic<bool> connected_{false};
};

#if CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED

class BleGattTransportPublisher;
BleGattTransportPublisher* g_ble_instance = nullptr;

constexpr uint8_t kStateIdle = 0;
constexpr uint8_t kStateCalibrating = 1;
constexpr uint8_t kStateStreaming = 2;
constexpr uint8_t kStateError = 3;
constexpr uint8_t kStatusStateMask = 0x0F;
constexpr uint8_t kStatusImuCalibrationValid = 0x10;
constexpr uint8_t kStatusEmgCalibrationValid = 0x20;
constexpr uint16_t kDefaultAttMtu = 23;
constexpr uint8_t kStatusBatteryUnknown = 0xFF;

struct __attribute__((packed)) BleControlCommandV1 {
  uint8_t opcode;
  uint8_t arg0;
  uint16_t arg1;
  uint32_t arg2;
};

struct __attribute__((packed)) BleStatusPayloadV1 {
  uint8_t state;
  uint8_t battery_pct;
  uint8_t link_quality;
  uint32_t dropped_packets;
  uint32_t uptime_ms;
};

const ble_uuid128_t kNatKitServiceUuid =
    BLE_UUID128_INIT(0x01, 0x00, 0xe8, 0xe9, 0xf5, 0x58, 0xf4, 0xa0, 0x9c,
                     0x4b, 0x4b, 0x2d, 0x01, 0x00, 0xce, 0x7f);
const ble_uuid128_t kNatKitDataNotifyUuid =
    BLE_UUID128_INIT(0x01, 0x00, 0xe8, 0xe9, 0xf5, 0x58, 0xf4, 0xa0, 0x9c,
                     0x4b, 0x4b, 0x2d, 0x02, 0x00, 0xce, 0x7f);
const ble_uuid128_t kNatKitControlWriteUuid =
    BLE_UUID128_INIT(0x01, 0x00, 0xe8, 0xe9, 0xf5, 0x58, 0xf4, 0xa0, 0x9c,
                     0x4b, 0x4b, 0x2d, 0x03, 0x00, 0xce, 0x7f);
const ble_uuid128_t kNatKitStatusUuid =
    BLE_UUID128_INIT(0x01, 0x00, 0xe8, 0xe9, 0xf5, 0x58, 0xf4, 0xa0, 0x9c,
                     0x4b, 0x4b, 0x2d, 0x04, 0x00, 0xce, 0x7f);

uint16_t g_data_char_handle = 0;
uint16_t g_control_char_handle = 0;
uint16_t g_status_char_handle = 0;

int ble_gap_event_static(struct ble_gap_event* event, void* arg);
int ble_gatt_access_static(uint16_t conn_handle, uint16_t attr_handle,
                           struct ble_gatt_access_ctxt* ctxt, void* arg);
void ble_host_task_static(void* param);
void ble_on_reset_static(int reason);
void ble_on_sync_static(void);

const ble_gatt_svc_def kNatKitServices[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &kNatKitServiceUuid.u,
        .includes = nullptr,
        .characteristics =
            (ble_gatt_chr_def[]){
                {
                    .uuid = &kNatKitDataNotifyUuid.u,
                    .access_cb = nullptr,
                    .arg = nullptr,
                    .descriptors = nullptr,
                    .flags = BLE_GATT_CHR_F_NOTIFY,
                    .min_key_size = 0,
                    .val_handle = &g_data_char_handle,
                    .cpfd = nullptr,
                },
                {
                    .uuid = &kNatKitControlWriteUuid.u,
                    .access_cb = ble_gatt_access_static,
                    .arg = nullptr,
                    .descriptors = nullptr,
                    .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP,
                    .min_key_size = 0,
                    .val_handle = &g_control_char_handle,
                    .cpfd = nullptr,
                },
                {
                    .uuid = &kNatKitStatusUuid.u,
                    .access_cb = ble_gatt_access_static,
                    .arg = nullptr,
                    .descriptors = nullptr,
                    .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
                    .min_key_size = 0,
                    .val_handle = &g_status_char_handle,
                    .cpfd = nullptr,
                },
                {
                    .uuid = nullptr,
                    .access_cb = nullptr,
                    .arg = nullptr,
                    .descriptors = nullptr,
                    .flags = 0,
                    .min_key_size = 0,
                    .val_handle = nullptr,
                    .cpfd = nullptr,
                },
            },
    },
    {
        .type = 0,
        .uuid = nullptr,
        .includes = nullptr,
        .characteristics = nullptr,
    },
};

class BleGattTransportPublisher final : public ITransportPublisher {
 public:
  explicit BleGattTransportPublisher(BleTransportConfig config) : config_(config) {}

  esp_err_t connect() override {
    if (initialized_.load(std::memory_order_acquire)) {
      return ESP_OK;
    }

    if (g_ble_instance != nullptr && g_ble_instance != this) {
      ESP_LOGW(kTag, "BLE_GATT already initialized by another publisher instance");
      return ESP_ERR_INVALID_STATE;
    }

    esp_err_t nvs_err = nvs_flash_init();
    if (nvs_err == ESP_ERR_NVS_NO_FREE_PAGES ||
        nvs_err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      nvs_err = nvs_flash_init();
    }
    if (nvs_err != ESP_OK) {
      ESP_LOGE(kTag, "nvs_flash_init failed for BLE: %s", esp_err_to_name(nvs_err));
      return nvs_err;
    }

    const esp_err_t nimble_err = nimble_port_init();
    if (nimble_err != ESP_OK) {
      ESP_LOGE(kTag, "nimble_port_init failed: %s", esp_err_to_name(nimble_err));
      return nimble_err;
    }

    ble_svc_gap_init();
    ble_svc_gatt_init();

    int rc = ble_gatts_count_cfg(kNatKitServices);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_gatts_count_cfg failed: %d", rc);
      return ESP_FAIL;
    }
    rc = ble_gatts_add_svcs(kNatKitServices);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_gatts_add_svcs failed: %d", rc);
      return ESP_FAIL;
    }

    rc = ble_svc_gap_device_name_set(config_.device_name);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_svc_gap_device_name_set failed: %d", rc);
      return ESP_FAIL;
    }

    ble_hs_cfg.reset_cb = ble_on_reset_static;
    ble_hs_cfg.sync_cb = ble_on_sync_static;

    ble_store_config_init();

    g_ble_instance = this;
    initialized_.store(true, std::memory_order_release);
    nimble_port_freertos_init(ble_host_task_static);

    runtime_state_.store(kStateIdle, std::memory_order_release);
    stream_enabled_.store(false, std::memory_order_release);
    set_stream_enabled(false);
    status_dirty_.store(true, std::memory_order_release);

    ESP_LOGI(kTag, "BLE_GATT transport init complete (name=%s mtu=%u)",
             config_.device_name, static_cast<unsigned>(config_.preferred_mtu));
    return ESP_OK;
  }

  bool is_connected() const override {
    return connected_.load(std::memory_order_acquire) &&
           data_notify_enabled_.load(std::memory_order_acquire);
  }

  esp_err_t publish(const uint8_t* packet, size_t packet_len, uint32_t sequence,
                    uint64_t timestamp_us) override {
    if (packet == nullptr || packet_len == 0U) {
      return ESP_ERR_INVALID_ARG;
    }
    if (!initialized_.load(std::memory_order_acquire)) {
      return ESP_ERR_INVALID_STATE;
    }
    if (!stream_enabled_.load(std::memory_order_acquire)) {
      return ESP_OK;
    }
    if (!is_connected()) {
      dropped_packets_.fetch_add(1, std::memory_order_relaxed);
      status_dirty_.store(true, std::memory_order_release);
      return ESP_ERR_INVALID_STATE;
    }

    const uint16_t conn_handle = conn_handle_.load(std::memory_order_acquire);
    const uint16_t mtu = att_mtu_.load(std::memory_order_acquire);
    const size_t max_chunk = (mtu > 3U) ? static_cast<size_t>(mtu - 3U) : 20U;

    size_t offset = 0U;
    while (offset < packet_len) {
      const size_t chunk_len = std::min(max_chunk, packet_len - offset);
      struct os_mbuf* om = ble_hs_mbuf_from_flat(packet + offset, chunk_len);
      if (om == nullptr) {
        dropped_packets_.fetch_add(1, std::memory_order_relaxed);
        status_dirty_.store(true, std::memory_order_release);
        return ESP_ERR_NO_MEM;
      }

      const int rc = ble_gatts_notify_custom(conn_handle, g_data_char_handle, om);
      if (rc != 0) {
        dropped_packets_.fetch_add(1, std::memory_order_relaxed);
        status_dirty_.store(true, std::memory_order_release);
        return ESP_FAIL;
      }
      offset += chunk_len;
    }

    if ((sequence % 10U) == 0U) {
      ESP_LOGI(kTag, "BLE transport seq=%" PRIu32 " ts=%" PRIu64
                     "us bytes=%u mtu=%u",
               sequence, timestamp_us, static_cast<unsigned>(packet_len),
               static_cast<unsigned>(mtu));
    }
    return ESP_OK;
  }

  void loop() override {
    if (!initialized_.load(std::memory_order_acquire)) {
      return;
    }

    const uint64_t now_ms =
        static_cast<uint64_t>(esp_timer_get_time() / 1000LL);
    const uint64_t last_notify_ms =
        last_status_notify_ms_.load(std::memory_order_acquire);
    const bool interval_elapsed =
        (now_ms >= last_notify_ms) &&
        ((now_ms - last_notify_ms) >= config_.status_interval_ms);

    if (interval_elapsed ||
        status_dirty_.load(std::memory_order_acquire)) {
      send_status_notification(now_ms);
    }
  }

  TransportType type() const override { return TransportType::BleGatt; }

  int on_gap_event(struct ble_gap_event* event) {
    if (event == nullptr) {
      return 0;
    }

    switch (event->type) {
      case BLE_GAP_EVENT_CONNECT: {
        if (event->connect.status == 0) {
          conn_handle_.store(event->connect.conn_handle, std::memory_order_release);
          connected_.store(true, std::memory_order_release);
          data_notify_enabled_.store(false, std::memory_order_release);
          status_notify_enabled_.store(false, std::memory_order_release);
          att_mtu_.store(kDefaultAttMtu, std::memory_order_release);

          struct ble_gap_upd_params conn_params{};
          conn_params.itvl_min = config_.conn_interval_min_units;
          conn_params.itvl_max = config_.conn_interval_max_units;
          conn_params.latency = 0;
          conn_params.supervision_timeout = 400;
          conn_params.min_ce_len = 0;
          conn_params.max_ce_len = 0;
          const int update_rc =
              ble_gap_update_params(event->connect.conn_handle, &conn_params);
          if (update_rc != 0) {
            ESP_LOGW(kTag, "BLE conn params update request failed: %d", update_rc);
          }

          runtime_state_.store(kStateIdle, std::memory_order_release);
          stream_enabled_.store(false, std::memory_order_release);
          set_stream_enabled(false);
          ESP_LOGI(kTag, "BLE client connected, conn_handle=%u",
                   static_cast<unsigned>(event->connect.conn_handle));
        } else {
          ESP_LOGW(kTag, "BLE connection failed, status=%d", event->connect.status);
          start_advertising();
        }
        status_dirty_.store(true, std::memory_order_release);
        return 0;
      }

      case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGW(kTag, "BLE disconnect reason=%d", event->disconnect.reason);
        connected_.store(false, std::memory_order_release);
        data_notify_enabled_.store(false, std::memory_order_release);
        status_notify_enabled_.store(false, std::memory_order_release);
        stream_enabled_.store(false, std::memory_order_release);
        set_stream_enabled(false);
        runtime_state_.store(kStateIdle, std::memory_order_release);
        conn_handle_.store(BLE_HS_CONN_HANDLE_NONE, std::memory_order_release);
        att_mtu_.store(kDefaultAttMtu, std::memory_order_release);
        status_dirty_.store(true, std::memory_order_release);
        start_advertising();
        return 0;

      case BLE_GAP_EVENT_ADV_COMPLETE:
        start_advertising();
        return 0;

      case BLE_GAP_EVENT_SUBSCRIBE:
        if (event->subscribe.attr_handle == g_data_char_handle) {
          data_notify_enabled_.store(event->subscribe.cur_notify,
                                     std::memory_order_release);
          ESP_LOGI(kTag, "BLE data notify=%d", event->subscribe.cur_notify);
        } else if (event->subscribe.attr_handle == g_status_char_handle) {
          status_notify_enabled_.store(event->subscribe.cur_notify,
                                       std::memory_order_release);
          ESP_LOGI(kTag, "BLE status notify=%d", event->subscribe.cur_notify);
        }
        status_dirty_.store(true, std::memory_order_release);
        return 0;

      case BLE_GAP_EVENT_MTU:
        att_mtu_.store(event->mtu.value, std::memory_order_release);
        ESP_LOGI(kTag, "BLE MTU updated: %u",
                 static_cast<unsigned>(event->mtu.value));
        status_dirty_.store(true, std::memory_order_release);
        return 0;

      default:
        return 0;
    }
  }

  int on_gatt_access(uint16_t conn_handle, uint16_t attr_handle,
                     struct ble_gatt_access_ctxt* ctxt) {
    (void)conn_handle;
    if (ctxt == nullptr) {
      return BLE_ATT_ERR_UNLIKELY;
    }

    switch (ctxt->op) {
      case BLE_GATT_ACCESS_OP_WRITE_CHR:
        if (attr_handle == g_control_char_handle) {
          return handle_control_write(ctxt->om);
        }
        return BLE_ATT_ERR_UNLIKELY;

      case BLE_GATT_ACCESS_OP_READ_CHR:
        if (attr_handle == g_status_char_handle) {
          BleStatusPayloadV1 payload = make_status_payload();
          const int rc = os_mbuf_append(ctxt->om, &payload, sizeof(payload));
          return (rc == 0) ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
        }
        return BLE_ATT_ERR_UNLIKELY;

      default:
        return BLE_ATT_ERR_UNLIKELY;
    }
  }

  void on_reset(int reason) {
    ESP_LOGW(kTag, "BLE reset reason=%d", reason);
    connected_.store(false, std::memory_order_release);
    data_notify_enabled_.store(false, std::memory_order_release);
    status_notify_enabled_.store(false, std::memory_order_release);
    stream_enabled_.store(false, std::memory_order_release);
    set_stream_enabled(false);
    runtime_state_.store(kStateError, std::memory_order_release);
    conn_handle_.store(BLE_HS_CONN_HANDLE_NONE, std::memory_order_release);
    att_mtu_.store(kDefaultAttMtu, std::memory_order_release);
    status_dirty_.store(true, std::memory_order_release);
  }

  void on_sync() {
    if (config_.preferred_mtu > 23U) {
      const int mtu_rc = ble_att_set_preferred_mtu(config_.preferred_mtu);
      if (mtu_rc != 0) {
        ESP_LOGW(kTag, "ble_att_set_preferred_mtu failed rc=%d", mtu_rc);
      }
    }

    int rc = ble_hs_id_infer_auto(0, &own_addr_type_);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_hs_id_infer_auto failed rc=%d", rc);
      return;
    }

    runtime_state_.store(kStateIdle, std::memory_order_release);
    status_dirty_.store(true, std::memory_order_release);
    start_advertising();
  }

 private:
  void start_advertising() {
    if (!initialized_.load(std::memory_order_acquire)) {
      return;
    }
    if (connected_.load(std::memory_order_acquire)) {
      return;
    }

    struct ble_hs_adv_fields fields{};
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.tx_pwr_lvl_is_present = 1;
    fields.tx_pwr_lvl = BLE_HS_ADV_TX_PWR_LVL_AUTO;
    fields.name = reinterpret_cast<const uint8_t*>(config_.device_name);
    fields.name_len = static_cast<uint8_t>(std::strlen(config_.device_name));
    fields.name_is_complete = 1;
    fields.uuids128 = &kNatKitServiceUuid;
    fields.num_uuids128 = 1;
    fields.uuids128_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_gap_adv_set_fields failed rc=%d", rc);
      return;
    }

    struct ble_gap_adv_params adv_params{};
    adv_params.conn_mode = BLE_GAP_CONN_MODE_UND;
    adv_params.disc_mode = BLE_GAP_DISC_MODE_GEN;

    rc = ble_gap_adv_start(own_addr_type_, nullptr, BLE_HS_FOREVER, &adv_params,
                           ble_gap_event_static, nullptr);
    if (rc != 0) {
      ESP_LOGE(kTag, "ble_gap_adv_start failed rc=%d", rc);
      return;
    }

    ESP_LOGI(kTag, "BLE advertising as '%s'", config_.device_name);
  }

  int handle_control_write(struct os_mbuf* om) {
    const uint16_t cmd_len = OS_MBUF_PKTLEN(om);
    if (cmd_len < 1U || cmd_len > sizeof(BleControlCommandV1)) {
      return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    }

    BleControlCommandV1 cmd{};
    uint16_t out_len = 0;
    const int rc = ble_hs_mbuf_to_flat(om, &cmd, sizeof(cmd), &out_len);
    if (rc != 0 || out_len < 1U) {
      return BLE_ATT_ERR_UNLIKELY;
    }

    switch (cmd.opcode) {
      case 0x01:  // START_STREAM
        stream_enabled_.store(true, std::memory_order_release);
        set_stream_enabled(true);
        runtime_state_.store(kStateStreaming, std::memory_order_release);
        ESP_LOGI(kTag, "BLE control START_STREAM");
        break;

      case 0x02:  // STOP_STREAM
        stream_enabled_.store(false, std::memory_order_release);
        set_stream_enabled(false);
        runtime_state_.store(kStateIdle, std::memory_order_release);
        ESP_LOGI(kTag, "BLE control STOP_STREAM");
        break;

      case 0x03:  // CALIBRATE_IMU_TARE
        request_imu_tare();
        runtime_state_.store(kStateCalibrating, std::memory_order_release);
        ESP_LOGI(kTag, "BLE control CALIBRATE_IMU_TARE");
        break;

      case 0x04:  // CALIBRATE_EMG_BASELINE
        request_emg_baseline();
        runtime_state_.store(kStateCalibrating, std::memory_order_release);
        ESP_LOGI(kTag, "BLE control CALIBRATE_EMG_BASELINE");
        break;

      case 0x05:  // SET_SAMPLE_RATE_HZ
        if (cmd.arg2 == 0U) {
          return BLE_ATT_ERR_VALUE_NOT_ALLOWED;
        }
        set_requested_sample_rate_hz(cmd.arg2);
        ESP_LOGI(kTag, "BLE control SET_SAMPLE_RATE_HZ=%" PRIu32, cmd.arg2);
        break;

      case 0x06:  // SET_TRANSPORT_MODE
        if (cmd.arg0 > static_cast<uint8_t>(TransportMode::Gestures)) {
          return BLE_ATT_ERR_VALUE_NOT_ALLOWED;
        }
        set_transport_mode(static_cast<TransportMode>(cmd.arg0));
        ESP_LOGI(kTag, "BLE control SET_TRANSPORT_MODE=%u",
                 static_cast<unsigned>(cmd.arg0));
        break;

      default:
        return BLE_ATT_ERR_VALUE_NOT_ALLOWED;
    }

    status_dirty_.store(true, std::memory_order_release);
    return 0;
  }

  BleStatusPayloadV1 make_status_payload() {
    BleStatusPayloadV1 status{};
    uint8_t packed_state =
        static_cast<uint8_t>(runtime_state_.load(std::memory_order_acquire) &
                             kStatusStateMask);
    if (imu_tare_calibration_valid()) {
      packed_state = static_cast<uint8_t>(packed_state | kStatusImuCalibrationValid);
    }
    if (emg_baseline_calibration_valid()) {
      packed_state = static_cast<uint8_t>(packed_state | kStatusEmgCalibrationValid);
    }
    status.state = packed_state;
    status.battery_pct = kStatusBatteryUnknown;
    status.link_quality = compute_link_quality();
    status.dropped_packets = dropped_packets_.load(std::memory_order_acquire);
    status.uptime_ms = static_cast<uint32_t>(esp_timer_get_time() / 1000LL);
    return status;
  }

  uint8_t compute_link_quality() {
    if (!connected_.load(std::memory_order_acquire)) {
      return 0;
    }

    const uint16_t conn_handle = conn_handle_.load(std::memory_order_acquire);
    int8_t rssi = -100;
    if (ble_gap_conn_rssi(conn_handle, &rssi) == 0) {
      rssi_dbm_.store(rssi, std::memory_order_release);
    } else {
      rssi = rssi_dbm_.load(std::memory_order_acquire);
    }

    if (rssi <= -100) {
      return 0;
    }
    if (rssi >= -40) {
      return 100;
    }
    return static_cast<uint8_t>(((rssi + 100) * 100) / 60);
  }

  void send_status_notification(uint64_t now_ms) {
    if (!connected_.load(std::memory_order_acquire) ||
        !status_notify_enabled_.load(std::memory_order_acquire)) {
      return;
    }

    const uint16_t conn_handle = conn_handle_.load(std::memory_order_acquire);
    BleStatusPayloadV1 status = make_status_payload();
    struct os_mbuf* om = ble_hs_mbuf_from_flat(&status, sizeof(status));
    if (om == nullptr) {
      dropped_packets_.fetch_add(1, std::memory_order_relaxed);
      status_dirty_.store(true, std::memory_order_release);
      return;
    }

    const int rc = ble_gatts_notify_custom(conn_handle, g_status_char_handle, om);
    if (rc != 0) {
      dropped_packets_.fetch_add(1, std::memory_order_relaxed);
      status_dirty_.store(true, std::memory_order_release);
      return;
    }

    last_status_notify_ms_.store(now_ms, std::memory_order_release);
    status_dirty_.store(false, std::memory_order_release);
  }

  BleTransportConfig config_{};
  std::atomic<bool> initialized_{false};
  std::atomic<bool> connected_{false};
  std::atomic<bool> data_notify_enabled_{false};
  std::atomic<bool> status_notify_enabled_{false};
  std::atomic<bool> stream_enabled_{false};
  std::atomic<uint8_t> runtime_state_{kStateIdle};
  std::atomic<uint16_t> conn_handle_{BLE_HS_CONN_HANDLE_NONE};
  std::atomic<uint16_t> att_mtu_{kDefaultAttMtu};
  std::atomic<uint32_t> dropped_packets_{0};
  std::atomic<int8_t> rssi_dbm_{-100};
  std::atomic<uint64_t> last_status_notify_ms_{0};
  std::atomic<bool> status_dirty_{false};
  uint8_t own_addr_type_ = BLE_OWN_ADDR_PUBLIC;
};

int ble_gap_event_static(struct ble_gap_event* event, void* arg) {
  (void)arg;
  if (g_ble_instance == nullptr) {
    return 0;
  }
  return g_ble_instance->on_gap_event(event);
}

int ble_gatt_access_static(uint16_t conn_handle, uint16_t attr_handle,
                           struct ble_gatt_access_ctxt* ctxt, void* arg) {
  (void)arg;
  if (g_ble_instance == nullptr) {
    return BLE_ATT_ERR_UNLIKELY;
  }
  return g_ble_instance->on_gatt_access(conn_handle, attr_handle, ctxt);
}

void ble_host_task_static(void* param) {
  (void)param;
  nimble_port_run();
  nimble_port_freertos_deinit();
}

void ble_on_reset_static(int reason) {
  if (g_ble_instance == nullptr) {
    return;
  }
  g_ble_instance->on_reset(reason);
}

void ble_on_sync_static(void) {
  if (g_ble_instance == nullptr) {
    return;
  }
  g_ble_instance->on_sync();
}

#endif  // CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED

LogTransportPublisher g_log_transport;

#if CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED
BleGattTransportPublisher* g_ble_transport = nullptr;
#else
UnsupportedTransportPublisher g_ble_transport{TransportType::BleGatt};
#endif

MqttTransportPublisher* g_mqtt_transport = nullptr;

}  // namespace

const char* to_string(TransportType type) {
  switch (type) {
    case TransportType::LogOnly:
      return "LOG_ONLY";
    case TransportType::MqttIp:
      return "MQTT_IP";
    case TransportType::BleGatt:
      return "BLE_GATT";
    default:
      return "UNKNOWN";
  }
}

ITransportPublisher* create_publisher(TransportType type) {
  return create_publisher(type, kDefaultTransportConfig);
}

ITransportPublisher* create_publisher(TransportType type,
                                      const TransportConfig& config) {
  switch (type) {
    case TransportType::LogOnly:
      set_stream_enabled(true);
      set_requested_sample_rate_hz(0);
      set_transport_mode(TransportMode::Raw);
      return &g_log_transport;

    case TransportType::MqttIp: {
      if (g_mqtt_transport != nullptr) {
        delete g_mqtt_transport;
      }
      g_mqtt_transport = new (std::nothrow) MqttTransportPublisher(config.mqtt);
      set_stream_enabled(true);
      set_requested_sample_rate_hz(0);
      set_transport_mode(TransportMode::Raw);
      if (g_mqtt_transport != nullptr) {
        return g_mqtt_transport;
      }
      return &g_log_transport;
    }

    case TransportType::BleGatt:
#if CONFIG_BT_ENABLED && CONFIG_BT_NIMBLE_ENABLED
      if (g_ble_transport == nullptr) {
        g_ble_transport = new (std::nothrow) BleGattTransportPublisher(config.ble);
      }
      if (g_ble_transport != nullptr) {
        return g_ble_transport;
      }
      return &g_log_transport;
#else
      return &g_ble_transport;
#endif

    default:
      return &g_log_transport;
  }
}

void set_stream_enabled(bool enabled) {
  g_runtime_stream_enabled.store(enabled, std::memory_order_release);
}

bool stream_enabled() {
  return g_runtime_stream_enabled.load(std::memory_order_acquire);
}

void set_requested_sample_rate_hz(uint32_t hz) {
  g_runtime_sample_rate_hz.store(hz, std::memory_order_release);
}

uint32_t requested_sample_rate_hz() {
  return g_runtime_sample_rate_hz.load(std::memory_order_acquire);
}

void set_transport_mode(TransportMode mode) {
  g_runtime_transport_mode.store(static_cast<uint8_t>(mode),
                                 std::memory_order_release);
}

TransportMode transport_mode() {
  const auto raw =
      g_runtime_transport_mode.load(std::memory_order_acquire);
  if (raw > static_cast<uint8_t>(TransportMode::Gestures)) {
    return TransportMode::Raw;
  }
  return static_cast<TransportMode>(raw);
}

void request_imu_tare() {
  g_runtime_imu_tare_pending.store(true, std::memory_order_release);
}

bool consume_imu_tare_request() {
  return g_runtime_imu_tare_pending.exchange(false, std::memory_order_acq_rel);
}

void request_emg_baseline() {
  g_runtime_emg_baseline_pending.store(true, std::memory_order_release);
}

bool consume_emg_baseline_request() {
  return g_runtime_emg_baseline_pending.exchange(false,
                                                 std::memory_order_acq_rel);
}

void set_calibration_validity(bool imu_tare_valid, bool emg_baseline_valid) {
  g_runtime_imu_tare_valid.store(imu_tare_valid, std::memory_order_release);
  g_runtime_emg_baseline_valid.store(emg_baseline_valid,
                                     std::memory_order_release);
}

bool imu_tare_calibration_valid() {
  return g_runtime_imu_tare_valid.load(std::memory_order_acquire);
}

bool emg_baseline_calibration_valid() {
  return g_runtime_emg_baseline_valid.load(std::memory_order_acquire);
}

}  // namespace nat::hand_tracking::transport
