#include <stdio.h>
#include "esp_log.h"
#include "muse_controller.h"

static const char *TAG = "MAIN";

// EEG data callback
static void on_eeg(muse_eeg_channel_t channel, const muse_eeg_data_t *data) {
    printf("EEG [%s] #%u: ", muse_controller_get_channel_name(channel), data->sequence);
    for (int i = 0; i < MUSE_EEG_SAMPLES_PER_PACKET; i++) {
        printf("%.1f ", data->samples[i]);
    }
    printf("\n");
}

// Accelerometer data callback
static void on_accel(const muse_accel_data_t *data) {
    printf("ACCEL #%u: x=%.3fg y=%.3fg z=%.3fg\n",
           data->sequence, data->x[0], data->y[0], data->z[0]);
}

// Gyroscope data callback
static void on_gyro(const muse_gyro_data_t *data) {
    printf("GYRO #%u: x=%.2f y=%.2f z=%.2f deg/s\n",
           data->sequence, data->x[0], data->y[0], data->z[0]);
}

// Status change callback
static void on_status(muse_status_t status) {
    const char *status_names[] = {
        "DISCONNECTED", "SCANNING", "CONNECTING", 
        "CONNECTED", "STREAMING", "ERROR"
    };
    ESP_LOGI(TAG, "Muse status: %s", status_names[status]);
}

void app_main(void) {
    ESP_LOGI(TAG, "Muse Controller Demo");
    
    // Configure the controller
    muse_config_t config;
    muse_controller_get_default_config(&config);
    
    config.on_eeg_data = on_eeg;
    config.on_accel_data = on_accel;
    config.on_gyro_data = on_gyro;
    config.on_status_change = on_status;
    
    // Initialize and start
    if (muse_controller_init(&config) != 0) {
        ESP_LOGE(TAG, "Failed to initialize Muse controller");
        return;
    }
    
    if (muse_controller_start() != 0) {
        ESP_LOGE(TAG, "Failed to start Muse controller");
        return;
    }
    
    ESP_LOGI(TAG, "Muse controller started - scanning for device...");
}
