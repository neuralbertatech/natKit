#ifndef MUSE_CONTROLLER_H
#define MUSE_CONTROLLER_H

#include <stdint.h>
#include <stdbool.h>

/**
 * Muse Controller Library
 * 
 * Simple high-level API for connecting to and streaming data from Muse headbands.
 * 
 * Usage:
 *   1. Call muse_controller_init() with your callbacks
 *   2. Call muse_controller_start() to begin scanning and streaming
 *   3. Receive data through your callbacks
 *   4. Call muse_controller_stop() when done
 */

// EEG channel identifiers
typedef enum {
    MUSE_EEG_TP9 = 0,    // Left ear
    MUSE_EEG_AF7 = 1,    // Left forehead  
    MUSE_EEG_AF8 = 2,    // Right forehead
    MUSE_EEG_TP10 = 3,   // Right ear
    MUSE_EEG_COUNT = 4
} muse_eeg_channel_t;

// Connection status
typedef enum {
    MUSE_STATUS_DISCONNECTED = 0,
    MUSE_STATUS_SCANNING,
    MUSE_STATUS_CONNECTING,
    MUSE_STATUS_CONNECTED,
    MUSE_STATUS_STREAMING,
    MUSE_STATUS_ERROR
} muse_status_t;

// EEG data packet (12 samples at 256 Hz)
#define MUSE_EEG_SAMPLES_PER_PACKET 12

typedef struct {
    uint16_t sequence;                              // Packet sequence number
    float samples[MUSE_EEG_SAMPLES_PER_PACKET];     // Samples in microvolts
} muse_eeg_data_t;

// Accelerometer data (3 samples at 52 Hz)
#define MUSE_MOTION_SAMPLES_PER_PACKET 3

typedef struct {
    uint16_t sequence;
    float x[MUSE_MOTION_SAMPLES_PER_PACKET];  // In g
    float y[MUSE_MOTION_SAMPLES_PER_PACKET];
    float z[MUSE_MOTION_SAMPLES_PER_PACKET];
} muse_accel_data_t;

// Gyroscope data (3 samples at 52 Hz)
typedef struct {
    uint16_t sequence;
    float x[MUSE_MOTION_SAMPLES_PER_PACKET];  // In degrees/second
    float y[MUSE_MOTION_SAMPLES_PER_PACKET];
    float z[MUSE_MOTION_SAMPLES_PER_PACKET];
} muse_gyro_data_t;

/**
 * Callback function types
 */
typedef void (*muse_eeg_callback_t)(muse_eeg_channel_t channel, const muse_eeg_data_t *data);
typedef void (*muse_accel_callback_t)(const muse_accel_data_t *data);
typedef void (*muse_gyro_callback_t)(const muse_gyro_data_t *data);
typedef void (*muse_status_callback_t)(muse_status_t status);

/**
 * Configuration for the Muse controller
 */
typedef struct {
    // Callbacks (set to NULL if not needed)
    muse_eeg_callback_t on_eeg_data;
    muse_accel_callback_t on_accel_data;
    muse_gyro_callback_t on_gyro_data;
    muse_status_callback_t on_status_change;
    
    // Options
    bool enable_accelerometer;   // Default: true
    bool enable_gyroscope;       // Default: true
    uint32_t scan_timeout_ms;    // Default: 30000 (30 seconds)
} muse_config_t;

/**
 * Get default configuration
 */
void muse_controller_get_default_config(muse_config_t *config);

/**
 * Initialize the Muse controller
 * Must be called before any other functions
 * 
 * @param config Configuration with callbacks and options
 * @return 0 on success, negative error code on failure
 */
int muse_controller_init(const muse_config_t *config);

/**
 * Start scanning for and connecting to a Muse device
 * Will automatically begin streaming once connected
 * 
 * @return 0 on success, negative error code on failure
 */
int muse_controller_start(void);

/**
 * Stop streaming and disconnect from the Muse
 * 
 * @return 0 on success
 */
int muse_controller_stop(void);

/**
 * Get current connection status
 */
muse_status_t muse_controller_get_status(void);

/**
 * Check if currently streaming data
 */
bool muse_controller_is_streaming(void);

/**
 * Get the name of an EEG channel
 */
const char* muse_controller_get_channel_name(muse_eeg_channel_t channel);

#endif // MUSE_CONTROLLER_H
