/**
 * @file spi_slave.h
 * @brief SPI slave driver for ESP32-S3 to receive data from ESP32-H2
 * 
 * This module handles SPI slave initialization and reception of
 * Muse data packets from the H2 BLE controller.
 */

#ifndef SPI_SLAVE_H
#define SPI_SLAVE_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "spi_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Callback for received EEG data
 * 
 * @param eeg_sequence Muse EEG sequence number
 * @param channel EEG channel (0-3)
 * @param samples Array of 12 EEG samples in microvolts
 */
typedef void (*spi_slave_eeg_cb_t)(uint16_t eeg_sequence, uint8_t channel, const float* samples);

/**
 * @brief Callback for received accelerometer data
 * 
 * @param motion_sequence Muse motion sequence number
 * @param samples Array of 3 samples × (x, y, z)
 */
typedef void (*spi_slave_accel_cb_t)(uint16_t motion_sequence, const float samples[3][3]);

/**
 * @brief Callback for received gyroscope data
 * 
 * @param motion_sequence Muse motion sequence number
 * @param samples Array of 3 samples × (x, y, z)
 */
typedef void (*spi_slave_gyro_cb_t)(uint16_t motion_sequence, const float samples[3][3]);

/**
 * @brief Callback for status updates
 * 
 * @param status Muse connection status (MUSE_STATUS_*)
 */
typedef void (*spi_slave_status_cb_t)(uint8_t status);

/**
 * @brief Callback for heartbeat received
 * 
 * @param uptime_ms H2 uptime in milliseconds
 */
typedef void (*spi_slave_heartbeat_cb_t)(uint32_t uptime_ms);

/**
 * @brief SPI slave configuration
 */
typedef struct {
    spi_slave_eeg_cb_t on_eeg_data;
    spi_slave_accel_cb_t on_accel_data;
    spi_slave_gyro_cb_t on_gyro_data;
    spi_slave_status_cb_t on_status;
    spi_slave_heartbeat_cb_t on_heartbeat;
} spi_slave_config_t;

/**
 * @brief Initialize SPI slave interface and start receive task
 * 
 * Configures SPI2 as slave with the pins defined in spi_protocol.h
 * and creates a FreeRTOS task to handle incoming packets.
 * 
 * @param config Callback configuration
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_slave_init(const spi_slave_config_t* config);

/**
 * @brief Check if H2 is connected (received heartbeat recently)
 * 
 * @return true if heartbeat received within last 5 seconds
 */
bool spi_slave_is_h2_connected(void);

/**
 * @brief Get last received H2 status
 * 
 * @return Last received Muse status from H2
 */
uint8_t spi_slave_get_muse_status(void);

#ifdef __cplusplus
}
#endif

#endif // SPI_SLAVE_H
