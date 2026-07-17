#pragma once

#include <cstdint>

#include "driver/spi_master.h"
#include "esp_err.h"

namespace nat::hand_tracking::imu {

struct Bno08xConfig {
  spi_host_device_t spi_host;
  int pin_spi_sck;
  int pin_spi_miso;
  int pin_spi_mosi;
  int pin_spi_cs;
  int pin_imu_int;
  int pin_imu_reset;
  int spi_clock_hz;
  uint32_t report_interval_us;
  uint32_t boot_ready_timeout_ms;
  uint32_t write_ready_timeout_ms;
  uint32_t followup_read_timeout_ms;
};

struct ImuSample {
  float quat_w;
  float quat_x;
  float quat_y;
  float quat_z;
  float accel_x;
  float accel_y;
  float accel_z;
  float gyro_x;
  float gyro_y;
  float gyro_z;
  uint8_t accuracy;
};

constexpr Bno08xConfig kDefaultConfig{
    .spi_host = SPI2_HOST,
    .pin_spi_sck = 5,
    .pin_spi_miso = 21,
    .pin_spi_mosi = 19,
    .pin_spi_cs = 15,
    .pin_imu_int = 32,
    .pin_imu_reset = 14,
    .spi_clock_hz = 3000000,
    .report_interval_us = 20000,
    .boot_ready_timeout_ms = 500,
    .write_ready_timeout_ms = 20,
    .followup_read_timeout_ms = 2,
};

esp_err_t init();
esp_err_t init(const Bno08xConfig& config);
void service();
bool get_latest(ImuSample* out_sample);

}  // namespace nat::hand_tracking::imu
