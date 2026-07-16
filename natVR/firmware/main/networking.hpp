#pragma once

#include <cstddef>
#include <cstdint>

int networking_init();

int networking_wifi_connect(const char* ssid, const char* password,
                            uint32_t timeout_ms = 30000);
bool networking_wifi_is_connected();
int networking_wifi_rssi_dbm();

int networking_ntp_init(const char* ntp_server);
int networking_ntp_wait_sync(uint32_t timeout_ms = 60000);
bool networking_ntp_is_synced();
uint64_t networking_get_time_us();
void networking_get_mac_string(char* out_mac);

int networking_mqtt_init(const char* broker_host, uint16_t broker_port,
                         const char* client_id, size_t buffer_size = 12288);
int networking_mqtt_connect(uint32_t timeout_ms = 10000);
bool networking_mqtt_is_connected();
int networking_mqtt_publish(const char* topic, const uint8_t* data, size_t len,
                            int qos = 0, bool retain = false);
void networking_mqtt_disconnect();
