#include "networking.hpp"

#include <cstring>
#include <ctime>

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_sntp.h"
#include "esp_mac.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char* TAG = "Networking";

// Event group bits
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1
#define MQTT_CONNECTED_BIT BIT2
#define NTP_SYNCED_BIT     BIT3

static EventGroupHandle_t s_networking_event_group = nullptr;
static esp_mqtt_client_handle_t s_mqtt_client = nullptr;
static bool s_wifi_connected = false;
static bool s_mqtt_connected = false;
static bool s_ntp_synced = false;

// WiFi event handler
static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT) {
        switch (event_id) {
            case WIFI_EVENT_STA_START:
                ESP_LOGI(TAG, "WiFi STA started, connecting...");
                esp_wifi_connect();
                break;
            case WIFI_EVENT_STA_DISCONNECTED:
                ESP_LOGW(TAG, "WiFi disconnected");
                s_wifi_connected = false;
                xEventGroupClearBits(s_networking_event_group, WIFI_CONNECTED_BIT);
                // Try to reconnect
                esp_wifi_connect();
                break;
            default:
                break;
        }
    } else if (event_base == IP_EVENT) {
        if (event_id == IP_EVENT_STA_GOT_IP) {
            ip_event_got_ip_t* event = (ip_event_got_ip_t*)event_data;
            ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
            s_wifi_connected = true;
            xEventGroupSetBits(s_networking_event_group, WIFI_CONNECTED_BIT);
        }
    }
}

// MQTT event handler
static void mqtt_event_handler(void* handler_args, esp_event_base_t base,
                               int32_t event_id, void* event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    
    switch (event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT connected");
            s_mqtt_connected = true;
            xEventGroupSetBits(s_networking_event_group, MQTT_CONNECTED_BIT);
            break;
        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "MQTT disconnected");
            s_mqtt_connected = false;
            xEventGroupClearBits(s_networking_event_group, MQTT_CONNECTED_BIT);
            break;
        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT error");
            if (event->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
                ESP_LOGE(TAG, "TCP transport error");
            }
            break;
        default:
            break;
    }
}

// NTP time sync callback
static void ntp_sync_notification_cb(struct timeval* tv) {
    ESP_LOGI(TAG, "NTP time synchronized");
    s_ntp_synced = true;
    if (s_networking_event_group) {
        xEventGroupSetBits(s_networking_event_group, NTP_SYNCED_BIT);
    }
}

int networking_init() {
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Create event group
    s_networking_event_group = xEventGroupCreate();
    if (s_networking_event_group == nullptr) {
        ESP_LOGE(TAG, "Failed to create event group");
        return -1;
    }

    // Initialize TCP/IP stack
    ESP_ERROR_CHECK(esp_netif_init());

    // Create default event loop
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    ESP_LOGI(TAG, "Networking subsystem initialized");
    return 0;
}

int networking_wifi_connect(const char* ssid, const char* password, uint32_t timeout_ms) {
    // Create default WiFi STA
    esp_netif_create_default_wifi_sta();

    // Initialize WiFi with default config
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    // Register event handlers
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler, nullptr, nullptr));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler, nullptr, nullptr));

    // Configure WiFi
    wifi_config_t wifi_config = {};
    strncpy((char*)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char*)wifi_config.sta.password, password, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Connecting to WiFi SSID: %s", ssid);

    // Wait for connection
    EventBits_t bits = xEventGroupWaitBits(s_networking_event_group,
                                           WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                           pdFALSE, pdFALSE,
                                           timeout_ms / portTICK_PERIOD_MS);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "WiFi connected successfully");
        
        // Disable WiFi power save mode for better BLE coexistence
        // This prevents WiFi from sleeping and causing BLE packet loss
        esp_err_t ps_err = esp_wifi_set_ps(WIFI_PS_NONE);
        if (ps_err == ESP_OK) {
            ESP_LOGI(TAG, "WiFi power save disabled for BLE coexistence");
        } else {
            ESP_LOGW(TAG, "Failed to disable WiFi power save: %d", ps_err);
        }
        
        return 0;
    } else {
        ESP_LOGE(TAG, "WiFi connection failed or timed out");
        return -1;
    }
}

