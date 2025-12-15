#ifndef MUSE_PROTOCOL_H
#define MUSE_PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>

// Muse GATT Service UUID: 273e0001-4c4d-454d-96be-f03bac821358
// UUIDs are stored in little-endian format for ESP-IDF
#define MUSE_SERVICE_UUID_128 \
    { 0x58, 0x13, 0x82, 0xac, 0x3b, 0xf0, 0xbe, 0x96, \
      0x4d, 0x45, 0x4d, 0x4c, 0x01, 0x00, 0x3e, 0x27 }

// Characteristic UUIDs (16-bit portion that varies)
#define MUSE_CHAR_CONTROL       0x0001  // Stream toggle / commands
#define MUSE_CHAR_TP9           0x0003  // EEG Left ear
#define MUSE_CHAR_AF7           0x0004  // EEG Left forehead
#define MUSE_CHAR_AF8           0x0005  // EEG Right forehead
#define MUSE_CHAR_TP10          0x0006  // EEG Right ear
#define MUSE_CHAR_RIGHT_AUX     0x0007  // EEG Right aux (optional)
#define MUSE_CHAR_GYRO          0x0009  // Gyroscope
#define MUSE_CHAR_ACCEL         0x000A  // Accelerometer
#define MUSE_CHAR_PPG0          0x000F  // PPG channel 0 (Muse 2/S only)
#define MUSE_CHAR_PPG1          0x0010  // PPG channel 1
#define MUSE_CHAR_PPG2          0x0011  // PPG channel 2

// Data packet sizes
#define MUSE_PACKET_SIZE        20
#define MUSE_EEG_SAMPLES        12      // 12 samples per EEG packet
#define MUSE_MOTION_SAMPLES     3       // 3 samples per accel/gyro packet

// Scale factors
#define MUSE_EEG_SCALE          (125.0 / 256.0)  // Convert to microvolts
#define MUSE_ACCEL_SCALE        (1.0 / 16384.0)  // Convert to g
#define MUSE_GYRO_SCALE         0.007476         // Convert to deg/s

// Internal EEG channel indices (includes AUX)
typedef enum {
    MUSE_CHANNEL_TP9 = 0,
    MUSE_CHANNEL_AF7 = 1,
    MUSE_CHANNEL_AF8 = 2,
    MUSE_CHANNEL_TP10 = 3,
    MUSE_CHANNEL_AUX = 4,
    MUSE_CHANNEL_COUNT = 5
} muse_protocol_channel_t;

// Decoded EEG data
typedef struct {
    uint16_t packet_num;
    float samples[MUSE_EEG_SAMPLES];  // 12 samples in microvolts
} muse_eeg_packet_t;

// Decoded accelerometer data
typedef struct {
    uint16_t packet_num;
    float x[MUSE_MOTION_SAMPLES];  // 3 samples in g
    float y[MUSE_MOTION_SAMPLES];
    float z[MUSE_MOTION_SAMPLES];
} muse_accel_packet_t;

// Decoded gyroscope data
typedef struct {
    uint16_t packet_num;
    float x[MUSE_MOTION_SAMPLES];  // 3 samples in deg/s
    float y[MUSE_MOTION_SAMPLES];
    float z[MUSE_MOTION_SAMPLES];
} muse_gyro_packet_t;

/**
 * Decode raw EEG packet from Muse
 * @param data Raw 20-byte packet
 * @param packet Output decoded packet
 * @return true on success
 */
bool muse_decode_eeg(const uint8_t *data, muse_eeg_packet_t *packet);

/**
 * Decode raw accelerometer packet from Muse
 * @param data Raw 20-byte packet
 * @param packet Output decoded packet
 * @return true on success
 */
bool muse_decode_accel(const uint8_t *data, muse_accel_packet_t *packet);

/**
 * Decode raw gyroscope packet from Muse
 * @param data Raw 20-byte packet
 * @param packet Output decoded packet
 * @return true on success
 */
bool muse_decode_gyro(const uint8_t *data, muse_gyro_packet_t *packet);

/**
 * Get characteristic UUID (16-bit portion) name as string
 * @param char_uuid 16-bit characteristic identifier
 * @return Static string name
 */
const char* muse_get_channel_name(uint16_t char_uuid);

/**
 * Build full 128-bit UUID from 16-bit characteristic ID
 * @param char_id 16-bit characteristic ID (e.g., MUSE_CHAR_TP9)
 * @param uuid_128 Output 16-byte UUID array
 */
void muse_build_char_uuid(uint16_t char_id, uint8_t *uuid_128);

#endif // MUSE_PROTOCOL_H
