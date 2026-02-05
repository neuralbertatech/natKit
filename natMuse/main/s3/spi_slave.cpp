/**
 * @file spi_slave.cpp
 * @brief SPI slave driver implementation for ESP32-S3
 */

#include "spi_slave.h"
#include "driver/spi_slave.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>

static const char* TAG = "spi_slave";

// Callback configuration
static spi_slave_config_t s_config = {};

// Last heartbeat time and status
static uint32_t s_last_heartbeat_time = 0;
static uint8_t s_muse_status = MUSE_STATUS_DISCONNECTED;

// Receive buffers (DMA-capable, word-aligned)
WORD_ALIGNED_ATTR static uint8_t s_rx_buffer[SPI_MAX_PACKET_SIZE];

// Task handle
static TaskHandle_t s_rx_task_handle = nullptr;

// Expected sequence number for packet loss detection
static uint8_t s_expected_seq = 0;

/**
 * @brief Process a received packet
 */
static void process_packet(const uint8_t* data, size_t len) {
    if (len < sizeof(spi_packet_header_t)) {
        ESP_LOGW(TAG, "Packet too short: %zu bytes", len);
        return;
    }

    const spi_packet_header_t* header = (const spi_packet_header_t*)data;
    const uint8_t* payload = data + sizeof(spi_packet_header_t);

    // Check sequence number for packet loss
    if (header->seq != s_expected_seq) {
        uint8_t lost = header->seq - s_expected_seq;
        ESP_LOGW(TAG, "Packet loss detected: expected seq %u, got %u (lost %u)",
                 s_expected_seq, header->seq, lost);
    }
    s_expected_seq = header->seq + 1;

    // Verify payload length
    if (len < sizeof(spi_packet_header_t) + header->length) {
        ESP_LOGW(TAG, "Incomplete packet: expected %u payload bytes, got %zu",
                 header->length, len - sizeof(spi_packet_header_t));
        return;
    }

    switch (header->type) {
        case PACKET_TYPE_EEG: {
            if (header->length != sizeof(spi_eeg_payload_t)) {
                ESP_LOGW(TAG, "Invalid EEG payload size: %u", header->length);
                break;
            }
            const spi_eeg_payload_t* eeg = (const spi_eeg_payload_t*)payload;
            if (s_config.on_eeg_data) {
                s_config.on_eeg_data(eeg->eeg_sequence, eeg->channel, eeg->samples);
            }
            break;
        }

        case PACKET_TYPE_ACCEL: {
            if (header->length != sizeof(spi_accel_payload_t)) {
                ESP_LOGW(TAG, "Invalid accel payload size: %u", header->length);
                break;
            }
            const spi_accel_payload_t* accel = (const spi_accel_payload_t*)payload;
            if (s_config.on_accel_data) {
                s_config.on_accel_data(accel->motion_sequence, accel->samples);
            }
            break;
        }

        case PACKET_TYPE_GYRO: {
            if (header->length != sizeof(spi_gyro_payload_t)) {
                ESP_LOGW(TAG, "Invalid gyro payload size: %u", header->length);
                break;
            }
            const spi_gyro_payload_t* gyro = (const spi_gyro_payload_t*)payload;
            if (s_config.on_gyro_data) {
                s_config.on_gyro_data(gyro->motion_sequence, gyro->samples);
            }
            break;
        }

        case PACKET_TYPE_STATUS: {
            if (header->length != sizeof(spi_status_payload_t)) {
                ESP_LOGW(TAG, "Invalid status payload size: %u", header->length);
                break;
            }
            const spi_status_payload_t* status = (const spi_status_payload_t*)payload;
            s_muse_status = status->status;
            if (s_config.on_status) {
                s_config.on_status(status->status);
            }
            break;
        }

        case PACKET_TYPE_HEARTBEAT: {
            if (header->length != sizeof(spi_heartbeat_payload_t)) {
                ESP_LOGW(TAG, "Invalid heartbeat payload size: %u", header->length);
                break;
            }
            const spi_heartbeat_payload_t* heartbeat = (const spi_heartbeat_payload_t*)payload;
            s_last_heartbeat_time = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
            if (s_config.on_heartbeat) {
                s_config.on_heartbeat(heartbeat->uptime_ms);
            }
            break;
        }

        default:
            ESP_LOGW(TAG, "Unknown packet type: 0x%02X", header->type);
            break;
    }
}

