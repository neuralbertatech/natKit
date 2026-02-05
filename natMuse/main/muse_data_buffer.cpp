#include "muse_data_buffer.hpp"
#include "esp_log.h"
#include <cstring>

static const char* TAG = "MuseDataBuffer";

MuseDataBuffer::MuseDataBuffer()
    : eegChannelsMask_(0)
    , currentEegSequence_(0) {
    mutex_ = xSemaphoreCreateMutex();
    if (mutex_ == nullptr) {
        ESP_LOGE(TAG, "Failed to create mutex");
    }
}

MuseDataBuffer::~MuseDataBuffer() {
    if (mutex_ != nullptr) {
        vSemaphoreDelete(mutex_);
    }
}

void MuseDataBuffer::lock() {
    if (mutex_ != nullptr) {
        xSemaphoreTake(mutex_, portMAX_DELAY);
    }
}

void MuseDataBuffer::unlock() {
    if (mutex_ != nullptr) {
        xSemaphoreGive(mutex_);
    }
}

void MuseDataBuffer::addEegData(uint64_t timestamp, uint16_t sequence,
                                 uint8_t channel, const float samples[EEG_SAMPLES_PER_PACKET]) {
    lock();

    // If this is a new sequence, finalize the previous sample if we had any data
    if (sequence != currentEegSequence_ && eegChannelsMask_ != 0) {
        finalizeCurrentSample();
    }

    // Update current sample
    currentSample_.setTime(timestamp);
    currentSample_.eeg_sequence = sequence;
    currentEegSequence_ = sequence;

    // Copy data to appropriate channel (channel: 0=TP9, 1=AF7, 2=AF8, 3=TP10)
    switch (channel) {
        case 0:  // TP9
            memcpy(currentSample_.tp9, samples, sizeof(currentSample_.tp9));
            eegChannelsMask_ |= 0x01;
            break;
        case 1:  // AF7
            memcpy(currentSample_.af7, samples, sizeof(currentSample_.af7));
            eegChannelsMask_ |= 0x02;
            break;
        case 2:  // AF8
            memcpy(currentSample_.af8, samples, sizeof(currentSample_.af8));
            eegChannelsMask_ |= 0x04;
            break;
        case 3:  // TP10
            memcpy(currentSample_.tp10, samples, sizeof(currentSample_.tp10));
            eegChannelsMask_ |= 0x08;
            break;
        default:
            break;
    }

    currentSample_.has_data |= HAS_EEG;

    // If we have all 4 EEG channels, finalize the sample
    if (eegChannelsMask_ == 0x0F) {
        finalizeCurrentSample();
    }

    unlock();
}

void MuseDataBuffer::addAccelData(uint64_t timestamp, uint16_t sequence, const float samples[MOTION_SAMPLES][3]) {
    lock();

    // Update current sample with accel data
    currentSample_.setTime(timestamp);
    currentSample_.motion_sequence = sequence;

    for (int i = 0; i < MOTION_SAMPLES; ++i) {
        currentSample_.accel[i][0] = samples[i][0];
        currentSample_.accel[i][1] = samples[i][1];
        currentSample_.accel[i][2] = samples[i][2];
    }

    currentSample_.has_data |= HAS_ACCEL;

    unlock();
}

void MuseDataBuffer::addGyroData(uint64_t timestamp, uint16_t sequence, const float samples[MOTION_SAMPLES][3]) {
    lock();

    // Update current sample with gyro data
    currentSample_.setTime(timestamp);
    currentSample_.motion_sequence = sequence;

    for (int i = 0; i < MOTION_SAMPLES; ++i) {
        currentSample_.gyro[i][0] = samples[i][0];
        currentSample_.gyro[i][1] = samples[i][1];
        currentSample_.gyro[i][2] = samples[i][2];
    }

    currentSample_.has_data |= HAS_GYRO;

    unlock();
}

void MuseDataBuffer::finalizeCurrentSample() {
    // This is called while holding the lock
    
    if (bulkSchema_.isFull()) {
        // Buffer is full, can't add more
        ESP_LOGW(TAG, "Buffer full, dropping sample");
        return;
    }

    // Add current sample to bulk schema
    bulkSchema_.add(currentSample_);

    // Reset current sample for next collection
    currentSample_ = nat::core::NatMuseDataSchema();
    eegChannelsMask_ = 0;
}

bool MuseDataBuffer::isFull() const {
    return bulkSchema_.isFull();
}

size_t MuseDataBuffer::getSize() const {
    return bulkSchema_.getSize();
}

const nat::core::NatMuseBulkDataSchema& MuseDataBuffer::getBulkSchema() const {
    return bulkSchema_;
}

void MuseDataBuffer::reset() {
    lock();
    bulkSchema_.reset();
    currentSample_ = nat::core::NatMuseDataSchema();
    eegChannelsMask_ = 0;
    currentEegSequence_ = 0;
    unlock();
}
