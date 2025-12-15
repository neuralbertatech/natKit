#include <cstdio>
#include <cstring>
#include <new>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "muse_cpp_wrapper.hpp"
#include "muse_data_buffer.hpp"
#include "networking.hpp"

// Development configuration - copy DevConfig.hpp.example to DevConfig.hpp
#if __has_include("DevConfig.hpp")
#include "DevConfig.hpp"
#else
// Default configuration - override with DevConfig.hpp
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define MQTT_BROKER_HOST "192.168.1.100"
#define MQTT_BROKER_PORT 1883
#endif

static const char* TAG = "natMuse";

// Global data buffer
static MuseDataBuffer g_dataBuffer;

// MQTT topic for bulk data
static char g_mqttTopic[128];

// Task handles
static TaskHandle_t g_publishTaskHandle = nullptr;

// Forward declarations
static void publishTask(void* param);
static void onEegData(muse_eeg_channel_t channel, const muse_eeg_data_t* data);
static void onAccelData(const muse_accel_data_t* data);
static void onGyroData(const muse_gyro_data_t* data);
static void onStatusChange(muse_status_t status);

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "       natMuse - Muse Headband Gateway     ");
    ESP_LOGI(TAG, "===========================================");

    // Initialize networking subsystem
    ESP_LOGI(TAG, "Initializing networking...");
    if (networking_init() != 0) {
        ESP_LOGE(TAG, "Failed to initialize networking");
        return;
    }

    // Connect to WiFi
    ESP_LOGI(TAG, "Connecting to WiFi: %s", WIFI_SSID);
    if (networking_wifi_connect(WIFI_SSID, WIFI_PASSWORD, 30000) != 0) {
        ESP_LOGE(TAG, "Failed to connect to WiFi");
        return;
    }

    // Initialize and wait for NTP sync
    ESP_LOGI(TAG, "Synchronizing time via NTP...");
    networking_ntp_init(nullptr);
    if (networking_ntp_wait_sync(60000) != 0) {
        ESP_LOGW(TAG, "NTP sync timed out, continuing anyway...");
    }

    // Get device MAC for client ID and topic
    char macStr[18];
    networking_get_mac_string(macStr);
    ESP_LOGI(TAG, "Device MAC: %s", macStr);

    // Create MQTT topic
    // Format: natKit/sending/Muse-{MAC}/data-bulk/BINARY/NatMuseBulkDataSchema
    char clientId[32];
    snprintf(clientId, sizeof(clientId), "Muse-%02X%02X%02X", 
             (uint8_t)macStr[9], (uint8_t)macStr[12], (uint8_t)macStr[15]);
    
    snprintf(g_mqttTopic, sizeof(g_mqttTopic),
             "natKit/sending/%s/data-bulk/BINARY/NatMuseBulkDataSchema", clientId);
    ESP_LOGI(TAG, "MQTT Topic: %s", g_mqttTopic);

    // Initialize MQTT
    ESP_LOGI(TAG, "Connecting to MQTT broker: %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    if (networking_mqtt_init(MQTT_BROKER_HOST, MQTT_BROKER_PORT, clientId) != 0) {
        ESP_LOGE(TAG, "Failed to initialize MQTT");
        return;
    }

    // Try to connect with longer timeout, but continue even if it fails
    // (MQTT client will auto-reconnect in background)
    if (networking_mqtt_connect(30000) != 0) {
        ESP_LOGW(TAG, "MQTT connection timed out, will retry in background");
    } else {
        ESP_LOGI(TAG, "MQTT connected successfully");
    }

    // IMPORTANT: Initialize BLE BEFORE creating publish task
    // The publish task allocates ~35KB buffer which would exhaust heap
    
    // Set up Muse callbacks
    auto& muse = MuseCppWrapper::getInstance();
    
    muse.setEegCallback(onEegData);
    muse.setAccelCallback(onAccelData);
    muse.setGyroCallback(onGyroData);
    muse.setStatusCallback(onStatusChange);

    // Initialize Muse controller (this initializes NimBLE)
    ESP_LOGI(TAG, "Initializing Muse controller...");
    if (muse.init(true, true, 60000) != 0) {
        ESP_LOGE(TAG, "Failed to initialize Muse controller");
        return;
    }

    // Start scanning for Muse device (this creates BLE host task)
    ESP_LOGI(TAG, "Starting Muse controller - scanning for device...");
    if (muse.start() != 0) {
        ESP_LOGE(TAG, "Failed to start Muse controller");
        return;
    }

    // Create publish task AFTER BLE is initialized
    // The task will allocate its buffer when first needed
    xTaskCreate(publishTask, "publish_task", 8192, nullptr, 5, &g_publishTaskHandle);

    ESP_LOGI(TAG, "natMuse started - waiting for Muse connection...");
}

