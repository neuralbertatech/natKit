/**
 * @file spi_master.cpp
 * @brief SPI master driver implementation for ESP32-H2
 */

#include "spi_master.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <cstring>

static const char* TAG = "spi_master";

// SPI device handle
static spi_device_handle_t s_spi_device = nullptr;

// Sequence number for packets (rolling 0-255)
static uint8_t s_packet_seq = 0;

// Mutex to protect SPI transactions
static SemaphoreHandle_t s_spi_mutex = nullptr;

// Transmit buffer (statically allocated to avoid heap fragmentation)
static uint8_t s_tx_buffer[SPI_MAX_PACKET_SIZE];

/**
 * @brief Build packet header
 */
static void build_header(spi_packet_header_t* header, uint8_t type, uint16_t payload_len) {
    header->type = type;
    header->seq = s_packet_seq++;
    header->length = payload_len;
}

/**
 * @brief Transmit a packet over SPI
 */
static esp_err_t spi_transmit(const void* data, size_t len) {
    if (s_spi_device == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }

    spi_transaction_t trans = {};
    trans.length = len * 8;  // Length in bits
    trans.tx_buffer = data;
    trans.rx_buffer = nullptr;

    esp_err_t ret = spi_device_polling_transmit(s_spi_device, &trans);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI transmit failed: %s", esp_err_to_name(ret));
    }
    
    return ret;
}

esp_err_t spi_master_init(void) {
    ESP_LOGI(TAG, "Initializing SPI master...");

    // Create mutex
    s_spi_mutex = xSemaphoreCreateMutex();
    if (s_spi_mutex == nullptr) {
        ESP_LOGE(TAG, "Failed to create SPI mutex");
        return ESP_ERR_NO_MEM;
    }

    // SPI bus configuration
    spi_bus_config_t bus_cfg = {};
    bus_cfg.mosi_io_num = H2_SPI_MOSI_PIN;
    bus_cfg.miso_io_num = H2_SPI_MISO_PIN;
    bus_cfg.sclk_io_num = H2_SPI_SCLK_PIN;
    bus_cfg.quadwp_io_num = -1;
    bus_cfg.quadhd_io_num = -1;
    bus_cfg.max_transfer_sz = SPI_MAX_TRANSFER_SIZE;

    // Initialize SPI bus
    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize SPI bus: %s", esp_err_to_name(ret));
        return ret;
    }

    // SPI device configuration
    spi_device_interface_config_t dev_cfg = {};
    dev_cfg.clock_speed_hz = SPI_CLOCK_SPEED_HZ;
    dev_cfg.mode = 0;  // CPOL=0, CPHA=0
    dev_cfg.spics_io_num = H2_SPI_CS_PIN;
    dev_cfg.queue_size = 1;
    dev_cfg.pre_cb = nullptr;
    dev_cfg.post_cb = nullptr;

    // Add device to bus
    ret = spi_bus_add_device(SPI2_HOST, &dev_cfg, &s_spi_device);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add SPI device: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "SPI master initialized successfully");
    ESP_LOGI(TAG, "  MOSI: GPIO %d", H2_SPI_MOSI_PIN);
    ESP_LOGI(TAG, "  MISO: GPIO %d", H2_SPI_MISO_PIN);
    ESP_LOGI(TAG, "  SCLK: GPIO %d", H2_SPI_SCLK_PIN);
    ESP_LOGI(TAG, "  CS:   GPIO %d", H2_SPI_CS_PIN);
    ESP_LOGI(TAG, "  Clock: %d Hz", SPI_CLOCK_SPEED_HZ);

    return ESP_OK;
}

