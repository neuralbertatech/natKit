#include "Bno08xProvider.hpp"

#include <array>
#include <atomic>
#include <cstdint>

extern "C" {
#include "sh2.h"
#include "sh2_err.h"
#include "sh2_SensorValue.h"
}

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace nat::hand_tracking::imu {
namespace {

constexpr char kTag[] = "natkit-bno086";

ImuSample make_default_sample() {
  ImuSample sample{};
  sample.quat_w = 1.0f;
  sample.quat_x = 0.0f;
  sample.quat_y = 0.0f;
  sample.quat_z = 0.0f;
  sample.accel_x = 0.0f;
  sample.accel_y = 0.0f;
  sample.accel_z = 9.81f;
  sample.gyro_x = 0.0f;
  sample.gyro_y = 0.0f;
  sample.gyro_z = 0.0f;
  sample.accuracy = 0;
  return sample;
}

struct BnoState {
  Bno08xConfig config = kDefaultConfig;
  spi_device_handle_t spi_handle = nullptr;
  sh2_Hal_t hal{};
  std::array<uint8_t, SH2_HAL_MAX_TRANSFER_IN> zero_tx{};
  ImuSample latest = make_default_sample();
  bool initialized = false;
  bool has_sample = false;
};

BnoState g_state{};
std::atomic<bool> g_needs_reconfigure{false};

gpio_num_t pin_to_gpio(int pin) {
  return static_cast<gpio_num_t>(pin);
}

bool wait_for_int_low(uint32_t timeout_ms) {
  if (g_state.config.pin_imu_int < 0) {
    return true;
  }

  if (gpio_get_level(pin_to_gpio(g_state.config.pin_imu_int)) == 0) {
    return true;
  }
  if (timeout_ms == 0U) {
    return false;
  }

  const int64_t deadline_us =
      esp_timer_get_time() + static_cast<int64_t>(timeout_ms) * 1000;
  while (esp_timer_get_time() < deadline_us) {
    if (gpio_get_level(pin_to_gpio(g_state.config.pin_imu_int)) == 0) {
      return true;
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
  return gpio_get_level(pin_to_gpio(g_state.config.pin_imu_int)) == 0;
}

esp_err_t spi_read_bytes(uint8_t* buffer, size_t len) {
  if (len == 0U) {
    return ESP_OK;
  }
  if (buffer == nullptr || len > g_state.zero_tx.size()) {
    return ESP_ERR_INVALID_ARG;
  }

  spi_transaction_t transaction{};
  transaction.length = len * 8U;
  transaction.tx_buffer = g_state.zero_tx.data();
  transaction.rx_buffer = buffer;
  return spi_device_polling_transmit(g_state.spi_handle, &transaction);
}

esp_err_t spi_write_bytes(const uint8_t* buffer, size_t len) {
  if (len == 0U) {
    return ESP_OK;
  }
  if (buffer == nullptr) {
    return ESP_ERR_INVALID_ARG;
  }

  spi_transaction_t transaction{};
  transaction.length = len * 8U;
  transaction.tx_buffer = buffer;
  return spi_device_polling_transmit(g_state.spi_handle, &transaction);
}

void hardware_reset() {
  if (g_state.config.pin_imu_reset < 0) {
    return;
  }

  gpio_set_level(pin_to_gpio(g_state.config.pin_imu_reset), 1);
  vTaskDelay(pdMS_TO_TICKS(10));
  gpio_set_level(pin_to_gpio(g_state.config.pin_imu_reset), 0);
  vTaskDelay(pdMS_TO_TICKS(10));
  gpio_set_level(pin_to_gpio(g_state.config.pin_imu_reset), 1);
  vTaskDelay(pdMS_TO_TICKS(10));
}

int hal_open(sh2_Hal_t* /*self*/) {
  hardware_reset();
  if (!wait_for_int_low(g_state.config.boot_ready_timeout_ms)) {
    ESP_LOGW(kTag, "INT pin did not go low during boot wait");
  }
  return 0;
}

void hal_close(sh2_Hal_t* /*self*/) {}

int hal_read(sh2_Hal_t* /*self*/, uint8_t* p_buffer, unsigned len,
             uint32_t* t_us) {
  if (p_buffer == nullptr || len < 4U) {
    return 0;
  }

  if (!wait_for_int_low(0)) {
    return 0;
  }

  uint8_t header[4] = {0, 0, 0, 0};
  if (spi_read_bytes(header, sizeof(header)) != ESP_OK) {
    return 0;
  }

  uint16_t packet_size = static_cast<uint16_t>(header[0]) |
                         static_cast<uint16_t>(header[1] << 8);
  packet_size &= static_cast<uint16_t>(~0x8000U);
  if (packet_size == 0U || packet_size > len) {
    return 0;
  }

  if (!wait_for_int_low(g_state.config.followup_read_timeout_ms)) {
    return 0;
  }

  if (spi_read_bytes(p_buffer, packet_size) != ESP_OK) {
    return 0;
  }

  if (t_us != nullptr) {
    *t_us = static_cast<uint32_t>(esp_timer_get_time() & 0xFFFFFFFFULL);
  }

  return static_cast<int>(packet_size);
}

int hal_write(sh2_Hal_t* /*self*/, uint8_t* p_buffer, unsigned len) {
  if (p_buffer == nullptr || len == 0U) {
    return 0;
  }

  if (!wait_for_int_low(g_state.config.write_ready_timeout_ms)) {
    return 0;
  }

  if (spi_write_bytes(p_buffer, len) != ESP_OK) {
    return 0;
  }
  return static_cast<int>(len);
}

uint32_t hal_get_time_us(sh2_Hal_t* /*self*/) {
  return static_cast<uint32_t>(esp_timer_get_time() & 0xFFFFFFFFULL);
}

void on_async_event(void* /*cookie*/, sh2_AsyncEvent_t* event) {
  if (event != nullptr && event->eventId == SH2_RESET) {
    g_needs_reconfigure.store(true, std::memory_order_release);
  }
}

void on_sensor_event(void* /*cookie*/, sh2_SensorEvent_t* event) {
  if (event == nullptr) {
    return;
  }

  sh2_SensorValue_t decoded{};
  const int decode_result = sh2_decodeSensorEvent(&decoded, event);
  if (decode_result != SH2_OK) {
    return;
  }

  switch (decoded.sensorId) {
    case SH2_ROTATION_VECTOR:
      g_state.latest.quat_w = decoded.un.rotationVector.real;
      g_state.latest.quat_x = decoded.un.rotationVector.i;
      g_state.latest.quat_y = decoded.un.rotationVector.j;
      g_state.latest.quat_z = decoded.un.rotationVector.k;
      g_state.latest.accuracy = static_cast<uint8_t>(decoded.status & 0x03U);
      g_state.has_sample = true;
      break;

    case SH2_ACCELEROMETER:
      g_state.latest.accel_x = decoded.un.accelerometer.x;
      g_state.latest.accel_y = decoded.un.accelerometer.y;
      g_state.latest.accel_z = decoded.un.accelerometer.z;
      g_state.has_sample = true;
      break;

    case SH2_GYROSCOPE_CALIBRATED:
      g_state.latest.gyro_x = decoded.un.gyroscope.x;
      g_state.latest.gyro_y = decoded.un.gyroscope.y;
      g_state.latest.gyro_z = decoded.un.gyroscope.z;
      g_state.has_sample = true;
      break;

    default:
      break;
  }
}

esp_err_t configure_reports() {
  const auto configure_sensor = [](sh2_SensorId_t sensor_id) -> esp_err_t {
    sh2_SensorConfig_t config{};
    config.changeSensitivityEnabled = false;
    config.wakeupEnabled = false;
    config.changeSensitivityRelative = false;
    config.alwaysOnEnabled = false;
    config.changeSensitivity = 0;
    config.batchInterval_us = 0;
    config.sensorSpecific = 0;
    config.reportInterval_us = g_state.config.report_interval_us;

    const int rc = sh2_setSensorConfig(sensor_id, &config);
    if (rc != SH2_OK) {
      ESP_LOGE(kTag, "sh2_setSensorConfig(0x%02X) failed: %d",
               static_cast<unsigned>(sensor_id), rc);
      return ESP_FAIL;
    }
    return ESP_OK;
  };

  ESP_RETURN_ON_ERROR(configure_sensor(SH2_ACCELEROMETER), kTag,
                      "Failed to enable accelerometer");
  ESP_RETURN_ON_ERROR(configure_sensor(SH2_GYROSCOPE_CALIBRATED), kTag,
                      "Failed to enable calibrated gyroscope");
  ESP_RETURN_ON_ERROR(configure_sensor(SH2_ROTATION_VECTOR), kTag,
                      "Failed to enable rotation vector");
  return ESP_OK;
}

esp_err_t init_gpio_lines() {
  if (g_state.config.pin_imu_int >= 0) {
    gpio_config_t int_cfg{};
    int_cfg.pin_bit_mask =
        (1ULL << static_cast<uint32_t>(g_state.config.pin_imu_int));
    int_cfg.mode = GPIO_MODE_INPUT;
    int_cfg.pull_up_en = GPIO_PULLUP_ENABLE;
    int_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    int_cfg.intr_type = GPIO_INTR_DISABLE;
    ESP_RETURN_ON_ERROR(gpio_config(&int_cfg), kTag, "INT gpio_config failed");
  }

  if (g_state.config.pin_imu_reset >= 0) {
    gpio_config_t reset_cfg{};
    reset_cfg.pin_bit_mask =
        (1ULL << static_cast<uint32_t>(g_state.config.pin_imu_reset));
    reset_cfg.mode = GPIO_MODE_OUTPUT;
    reset_cfg.pull_up_en = GPIO_PULLUP_DISABLE;
    reset_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    reset_cfg.intr_type = GPIO_INTR_DISABLE;
    ESP_RETURN_ON_ERROR(gpio_config(&reset_cfg), kTag,
                        "RESET gpio_config failed");
    gpio_set_level(pin_to_gpio(g_state.config.pin_imu_reset), 1);
  }

  return ESP_OK;
}

esp_err_t init_spi_bus() {
  spi_bus_config_t bus_cfg{};
  bus_cfg.mosi_io_num = g_state.config.pin_spi_mosi;
  bus_cfg.miso_io_num = g_state.config.pin_spi_miso;
  bus_cfg.sclk_io_num = g_state.config.pin_spi_sck;
  bus_cfg.quadwp_io_num = -1;
  bus_cfg.quadhd_io_num = -1;
  bus_cfg.max_transfer_sz = SH2_HAL_MAX_TRANSFER_IN;

  ESP_RETURN_ON_ERROR(
      spi_bus_initialize(g_state.config.spi_host, &bus_cfg, SPI_DMA_CH_AUTO),
      kTag, "spi_bus_initialize failed");

  spi_device_interface_config_t dev_cfg{};
  dev_cfg.clock_speed_hz = g_state.config.spi_clock_hz;
  dev_cfg.mode = 3;
  dev_cfg.spics_io_num = g_state.config.pin_spi_cs;
  dev_cfg.queue_size = 1;

  ESP_RETURN_ON_ERROR(
      spi_bus_add_device(g_state.config.spi_host, &dev_cfg, &g_state.spi_handle),
      kTag, "spi_bus_add_device failed");
  return ESP_OK;
}

}  // namespace

esp_err_t init() {
  return init(kDefaultConfig);
}

esp_err_t init(const Bno08xConfig& config) {
  if (g_state.initialized) {
    return ESP_OK;
  }

  g_state.config = config;
  g_state.latest = make_default_sample();
  g_state.has_sample = false;
  g_needs_reconfigure.store(false, std::memory_order_release);

  ESP_RETURN_ON_ERROR(init_gpio_lines(), kTag, "GPIO init failed");
  ESP_RETURN_ON_ERROR(init_spi_bus(), kTag, "SPI init failed");

  g_state.hal.open = hal_open;
  g_state.hal.close = hal_close;
  g_state.hal.read = hal_read;
  g_state.hal.write = hal_write;
  g_state.hal.getTimeUs = hal_get_time_us;

  const int open_result = sh2_open(&g_state.hal, on_async_event, nullptr);
  if (open_result != SH2_OK) {
    ESP_LOGE(kTag, "sh2_open failed: %d", open_result);
    return ESP_FAIL;
  }

  sh2_ProductIds_t prod_ids{};
  const int prod_result = sh2_getProdIds(&prod_ids);
  if (prod_result != SH2_OK) {
    ESP_LOGE(kTag, "sh2_getProdIds failed: %d", prod_result);
    return ESP_FAIL;
  }
  ESP_LOGI(kTag, "BNO08x product IDs received: %u entries", prod_ids.numEntries);

  const int sensor_cb_result = sh2_setSensorCallback(on_sensor_event, nullptr);
  if (sensor_cb_result != SH2_OK) {
    ESP_LOGE(kTag, "sh2_setSensorCallback failed: %d", sensor_cb_result);
    return ESP_FAIL;
  }

  ESP_RETURN_ON_ERROR(configure_reports(), kTag, "Failed to configure reports");
  g_state.initialized = true;
  return ESP_OK;
}

void service() {
  if (!g_state.initialized) {
    return;
  }

  sh2_service();

  if (g_needs_reconfigure.exchange(false, std::memory_order_acq_rel)) {
    if (configure_reports() != ESP_OK) {
      g_needs_reconfigure.store(true, std::memory_order_release);
    }
  }
}

bool get_latest(ImuSample* out_sample) {
  if (out_sample == nullptr) {
    return false;
  }
  *out_sample = g_state.latest;
  return g_state.has_sample;
}

}  // namespace nat::hand_tracking::imu