bool networking_wifi_is_connected() {
    return s_wifi_connected;
}

int networking_ntp_init(const char* ntp_server) {
    const char* server = ntp_server ? ntp_server : "pool.ntp.org";
    
    ESP_LOGI(TAG, "Initializing NTP with server: %s", server);
    
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, server);
    sntp_set_time_sync_notification_cb(ntp_sync_notification_cb);
    esp_sntp_init();
    
    return 0;
}

int networking_ntp_wait_sync(uint32_t timeout_ms) {
    ESP_LOGI(TAG, "Waiting for NTP sync...");
    
    EventBits_t bits = xEventGroupWaitBits(s_networking_event_group,
                                           NTP_SYNCED_BIT,
                                           pdFALSE, pdFALSE,
                                           timeout_ms / portTICK_PERIOD_MS);
    
    if (bits & NTP_SYNCED_BIT) {
        time_t now;
        struct tm timeinfo;
        time(&now);
        localtime_r(&now, &timeinfo);
        ESP_LOGI(TAG, "NTP synced, current time: %s", asctime(&timeinfo));
        return 0;
    } else {
        ESP_LOGW(TAG, "NTP sync timed out");
        return -1;
    }
}

bool networking_ntp_is_synced() {
    return s_ntp_synced;
}

uint64_t networking_get_time_us() {
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    return (uint64_t)tv.tv_sec * 1000000ULL + (uint64_t)tv.tv_usec;
}

int networking_mqtt_init(const char* broker_host, uint16_t broker_port, const char* client_id) {
    char uri[128];
    snprintf(uri, sizeof(uri), "mqtt://%s:%u", broker_host, broker_port);
    
    ESP_LOGI(TAG, "Initializing MQTT client: %s (client_id: %s)", uri, client_id);
    
    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = uri;
    mqtt_cfg.credentials.client_id = client_id;
    mqtt_cfg.buffer.size = 16384;  // 16KB buffer for bulk messages
    
    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    if (s_mqtt_client == nullptr) {
        ESP_LOGE(TAG, "Failed to initialize MQTT client");
        return -1;
    }
    
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(s_mqtt_client, 
                                                   (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID,
                                                   mqtt_event_handler, nullptr));
    
    return 0;
}

int networking_mqtt_connect(uint32_t timeout_ms) {
    if (s_mqtt_client == nullptr) {
        ESP_LOGE(TAG, "MQTT client not initialized");
        return -1;
    }
    
    ESP_LOGI(TAG, "Connecting to MQTT broker...");
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt_client));
    
    // Wait for connection
    EventBits_t bits = xEventGroupWaitBits(s_networking_event_group,
                                           MQTT_CONNECTED_BIT,
                                           pdFALSE, pdFALSE,
                                           timeout_ms / portTICK_PERIOD_MS);
    
    if (bits & MQTT_CONNECTED_BIT) {
        ESP_LOGI(TAG, "MQTT connected successfully");
        return 0;
    } else {
        ESP_LOGE(TAG, "MQTT connection timed out");
        return -1;
    }
}

bool networking_mqtt_is_connected() {
    return s_mqtt_connected;
}

int networking_mqtt_publish(const char* topic, const uint8_t* data, size_t len, int qos) {
    if (s_mqtt_client == nullptr || !s_mqtt_connected) {
        return -1;
    }
    
    int msg_id = esp_mqtt_client_publish(s_mqtt_client, topic, 
                                         (const char*)data, len, qos, 0);
    
    if (msg_id < 0) {
        ESP_LOGE(TAG, "MQTT publish failed");
        return -1;
    }
    
    return 0;
}

void networking_mqtt_disconnect() {
    if (s_mqtt_client != nullptr) {
        esp_mqtt_client_stop(s_mqtt_client);
        esp_mqtt_client_destroy(s_mqtt_client);
        s_mqtt_client = nullptr;
        s_mqtt_connected = false;
    }
}

void networking_get_mac_string(char* buffer) {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(buffer, 18, "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

uint64_t networking_get_device_id() {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    
    // Create a 64-bit ID from the MAC address
    uint64_t id = 0;
    for (int i = 0; i < 6; i++) {
        id = (id << 8) | mac[i];
    }
    return id;
}
