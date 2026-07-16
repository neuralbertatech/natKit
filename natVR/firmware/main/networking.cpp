#include "networking.hpp"

#include <cstdio>
#include <cstring>
#include <ctime>
#include <sys/time.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

namespace {

constexpr char kTag[] = "natvr-net";

constexpr EventBits_t kWifiConnectedBit = BIT0;
constexpr EventBits_t kMqttConnectedBit = BIT1;
constexpr EventBits_t kNtpSyncedBit = BIT2;

EventGroupHandle_t g_event_group = nullptr;
esp_mqtt_client_handle_t g_mqtt_client = nullptr;
bool g_wifi_connected = false;
bool g_mqtt_connected = false;
bool g_ntp_synced = false;

void wifi_event_handler(void* /*arg*/, esp_event_base_t event_base,
                        int32_t event_id, void* event_data) {
  if (event_base == WIFI_EVENT) {
    switch (event_id) {
      case WIFI_EVENT_STA_START:
        esp_wifi_connect();
        break;
      case WIFI_EVENT_STA_DISCONNECTED:
        ESP_LOGW(kTag, "WiFi disconnected");
        g_wifi_connected = false;
        xEventGroupClearBits(g_event_group, kWifiConnectedBit);
        esp_wifi_connect();
        break;
      default:
        break;
    }
    return;
  }

  if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
    const auto* event = static_cast<ip_event_got_ip_t*>(event_data);
    ESP_LOGI(kTag, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
    g_wifi_connected = true;
    xEventGroupSetBits(g_event_group, kWifiConnectedBit);
  }
}

void mqtt_event_handler(void* /*handler_args*/, esp_event_base_t /*base*/,
                        int32_t event_id, void* event_data) {
  const auto* event = static_cast<esp_mqtt_event_handle_t>(event_data);
  switch (event_id) {
    case MQTT_EVENT_CONNECTED:
      ESP_LOGI(kTag, "MQTT connected");
      g_mqtt_connected = true;
      xEventGroupSetBits(g_event_group, kMqttConnectedBit);
      break;
    case MQTT_EVENT_DISCONNECTED:
      ESP_LOGW(kTag, "MQTT disconnected");
      g_mqtt_connected = false;
      xEventGroupClearBits(g_event_group, kMqttConnectedBit);
      break;
    case MQTT_EVENT_ERROR:
      g_mqtt_connected = false;
      xEventGroupClearBits(g_event_group, kMqttConnectedBit);
      if (event != nullptr && event->error_handle != nullptr) {
        ESP_LOGW(kTag, "MQTT error type=%d", event->error_handle->error_type);
      } else {
        ESP_LOGW(kTag, "MQTT error");
      }
      break;
    default:
      break;
  }
}

void ntp_sync_notification_cb(struct timeval* /*tv*/) {
  ESP_LOGI(kTag, "NTP synchronized");
  g_ntp_synced = true;
  if (g_event_group != nullptr) {
    xEventGroupSetBits(g_event_group, kNtpSyncedBit);
  }
}

}  // namespace

int networking_init() {
  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES ||
      err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    err = nvs_flash_init();
  }
  ESP_ERROR_CHECK(err);

  if (g_event_group == nullptr) {
    g_event_group = xEventGroupCreate();
    if (g_event_group == nullptr) {
      ESP_LOGE(kTag, "Failed to create event group");
      return -1;
    }
  }

  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());
  return 0;
}

int networking_wifi_connect(const char* ssid, const char* password,
                            uint32_t timeout_ms) {
  esp_netif_create_default_wifi_sta();

  const wifi_init_config_t init_cfg = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&init_cfg));

  ESP_ERROR_CHECK(esp_event_handler_instance_register(
      WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, nullptr, nullptr));
  ESP_ERROR_CHECK(esp_event_handler_instance_register(
      IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, nullptr, nullptr));

  wifi_config_t wifi_config{};
  std::strncpy(reinterpret_cast<char*>(wifi_config.sta.ssid), ssid,
               sizeof(wifi_config.sta.ssid) - 1);
  std::strncpy(reinterpret_cast<char*>(wifi_config.sta.password), password,
               sizeof(wifi_config.sta.password) - 1);
  wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
  ESP_ERROR_CHECK(esp_wifi_start());

  const EventBits_t bits = xEventGroupWaitBits(
      g_event_group, kWifiConnectedBit, pdFALSE, pdFALSE,
      pdMS_TO_TICKS(timeout_ms));
  if ((bits & kWifiConnectedBit) == 0) {
    ESP_LOGE(kTag, "WiFi connection timed out");
    return -1;
  }

  const esp_err_t ps_err = esp_wifi_set_ps(WIFI_PS_NONE);
  if (ps_err != ESP_OK) {
    ESP_LOGW(kTag, "Failed to disable WiFi power-save: %s",
             esp_err_to_name(ps_err));
  }
  return 0;
}

