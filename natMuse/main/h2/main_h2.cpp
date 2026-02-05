/**
 * @file main_h2.cpp
 * @brief ESP32-H2 entry point for natMuse BLE controller
 * 
 * This firmware runs on the ESP32-H2 and handles:
 * - BLE connection to Muse headband
 * - Decoding Muse data packets
 * - Transmitting decoded data to ESP32-S3 via SPI
 */

#include <cstdio>
#include <cstring>

#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "muse_controller.h"
#include "spi_master.h"
#include "spi_protocol.h"

static const char* TAG = "natMuse-H2";

// Forward declarations
static void onEegData(muse_eeg_channel_t channel, const muse_eeg_data_t* data);
static void onAccelData(const muse_accel_data_t* data);
static void onGyroData(const muse_gyro_data_t* data);
static void onStatusChange(muse_status_t status);
static void heartbeatTask(void* param);

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "   natMuse H2 - BLE Controller             ");
    ESP_LOGI(TAG, "===========================================");

    // Initialize NVS (required for BLE)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize SPI master (communication with S3)
    ESP_LOGI(TAG, "Initializing SPI master...");
    ret = spi_master_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize SPI master: %s", esp_err_to_name(ret));
        return;
    }

    // Send initial status to S3
    spi_master_send_status(MUSE_STATUS_DISCONNECTED);

    // Configure Muse controller
    muse_config_t config;
    muse_controller_get_default_config(&config);
    
    config.on_eeg_data = onEegData;
    config.on_accel_data = onAccelData;
    config.on_gyro_data = onGyroData;
    config.on_status_change = onStatusChange;
    config.enable_accelerometer = true;
    config.enable_gyroscope = true;
    config.scan_timeout_ms = 60000;  // 60 second scan timeout

    // Initialize Muse controller
    ESP_LOGI(TAG, "Initializing Muse controller...");
    int result = muse_controller_init(&config);
    if (result != 0) {
        ESP_LOGE(TAG, "Failed to initialize Muse controller: %d", result);
        return;
    }

    // Start scanning for Muse device
    ESP_LOGI(TAG, "Starting Muse controller - scanning for device...");
    result = muse_controller_start();
    if (result != 0) {
        ESP_LOGE(TAG, "Failed to start Muse controller: %d", result);
        return;
    }

    // Create heartbeat task to keep S3 informed we're alive
    xTaskCreate(heartbeatTask, "heartbeat", 2048, nullptr, 2, nullptr);

    ESP_LOGI(TAG, "natMuse H2 started - waiting for Muse connection...");
}

/**
 * Callback for EEG data - send to S3 via SPI
 */
static void onEegData(muse_eeg_channel_t channel, const muse_eeg_data_t* data) {
    esp_err_t ret = spi_master_send_eeg(data->sequence, (uint8_t)channel, data->samples);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to send EEG data: %s", esp_err_to_name(ret));
    }
}

/**
 * Callback for accelerometer data - send to S3 via SPI
 */
static void onAccelData(const muse_accel_data_t* data) {
    // Reorganize data into the format expected by SPI protocol
    // From: x[3], y[3], z[3] -> To: samples[3][3] where samples[i] = {x[i], y[i], z[i]}
    float samples[3][3];
    for (int i = 0; i < MUSE_MOTION_SAMPLES_PER_PACKET; i++) {
        samples[i][0] = data->x[i];
        samples[i][1] = data->y[i];
        samples[i][2] = data->z[i];
    }
    
    esp_err_t ret = spi_master_send_accel(data->sequence, samples);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to send accel data: %s", esp_err_to_name(ret));
    }
}

/**
 * Callback for gyroscope data - send to S3 via SPI
 */
static void onGyroData(const muse_gyro_data_t* data) {
    // Reorganize data into the format expected by SPI protocol
    float samples[3][3];
    for (int i = 0; i < MUSE_MOTION_SAMPLES_PER_PACKET; i++) {
        samples[i][0] = data->x[i];
        samples[i][1] = data->y[i];
        samples[i][2] = data->z[i];
    }
    
    esp_err_t ret = spi_master_send_gyro(data->sequence, samples);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to send gyro data: %s", esp_err_to_name(ret));
    }
}

/**
 * Callback for Muse status changes - notify S3
 */
static void onStatusChange(muse_status_t status) {
    const char* statusNames[] = {
        "DISCONNECTED", "SCANNING", "CONNECTING",
        "CONNECTED", "STREAMING", "ERROR"
    };
    ESP_LOGI(TAG, "Muse status: %s", statusNames[status]);
    
    // Send status to S3
    esp_err_t ret = spi_master_send_status((uint8_t)status);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to send status: %s", esp_err_to_name(ret));
    }
}

/**
 * Task that sends periodic heartbeats to S3
 */
static void heartbeatTask(void* param) {
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(1000));  // Every 1 second
        
        esp_err_t ret = spi_master_send_heartbeat();
        if (ret != ESP_OK) {
            ESP_LOGD(TAG, "Heartbeat send failed: %s", esp_err_to_name(ret));
        }
    }
}
