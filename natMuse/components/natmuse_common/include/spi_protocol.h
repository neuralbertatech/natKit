/**
 * @file spi_protocol.h
 * @brief SPI communication protocol between ESP32-H2 (BLE) and ESP32-S3 (WiFi)
 * 
 * This header defines the packet format and data structures for inter-chip
 * communication. The H2 acts as SPI master, transmitting decoded Muse data
 * to the S3 which handles WiFi/MQTT publishing.
 */

#ifndef SPI_PROTOCOL_H
#define SPI_PROTOCOL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// SPI Configuration
#define SPI_CLOCK_SPEED_HZ      10000000    // 10 MHz
#define SPI_MAX_TRANSFER_SIZE   128         // Max bytes per transaction

// H2 SPI pins (SPI2)
#define H2_SPI_MOSI_PIN         5
#define H2_SPI_MISO_PIN         0
#define H2_SPI_SCLK_PIN         4
#define H2_SPI_CS_PIN           1

// S3 SPI pins (SPI2)
#define S3_SPI_MOSI_PIN         11
#define S3_SPI_MISO_PIN         13
#define S3_SPI_SCLK_PIN         12
#define S3_SPI_CS_PIN           10

// Packet types
#define PACKET_TYPE_EEG         0x01    // EEG channel data
#define PACKET_TYPE_ACCEL       0x02    // Accelerometer data
#define PACKET_TYPE_GYRO        0x03    // Gyroscope data
#define PACKET_TYPE_STATUS      0x04    // Muse connection status
#define PACKET_TYPE_HEARTBEAT   0x05    // Keep-alive ping

// Muse channel identifiers (matches muse_eeg_channel_t)
#define MUSE_CHANNEL_TP9        0
#define MUSE_CHANNEL_AF7        1
#define MUSE_CHANNEL_AF8        2
#define MUSE_CHANNEL_TP10       3

// Muse status values (matches muse_status_t)
#define MUSE_STATUS_DISCONNECTED    0
#define MUSE_STATUS_SCANNING        1
#define MUSE_STATUS_CONNECTING      2
#define MUSE_STATUS_CONNECTED       3
#define MUSE_STATUS_STREAMING       4
#define MUSE_STATUS_ERROR           5

// Number of samples per packet from Muse
#define EEG_SAMPLES_PER_PACKET      12
#define MOTION_SAMPLES_PER_PACKET   3

/**
 * @brief SPI packet header
 * All packets start with this 4-byte header
 */
typedef struct __attribute__((packed)) {
    uint8_t type;       // PACKET_TYPE_*
    uint8_t seq;        // Rolling sequence number (0-255)
    uint16_t length;    // Payload length in bytes (little-endian)
} spi_packet_header_t;

/**
 * @brief EEG data payload
 * Contains one channel's worth of EEG samples (12 samples)
 * Total size: 2 + 1 + 1 + 48 = 52 bytes
 */
typedef struct __attribute__((packed)) {
    uint16_t eeg_sequence;              // Muse EEG sequence number
    uint8_t channel;                    // Channel: 0=TP9, 1=AF7, 2=AF8, 3=TP10
    uint8_t reserved;                   // Padding for alignment
    float samples[EEG_SAMPLES_PER_PACKET];  // 12 EEG samples in microvolts
} spi_eeg_payload_t;

/**
 * @brief Accelerometer data payload
 * Contains 3 samples of XYZ acceleration
 * Total size: 2 + 2 + 36 = 40 bytes
 */
typedef struct __attribute__((packed)) {
    uint16_t motion_sequence;           // Muse motion sequence number
    uint16_t reserved;                  // Padding for alignment
    float samples[MOTION_SAMPLES_PER_PACKET][3];  // 3 samples × (x, y, z) in g
} spi_accel_payload_t;

/**
 * @brief Gyroscope data payload
 * Contains 3 samples of XYZ angular velocity
 * Total size: 2 + 2 + 36 = 40 bytes
 */
typedef struct __attribute__((packed)) {
    uint16_t motion_sequence;           // Muse motion sequence number
    uint16_t reserved;                  // Padding for alignment
    float samples[MOTION_SAMPLES_PER_PACKET][3];  // 3 samples × (x, y, z) in deg/s
} spi_gyro_payload_t;

/**
 * @brief Status update payload
 * Sent when Muse connection status changes
 * Total size: 1 + 3 = 4 bytes
 */
typedef struct __attribute__((packed)) {
    uint8_t status;                     // MUSE_STATUS_*
    uint8_t reserved[3];                // Padding
} spi_status_payload_t;

/**
 * @brief Heartbeat payload
 * Sent periodically to indicate H2 is alive
 * Total size: 4 bytes
 */
typedef struct __attribute__((packed)) {
    uint32_t uptime_ms;                 // H2 uptime in milliseconds
} spi_heartbeat_payload_t;

// Complete packet sizes (header + payload)
#define SPI_EEG_PACKET_SIZE     (sizeof(spi_packet_header_t) + sizeof(spi_eeg_payload_t))
#define SPI_ACCEL_PACKET_SIZE   (sizeof(spi_packet_header_t) + sizeof(spi_accel_payload_t))
#define SPI_GYRO_PACKET_SIZE    (sizeof(spi_packet_header_t) + sizeof(spi_gyro_payload_t))
#define SPI_STATUS_PACKET_SIZE  (sizeof(spi_packet_header_t) + sizeof(spi_status_payload_t))
#define SPI_HEARTBEAT_PACKET_SIZE (sizeof(spi_packet_header_t) + sizeof(spi_heartbeat_payload_t))

// Maximum packet size
#define SPI_MAX_PACKET_SIZE     SPI_EEG_PACKET_SIZE

#ifdef __cplusplus
}
#endif

#endif // SPI_PROTOCOL_H