bool networking_wifi_is_connected() { return g_wifi_connected; }

int networking_wifi_rssi_dbm() {
  if (!g_wifi_connected) {
    return 0;
  }
  wifi_ap_record_t ap_info{};
  if (esp_wifi_sta_get_ap_info(&ap_info) != ESP_OK) {
    return 0;
  }
  return static_cast<int>(ap_info.rssi);
}

int networking_ntp_init(const char* ntp_server) {
  const char* server = ntp_server != nullptr ? ntp_server : "pool.ntp.org";
  esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
  esp_sntp_setservername(0, server);
  sntp_set_time_sync_notification_cb(ntp_sync_notification_cb);
  esp_sntp_init();
  return 0;
}

int networking_ntp_wait_sync(uint32_t timeout_ms) {
  const EventBits_t bits = xEventGroupWaitBits(
      g_event_group, kNtpSyncedBit, pdFALSE, pdFALSE,
      pdMS_TO_TICKS(timeout_ms));
  if ((bits & kNtpSyncedBit) == 0) {
    return -1;
  }
  return 0;
}

bool networking_ntp_is_synced() { return g_ntp_synced; }

uint64_t networking_get_time_us() {
  timeval tv{};
  gettimeofday(&tv, nullptr);
  return (static_cast<uint64_t>(tv.tv_sec) * 1000000ULL) +
         static_cast<uint64_t>(tv.tv_usec);
}

void networking_get_mac_string(char* out_mac) {
  uint8_t mac[6]{};
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  std::snprintf(out_mac, 18, "%02X:%02X:%02X:%02X:%02X:%02X", mac[0], mac[1],
                mac[2], mac[3], mac[4], mac[5]);
}

int networking_mqtt_init(const char* broker_host, uint16_t broker_port,
                         const char* client_id, size_t buffer_size) {
  char uri[128];
  std::snprintf(uri, sizeof(uri), "mqtt://%s:%u", broker_host, broker_port);

  esp_mqtt_client_config_t mqtt_cfg{};
  mqtt_cfg.broker.address.uri = uri;
  mqtt_cfg.credentials.client_id = client_id;
  mqtt_cfg.buffer.size = static_cast<int>(buffer_size);
  mqtt_cfg.network.disable_auto_reconnect = false;

  g_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
  if (g_mqtt_client == nullptr) {
    ESP_LOGE(kTag, "Failed to initialize MQTT client");
    return -1;
  }

  ESP_ERROR_CHECK(esp_mqtt_client_register_event(
      g_mqtt_client, MQTT_EVENT_ANY, mqtt_event_handler, nullptr));
  return 0;
}

int networking_mqtt_connect(uint32_t timeout_ms) {
  if (g_mqtt_client == nullptr) {
    return -1;
  }
  ESP_ERROR_CHECK(esp_mqtt_client_start(g_mqtt_client));

  const EventBits_t bits = xEventGroupWaitBits(
      g_event_group, kMqttConnectedBit, pdFALSE, pdFALSE,
      pdMS_TO_TICKS(timeout_ms));
  return (bits & kMqttConnectedBit) != 0 ? 0 : -1;
}

bool networking_mqtt_is_connected() { return g_mqtt_connected; }

int networking_mqtt_publish(const char* topic, const uint8_t* data, size_t len,
                            int qos, bool retain) {
  if (g_mqtt_client == nullptr || !g_mqtt_connected) {
    return -1;
  }
  const int msg_id = esp_mqtt_client_publish(
      g_mqtt_client, topic, reinterpret_cast<const char*>(data),
      static_cast<int>(len), qos, retain ? 1 : 0);
  return msg_id < 0 ? -1 : 0;
}

void networking_mqtt_disconnect() {
  if (g_mqtt_client == nullptr) {
    return;
  }
  esp_mqtt_client_stop(g_mqtt_client);
  esp_mqtt_client_destroy(g_mqtt_client);
  g_mqtt_client = nullptr;
  g_mqtt_connected = false;
}