esp_err_t spi_master_send_eeg(uint16_t eeg_sequence, uint8_t channel, const float* samples) {
    if (xSemaphoreTake(s_spi_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Build packet in transmit buffer
    spi_packet_header_t* header = (spi_packet_header_t*)s_tx_buffer;
    spi_eeg_payload_t* payload = (spi_eeg_payload_t*)(s_tx_buffer + sizeof(spi_packet_header_t));

    build_header(header, PACKET_TYPE_EEG, sizeof(spi_eeg_payload_t));
    
    payload->eeg_sequence = eeg_sequence;
    payload->channel = channel;
    payload->reserved = 0;
    memcpy(payload->samples, samples, sizeof(float) * EEG_SAMPLES_PER_PACKET);

    esp_err_t ret = spi_transmit(s_tx_buffer, SPI_EEG_PACKET_SIZE);
    
    xSemaphoreGive(s_spi_mutex);
    return ret;
}

esp_err_t spi_master_send_accel(uint16_t motion_sequence, const float samples[3][3]) {
    if (xSemaphoreTake(s_spi_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Build packet in transmit buffer
    spi_packet_header_t* header = (spi_packet_header_t*)s_tx_buffer;
    spi_accel_payload_t* payload = (spi_accel_payload_t*)(s_tx_buffer + sizeof(spi_packet_header_t));

    build_header(header, PACKET_TYPE_ACCEL, sizeof(spi_accel_payload_t));
    
    payload->motion_sequence = motion_sequence;
    payload->reserved = 0;
    memcpy(payload->samples, samples, sizeof(float) * MOTION_SAMPLES_PER_PACKET * 3);

    esp_err_t ret = spi_transmit(s_tx_buffer, SPI_ACCEL_PACKET_SIZE);
    
    xSemaphoreGive(s_spi_mutex);
    return ret;
}

esp_err_t spi_master_send_gyro(uint16_t motion_sequence, const float samples[3][3]) {
    if (xSemaphoreTake(s_spi_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Build packet in transmit buffer
    spi_packet_header_t* header = (spi_packet_header_t*)s_tx_buffer;
    spi_gyro_payload_t* payload = (spi_gyro_payload_t*)(s_tx_buffer + sizeof(spi_packet_header_t));

    build_header(header, PACKET_TYPE_GYRO, sizeof(spi_gyro_payload_t));
    
    payload->motion_sequence = motion_sequence;
    payload->reserved = 0;
    memcpy(payload->samples, samples, sizeof(float) * MOTION_SAMPLES_PER_PACKET * 3);

    esp_err_t ret = spi_transmit(s_tx_buffer, SPI_GYRO_PACKET_SIZE);
    
    xSemaphoreGive(s_spi_mutex);
    return ret;
}

esp_err_t spi_master_send_status(uint8_t status) {
    if (xSemaphoreTake(s_spi_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Build packet in transmit buffer
    spi_packet_header_t* header = (spi_packet_header_t*)s_tx_buffer;
    spi_status_payload_t* payload = (spi_status_payload_t*)(s_tx_buffer + sizeof(spi_packet_header_t));

    build_header(header, PACKET_TYPE_STATUS, sizeof(spi_status_payload_t));
    
    payload->status = status;
    memset(payload->reserved, 0, sizeof(payload->reserved));

    esp_err_t ret = spi_transmit(s_tx_buffer, SPI_STATUS_PACKET_SIZE);
    
    xSemaphoreGive(s_spi_mutex);
    return ret;
}

esp_err_t spi_master_send_heartbeat(void) {
    if (xSemaphoreTake(s_spi_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ESP_ERR_TIMEOUT;
    }

    // Build packet in transmit buffer
    spi_packet_header_t* header = (spi_packet_header_t*)s_tx_buffer;
    spi_heartbeat_payload_t* payload = (spi_heartbeat_payload_t*)(s_tx_buffer + sizeof(spi_packet_header_t));

    build_header(header, PACKET_TYPE_HEARTBEAT, sizeof(spi_heartbeat_payload_t));
    
    payload->uptime_ms = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);

    esp_err_t ret = spi_transmit(s_tx_buffer, SPI_HEARTBEAT_PACKET_SIZE);
    
    xSemaphoreGive(s_spi_mutex);
    return ret;
}
