#ifndef MUSE_DATA_BUFFER_HPP
#define MUSE_DATA_BUFFER_HPP

#include <cstdint>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#include <libnatkit-core.hpp>

// Only include muse_controller.h when building for original single-chip target
// The S3 build receives data via SPI and doesn't need these types
#if !defined(NATMUSE_TARGET_S3)
extern "C" {
#include "muse_controller.h"
}
#endif

/**
 * Thread-safe buffer for collecting Muse data samples.
 * 
 * This buffer collects EEG, accelerometer, gyroscope, and PPG data
 * using the authoritative NatMuseDataSchema from libnatkit-core.
 * 
 * The buffer accumulates data until it reaches BULK_SIZE (100) samples,
 * then signals that it's ready for transmission.
 */
class MuseDataBuffer {
public:
    // Use constants from the authoritative schema
    static const size_t BULK_SIZE = nat::core::NatMuseBulkDataSchema::BULK_SIZE;
    static const int EEG_SAMPLES_PER_PACKET = nat::core::NatMuseDataSchema::EEG_SAMPLES_PER_PACKET;
    static const int MOTION_SAMPLES = nat::core::NatMuseDataSchema::MOTION_SAMPLES;
    static const int PPG_SAMPLES = nat::core::NatMuseDataSchema::PPG_SAMPLES;

    // has_data bitfield values from schema
    static const uint8_t HAS_EEG = nat::core::NatMuseDataSchema::HAS_EEG;
    static const uint8_t HAS_ACCEL = nat::core::NatMuseDataSchema::HAS_ACCEL;
    static const uint8_t HAS_GYRO = nat::core::NatMuseDataSchema::HAS_GYRO;
    static const uint8_t HAS_PPG = nat::core::NatMuseDataSchema::HAS_PPG;

    MuseDataBuffer();
    ~MuseDataBuffer();

    /**
     * Add EEG data for a specific channel (SPI-friendly version).
     * When all 4 channels have been received for a sequence, the sample is considered complete.
     * 
     * @param timestamp NTP-synchronized timestamp in microseconds
     * @param sequence Packet sequence number
     * @param channel EEG channel (0-3 for TP9/AF7/AF8/TP10)
     * @param samples Array of 12 float samples
     */
    void addEegData(uint64_t timestamp, uint16_t sequence, 
                    uint8_t channel, const float samples[EEG_SAMPLES_PER_PACKET]);

    /**
     * Add accelerometer data (SPI-friendly version).
     * 
     * @param timestamp NTP-synchronized timestamp in microseconds
     * @param sequence Motion sequence number
     * @param samples Array of 3 samples × (x, y, z)
     */
    void addAccelData(uint64_t timestamp, uint16_t sequence, const float samples[MOTION_SAMPLES][3]);

    /**
     * Add gyroscope data (SPI-friendly version).
     * 
     * @param timestamp NTP-synchronized timestamp in microseconds
     * @param sequence Motion sequence number
     * @param samples Array of 3 samples × (x, y, z)
     */
    void addGyroData(uint64_t timestamp, uint16_t sequence, const float samples[MOTION_SAMPLES][3]);

    /**
     * Check if buffer is full and ready for transmission.
     */
    bool isFull() const;

    /**
     * Get current sample count.
     */
    size_t getSize() const;

    /**
     * Get reference to the bulk schema (for serialization).
     * Call lock() before accessing and unlock() after.
     */
    const nat::core::NatMuseBulkDataSchema& getBulkSchema() const;

    /**
     * Reset the buffer after transmission.
     */
    void reset();

    /**
     * Lock the buffer for exclusive access.
     */
    void lock();

    /**
     * Unlock the buffer.
     */
    void unlock();

private:
    nat::core::NatMuseBulkDataSchema bulkSchema_;
    
    // Current sample being built (accumulating EEG channels)
    nat::core::NatMuseDataSchema currentSample_;
    uint8_t eegChannelsMask_;  // Tracks which EEG channels have been received
    uint16_t currentEegSequence_;
    
    SemaphoreHandle_t mutex_;

    // Finalize current sample and add to buffer
    void finalizeCurrentSample();
};

#endif // MUSE_DATA_BUFFER_HPP