/**
 * @brief SPI receive task
 */
static void spi_rx_task(void* param) {
    ESP_LOGI(TAG, "SPI receive task started");

    spi_slave_transaction_t trans;
    memset(&trans, 0, sizeof(trans));

    while (true) {
        // Prepare transaction
        trans.length = SPI_MAX_PACKET_SIZE * 8;  // Length in bits
        trans.rx_buffer = s_rx_buffer;
        trans.tx_buffer = nullptr;

        // Wait for transaction from master
        esp_err_t ret = spi_slave_transmit(SPI2_HOST, &trans, portMAX_DELAY);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "SPI slave receive failed: %s", esp_err_to_name(ret));
            continue;
        }

        // Process received data
        size_t bytes_received = trans.trans_len / 8;
        if (bytes_received > 0) {
            process_packet(s_rx_buffer, bytes_received);
        }
    }
}

esp_err_t spi_slave_init(const spi_slave_config_t* config) {
    ESP_LOGI(TAG, "Initializing SPI slave...");

    if (config == nullptr) {
        return ESP_ERR_INVALID_ARG;
    }

    // Store configuration
    memcpy(&s_config, config, sizeof(spi_slave_config_t));

    // Configure GPIO for SPI slave
    gpio_config_t io_conf = {};
    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pin_bit_mask = (1ULL << S3_SPI_SCLK_PIN) | (1ULL << S3_SPI_MOSI_PIN) | (1ULL << S3_SPI_CS_PIN);
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    gpio_config(&io_conf);

    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pin_bit_mask = (1ULL << S3_SPI_MISO_PIN);
    gpio_config(&io_conf);

    // SPI bus configuration
    spi_bus_config_t bus_cfg = {};
    bus_cfg.mosi_io_num = S3_SPI_MOSI_PIN;
    bus_cfg.miso_io_num = S3_SPI_MISO_PIN;
    bus_cfg.sclk_io_num = S3_SPI_SCLK_PIN;
    bus_cfg.quadwp_io_num = -1;
    bus_cfg.quadhd_io_num = -1;
    bus_cfg.max_transfer_sz = SPI_MAX_TRANSFER_SIZE;

    // SPI slave configuration
    spi_slave_interface_config_t slave_cfg = {};
    slave_cfg.mode = 0;  // CPOL=0, CPHA=0
    slave_cfg.spics_io_num = S3_SPI_CS_PIN;
    slave_cfg.queue_size = 3;
    slave_cfg.flags = 0;
    slave_cfg.post_setup_cb = nullptr;
    slave_cfg.post_trans_cb = nullptr;

    // Initialize SPI slave
    esp_err_t ret = spi_slave_initialize(SPI2_HOST, &bus_cfg, &slave_cfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize SPI slave: %s", esp_err_to_name(ret));
        return ret;
    }

    // Create receive task
    BaseType_t task_ret = xTaskCreate(spi_rx_task, "spi_rx", 4096, nullptr, 10, &s_rx_task_handle);
    if (task_ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create SPI receive task");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "SPI slave initialized successfully");
    ESP_LOGI(TAG, "  MOSI: GPIO %d", S3_SPI_MOSI_PIN);
    ESP_LOGI(TAG, "  MISO: GPIO %d", S3_SPI_MISO_PIN);
    ESP_LOGI(TAG, "  SCLK: GPIO %d", S3_SPI_SCLK_PIN);
    ESP_LOGI(TAG, "  CS:   GPIO %d", S3_SPI_CS_PIN);

    return ESP_OK;
}

bool spi_slave_is_h2_connected(void) {
    uint32_t now = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
    return (now - s_last_heartbeat_time) < 5000;  // 5 second timeout
}

uint8_t spi_slave_get_muse_status(void) {
    return s_muse_status;
}