/**
 * Callback for EEG data
 */
static void onEegData(muse_eeg_channel_t channel, const muse_eeg_data_t* data) {
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addEegData(timestamp, data->sequence, channel, data->samples);
}

/**
 * Callback for accelerometer data
 */
static void onAccelData(const muse_accel_data_t* data) {
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addAccelData(timestamp, data);
}

/**
 * Callback for gyroscope data
 */
static void onGyroData(const muse_gyro_data_t* data) {
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addGyroData(timestamp, data);
}

/**
 * Callback for Muse status changes
 */
static void onStatusChange(muse_status_t status) {
    const char* statusNames[] = {
        "DISCONNECTED", "SCANNING", "CONNECTING",
        "CONNECTED", "STREAMING", "ERROR"
    };
    ESP_LOGI(TAG, "Muse status: %s", statusNames[status]);
}

/**
 * Task that publishes bulk data when buffer is full
 */
static void publishTask(void* param) {
    ESP_LOGI(TAG, "Publish task started");

    // Use buffer size from authoritative schema
    static const size_t BUFFER_SIZE = nat::core::NatMuseBulkDataSchema::BINARY_BUFFER_SIZE;
    
    // Defer buffer allocation until first use to save memory during BLE init
    uint8_t* binaryBuffer = nullptr;
    
    while (true) {
        // Check if buffer is full
        if (g_dataBuffer.isFull()) {
            // Allocate buffer on first use
            if (binaryBuffer == nullptr) {
                ESP_LOGI(TAG, "Allocating publish buffer (%zu bytes)...", BUFFER_SIZE);
                binaryBuffer = new (std::nothrow) uint8_t[BUFFER_SIZE];
                if (binaryBuffer == nullptr) {
                    ESP_LOGE(TAG, "Failed to allocate publish buffer!");
                    g_dataBuffer.reset();  // Drop data
                    vTaskDelay(pdMS_TO_TICKS(1000));
                    continue;
                }
                ESP_LOGI(TAG, "Publish buffer allocated successfully");
            }
            
            ESP_LOGI(TAG, "Buffer full, encoding and publishing...");

            // Lock buffer and encode using authoritative schema serialization
            g_dataBuffer.lock();
            
            const nat::core::NatMuseBulkDataSchema& bulkSchema = g_dataBuffer.getBulkSchema();
            size_t encodedSize = bulkSchema.encodeToBytesInPlace(binaryBuffer, BUFFER_SIZE);
            
            // Reset buffer
            g_dataBuffer.reset();
            g_dataBuffer.unlock();

            // Verify encoding succeeded
            if (encodedSize == 0) {
                ESP_LOGE(TAG, "Failed to encode bulk data");
                continue;
            }

            // Publish to MQTT
            if (networking_mqtt_is_connected()) {
                int result = networking_mqtt_publish(g_mqttTopic, binaryBuffer, encodedSize, 0);
                if (result == 0) {
                    ESP_LOGI(TAG, "Published %zu bytes to MQTT", encodedSize);
                } else {
                    ESP_LOGE(TAG, "Failed to publish to MQTT");
                }
            } else {
                ESP_LOGW(TAG, "MQTT not connected, dropping data");
            }
        }

        // Small delay to avoid busy waiting
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    delete[] binaryBuffer;
    vTaskDelete(nullptr);
}
