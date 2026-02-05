/**
 * @file main_s3.cpp
 * @brief ESP32-S3 entry point for natMuse WiFi controller
 * 
 * This firmware runs on the ESP32-S3 and handles:
 * - Receiving Muse data from ESP32-H2 via SPI
 * - Adding NTP timestamps to received data
 * - Buffering data samples
 * - Publishing to MQTT via WiFi
 */

#include <cstdio>
#include <cstring>
#include <new>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "spi_slave.h"
#include "spi_protocol.h"
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

static const char* TAG = "natMuse-S3";

// Global data buffer
static MuseDataBuffer g_dataBuffer;

// MQTT topic for bulk data
static char g_mqttTopic[128];

// Task handles
static TaskHandle_t g_publishTaskHandle = nullptr;

// Muse status from H2
static uint8_t g_museStatus = MUSE_STATUS_DISCONNECTED;

// Forward declarations
static void publishTask(void* param);
static void onEegData(uint16_t eeg_sequence, uint8_t channel, const float* samples);
static void onAccelData(uint16_t motion_sequence, const float samples[3][3]);
static void onGyroData(uint16_t motion_sequence, const float samples[3][3]);
static void onStatus(uint8_t status);
static void onHeartbeat(uint32_t uptime_ms);

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "   natMuse S3 - WiFi Controller            ");
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

    // Create publish task
    xTaskCreate(publishTask, "publish_task", 8192, nullptr, 5, &g_publishTaskHandle);

    // Configure SPI slave callbacks
    spi_slave_config_t spi_config = {};
    spi_config.on_eeg_data = onEegData;
    spi_config.on_accel_data = onAccelData;
    spi_config.on_gyro_data = onGyroData;
    spi_config.on_status = onStatus;
    spi_config.on_heartbeat = onHeartbeat;

    // Initialize SPI slave (this creates the receive task)
    ESP_LOGI(TAG, "Initializing SPI slave...");
    esp_err_t ret = spi_slave_init(&spi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize SPI slave: %s", esp_err_to_name(ret));
        return;
    }

    ESP_LOGI(TAG, "natMuse S3 started - waiting for data from H2...");
}

/**
 * Callback for EEG data received from H2
 */
static void onEegData(uint16_t eeg_sequence, uint8_t channel, const float* samples) {
    // Add NTP timestamp and store in buffer
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addEegData(timestamp, eeg_sequence, channel, samples);
}

/**
 * Callback for accelerometer data received from H2
 */
static void onAccelData(uint16_t motion_sequence, const float samples[3][3]) {
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addAccelData(timestamp, motion_sequence, samples);
}

/**
 * Callback for gyroscope data received from H2
 */
static void onGyroData(uint16_t motion_sequence, const float samples[3][3]) {
    uint64_t timestamp = networking_get_time_us();
    g_dataBuffer.addGyroData(timestamp, motion_sequence, samples);
}

/**
 * Callback for status updates from H2
 */
static void onStatus(uint8_t status) {
    const char* statusNames[] = {
        "DISCONNECTED", "SCANNING", "CONNECTING",
        "CONNECTED", "STREAMING", "ERROR"
    };
    
    if (status != g_museStatus) {
        g_museStatus = status;
        ESP_LOGI(TAG, "Muse status (from H2): %s", 
                 status < 6 ? statusNames[status] : "UNKNOWN");
    }
}

/**
 * Callback for heartbeat from H2
 */
static void onHeartbeat(uint32_t uptime_ms) {
    // Just log periodically (every ~10 seconds)
    static uint32_t lastLog = 0;
    uint32_t now = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
    if (now - lastLog > 10000) {
        ESP_LOGD(TAG, "H2 heartbeat: uptime %lu ms", (unsigned long)uptime_ms);
        lastLog = now;
    }
}

/**
 * Task that publishes bulk data when buffer is full
 */
static void publishTask(void* param) {
    ESP_LOGI(TAG, "Publish task started");

    // Use buffer size from authoritative schema
    static const size_t BUFFER_SIZE = nat::core::NatMuseBulkDataSchema::BINARY_BUFFER_SIZE;
    
    // Defer buffer allocation until first use to save memory during init
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
