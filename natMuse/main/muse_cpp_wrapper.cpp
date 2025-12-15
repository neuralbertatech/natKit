#include "muse_cpp_wrapper.hpp"
#include "esp_log.h"

static const char* TAG = "MuseCppWrapper";

MuseCppWrapper& MuseCppWrapper::getInstance() {
    static MuseCppWrapper instance;
    return instance;
}

MuseCppWrapper::MuseCppWrapper()
    : eegCallback_(nullptr)
    , accelCallback_(nullptr)
    , gyroCallback_(nullptr)
    , statusCallback_(nullptr)
    , initialized_(false) {
}

MuseCppWrapper::~MuseCppWrapper() {
    if (initialized_) {
        stop();
    }
}

void MuseCppWrapper::setEegCallback(EegCallback callback) {
    eegCallback_ = callback;
}

void MuseCppWrapper::setAccelCallback(AccelCallback callback) {
    accelCallback_ = callback;
}

void MuseCppWrapper::setGyroCallback(GyroCallback callback) {
    gyroCallback_ = callback;
}

void MuseCppWrapper::setStatusCallback(StatusCallback callback) {
    statusCallback_ = callback;
}

// Static C callback trampolines that forward to the singleton instance
void MuseCppWrapper::eegTrampoline(muse_eeg_channel_t channel, const muse_eeg_data_t* data) {
    auto& instance = getInstance();
    if (instance.eegCallback_) {
        instance.eegCallback_(channel, data);
    }
}

void MuseCppWrapper::accelTrampoline(const muse_accel_data_t* data) {
    auto& instance = getInstance();
    if (instance.accelCallback_) {
        instance.accelCallback_(data);
    }
}

void MuseCppWrapper::gyroTrampoline(const muse_gyro_data_t* data) {
    auto& instance = getInstance();
    if (instance.gyroCallback_) {
        instance.gyroCallback_(data);
    }
}

void MuseCppWrapper::statusTrampoline(muse_status_t status) {
    auto& instance = getInstance();
    if (instance.statusCallback_) {
        instance.statusCallback_(status);
    }
}

int MuseCppWrapper::init(bool enableAccel, bool enableGyro, uint32_t scanTimeoutMs) {
    if (initialized_) {
        ESP_LOGW(TAG, "Already initialized");
        return 0;
    }

    muse_config_t config;
    muse_controller_get_default_config(&config);

    // Set our static trampolines as the C callbacks
    config.on_eeg_data = eegTrampoline;
    config.on_accel_data = accelTrampoline;
    config.on_gyro_data = gyroTrampoline;
    config.on_status_change = statusTrampoline;

    config.enable_accelerometer = enableAccel;
    config.enable_gyroscope = enableGyro;
    config.scan_timeout_ms = scanTimeoutMs;

    int result = muse_controller_init(&config);
    if (result == 0) {
        initialized_ = true;
        ESP_LOGI(TAG, "Muse controller initialized");
    } else {
        ESP_LOGE(TAG, "Failed to initialize Muse controller: %d", result);
    }

    return result;
}

int MuseCppWrapper::start() {
    if (!initialized_) {
        ESP_LOGE(TAG, "Not initialized");
        return -1;
    }

    int result = muse_controller_start();
    if (result == 0) {
        ESP_LOGI(TAG, "Muse controller started");
    } else {
        ESP_LOGE(TAG, "Failed to start Muse controller: %d", result);
    }

    return result;
}

int MuseCppWrapper::stop() {
    if (!initialized_) {
        return 0;
    }

    int result = muse_controller_stop();
    ESP_LOGI(TAG, "Muse controller stopped");
    return result;
}

muse_status_t MuseCppWrapper::getStatus() const {
    return muse_controller_get_status();
}

bool MuseCppWrapper::isStreaming() const {
    return muse_controller_is_streaming();
}

const char* MuseCppWrapper::getChannelName(muse_eeg_channel_t channel) {
    return muse_controller_get_channel_name(channel);
}
