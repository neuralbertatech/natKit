#include "muse_protocol.h"
#include <string.h>

// Helper to convert 16-bit big-endian to signed int
static int16_t be16_to_int16(const uint8_t *data) {
    return (int16_t)((data[0] << 8) | data[1]);
}

bool muse_decode_eeg(const uint8_t *data, muse_eeg_packet_t *packet) {
    if (!data || !packet) {
        return false;
    }
    
    // First 2 bytes are packet number (big-endian)
    packet->packet_num = (data[0] << 8) | data[1];
    
    // Remaining 18 bytes contain 12 samples packed as 12-bit values
    // Each 3 bytes contain 2 samples
    int sample_idx = 0;
    for (int i = 2; i < MUSE_PACKET_SIZE && sample_idx < MUSE_EEG_SAMPLES; i += 3) {
        // Unpack two 12-bit values from 3 bytes
        uint16_t val1 = (data[i] << 4) | (data[i + 1] >> 4);
        uint16_t val2 = ((data[i + 1] & 0x0F) << 8) | data[i + 2];
        
        // Convert to microvolts (centered at 0x800)
        packet->samples[sample_idx++] = ((float)val1 - 0x800) * MUSE_EEG_SCALE;
        packet->samples[sample_idx++] = ((float)val2 - 0x800) * MUSE_EEG_SCALE;
    }
    
    return true;
}

bool muse_decode_accel(const uint8_t *data, muse_accel_packet_t *packet) {
    if (!data || !packet) {
        return false;
    }
    
    // First 2 bytes are packet number
    packet->packet_num = (data[0] << 8) | data[1];
    
    // 3 samples, each with X, Y, Z as 16-bit big-endian values
    for (int i = 0; i < MUSE_MOTION_SAMPLES; i++) {
        int offset = 2 + (i * 6);  // 6 bytes per sample (3 axes * 2 bytes)
        
        packet->x[i] = (float)be16_to_int16(&data[offset]) * MUSE_ACCEL_SCALE;
        packet->y[i] = (float)be16_to_int16(&data[offset + 2]) * MUSE_ACCEL_SCALE;
        packet->z[i] = (float)be16_to_int16(&data[offset + 4]) * MUSE_ACCEL_SCALE;
    }
    
    return true;
}

bool muse_decode_gyro(const uint8_t *data, muse_gyro_packet_t *packet) {
    if (!data || !packet) {
        return false;
    }
    
    // First 2 bytes are packet number
    packet->packet_num = (data[0] << 8) | data[1];
    
    // 3 samples, each with X, Y, Z as 16-bit big-endian values
    for (int i = 0; i < MUSE_MOTION_SAMPLES; i++) {
        int offset = 2 + (i * 6);
        
        packet->x[i] = (float)be16_to_int16(&data[offset]) * MUSE_GYRO_SCALE;
        packet->y[i] = (float)be16_to_int16(&data[offset + 2]) * MUSE_GYRO_SCALE;
        packet->z[i] = (float)be16_to_int16(&data[offset + 4]) * MUSE_GYRO_SCALE;
    }
    
    return true;
}

const char* muse_get_channel_name(uint16_t char_uuid) {
    switch (char_uuid) {
        case MUSE_CHAR_CONTROL:   return "CONTROL";
        case MUSE_CHAR_TP9:       return "TP9";
        case MUSE_CHAR_AF7:       return "AF7";
        case MUSE_CHAR_AF8:       return "AF8";
        case MUSE_CHAR_TP10:      return "TP10";
        case MUSE_CHAR_RIGHT_AUX: return "AUX";
        case MUSE_CHAR_GYRO:      return "GYRO";
        case MUSE_CHAR_ACCEL:     return "ACCEL";
        case MUSE_CHAR_PPG0:      return "PPG0";
        case MUSE_CHAR_PPG1:      return "PPG1";
        case MUSE_CHAR_PPG2:      return "PPG2";
        default:                  return "UNKNOWN";
    }
}

void muse_build_char_uuid(uint16_t char_id, uint8_t *uuid_128) {
    // Base UUID in little-endian: 273e****-4c4d-454d-96be-f03bac821358
    static const uint8_t base_uuid[16] = {
        0x58, 0x13, 0x82, 0xac, 0x3b, 0xf0, 0xbe, 0x96,
        0x4d, 0x45, 0x4d, 0x4c, 0x00, 0x00, 0x3e, 0x27
    };
    
    memcpy(uuid_128, base_uuid, 16);
    
    // Insert 16-bit characteristic ID at bytes 12-13 (little-endian)
    uuid_128[12] = char_id & 0xFF;
    uuid_128[13] = (char_id >> 8) & 0xFF;
}
