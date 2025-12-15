#ifndef MUSE_CPP_WRAPPER_HPP
#define MUSE_CPP_WRAPPER_HPP

#include <functional>
#include <cstdint>

extern "C" {
#include "muse_controller.h"
}

/**
 * C++ Wrapper for the Muse Controller
 * 
 * Provides a C++ interface with std::function callbacks that can capture context.
 * This allows integrating with C++ classes and lambdas.
 */
class MuseCppWrapper {
public:
    // Callback types using std::function for flexibility
    using EegCallback = std::function<void(muse_eeg_channel_t channel, const muse_eeg_data_t* data)>;
    using AccelCallback = std::function<void(const muse_accel_data_t* data)>;
    using GyroCallback = std::function<void(const muse_gyro_data_t* data)>;
    using StatusCallback = std::function<void(muse_status_t status)>;

    /**
     * Get the singleton instance
     */
    static MuseCppWrapper& getInstance();

    // Prevent copying
    MuseCppWrapper(const MuseCppWrapper&) = delete;
    MuseCppWrapper& operator=(const MuseCppWrapper&) = delete;

    /**
     * Set callbacks before calling init()
     */
    void setEegCallback(EegCallback callback);
    void setAccelCallback(AccelCallback callback);
    void setGyroCallback(GyroCallback callback);
    void setStatusCallback(StatusCallback callback);

    /**
     * Initialize the Muse controller
     * @param enableAccel Enable accelerometer (default: true)
     * @param enableGyro Enable gyroscope (default: true)
     * @param scanTimeoutMs Scan timeout in milliseconds (default: 30000)
     * @return 0 on success, negative on error
     */
    int init(bool enableAccel = true, bool enableGyro = true, uint32_t scanTimeoutMs = 30000);

    /**
     * Start scanning for and connecting to Muse
     * @return 0 on success, negative on error
     */
    int start();

    /**
     * Stop and disconnect from Muse
     * @return 0 on success
     */
    int stop();

    /**
     * Get current status
     */
    muse_status_t getStatus() const;

    /**
     * Check if currently streaming
     */
    bool isStreaming() const;

    /**
     * Get channel name
     */
    static const char* getChannelName(muse_eeg_channel_t channel);

private:
    MuseCppWrapper();
    ~MuseCppWrapper();

    // Static C callback trampolines
    static void eegTrampoline(muse_eeg_channel_t channel, const muse_eeg_data_t* data);
    static void accelTrampoline(const muse_accel_data_t* data);
    static void gyroTrampoline(const muse_gyro_data_t* data);
    static void statusTrampoline(muse_status_t status);

    // Stored callbacks
    EegCallback eegCallback_;
    AccelCallback accelCallback_;
    GyroCallback gyroCallback_;
    StatusCallback statusCallback_;

    bool initialized_;
};

#endif // MUSE_CPP_WRAPPER_HPP
