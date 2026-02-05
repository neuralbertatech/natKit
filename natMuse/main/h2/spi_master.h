/**
 * @file spi_master.h
 * @brief SPI master driver for ESP32-H2 to communicate with ESP32-S3
 * 
 * This module handles SPI master initialization and transmission of
 * Muse data packets to the S3 for WiFi/MQTT publishing.
 */

#ifndef SPI_MASTER_H
#define SPI_MASTER_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"
#include "spi_protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize SPI master interface
 * 
 * Configures SPI2 as master with the pins defined in spi_protocol.h
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_init(void);

/**
 * @brief Send EEG data packet to S3
 * 
 * @param eeg_sequence Muse EEG sequence number
 * @param channel EEG channel (0-3 for TP9/AF7/AF8/TP10)
 * @param samples Array of 12 EEG samples in microvolts
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_send_eeg(uint16_t eeg_sequence, uint8_t channel, const float* samples);

/**
 * @brief Send accelerometer data packet to S3
 * 
 * @param motion_sequence Muse motion sequence number
 * @param samples Array of 3 samples, each with x, y, z values in g
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_send_accel(uint16_t motion_sequence, const float samples[3][3]);

/**
 * @brief Send gyroscope data packet to S3
 * 
 * @param motion_sequence Muse motion sequence number
 * @param samples Array of 3 samples, each with x, y, z values in deg/s
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_send_gyro(uint16_t motion_sequence, const float samples[3][3]);

/**
 * @brief Send status update to S3
 * 
 * @param status Muse connection status (MUSE_STATUS_*)
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_send_status(uint8_t status);

/**
 * @brief Send heartbeat to S3
 * 
 * @return ESP_OK on success, error code otherwise
 */
esp_err_t spi_master_send_heartbeat(void);

#ifdef __cplusplus
}
#endif

#endif // SPI_MASTER_H
