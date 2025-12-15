#ifndef NETWORKING_HPP
#define NETWORKING_HPP

#include <cstdint>
#include <functional>
#include <string>

/**
 * Networking module for natMuse
 * 
 * Provides WiFi, MQTT, and NTP functionality using ESP-IDF native APIs.
 */

// Connection configuration
struct NetworkConfig {
    // WiFi settings
    const char* wifi_ssid;
    const char* wifi_password;
    
    // MQTT settings
    const char* mqtt_broker_host;
    uint16_t mqtt_broker_port;
    const char* mqtt_client_id;
    
    // NTP settings (optional - uses pool.ntp.org by default)
    const char* ntp_server;
};

/**
 * Initialize networking subsystem (NVS, event loop, netif)
 * @return 0 on success
 */
int networking_init();

/**
 * Connect to WiFi
 * @param ssid WiFi network name
 * @param password WiFi password
 * @param timeout_ms Connection timeout in milliseconds
 * @return 0 on success
 */
int networking_wifi_connect(const char* ssid, const char* password, uint32_t timeout_ms = 30000);

/**
 * Check if WiFi is connected
 */
bool networking_wifi_is_connected();

/**
 * Initialize NTP time synchronization
 * @param ntp_server NTP server (nullptr for default pool.ntp.org)
 * @return 0 on success
 */
int networking_ntp_init(const char* ntp_server = nullptr);

/**
 * Wait for NTP synchronization
 * @param timeout_ms Maximum wait time
 * @return 0 on success (time synchronized)
 */
int networking_ntp_wait_sync(uint32_t timeout_ms = 60000);

/**
 * Check if NTP time is synchronized
 */
bool networking_ntp_is_synced();

/**
 * Get current time in microseconds (NTP-synchronized)
 */
uint64_t networking_get_time_us();

/**
 * Initialize MQTT client
 * @param broker_host MQTT broker hostname or IP
 * @param broker_port MQTT broker port
 * @param client_id Client identifier
 * @return 0 on success
 */
int networking_mqtt_init(const char* broker_host, uint16_t broker_port, const char* client_id);

/**
 * Connect to MQTT broker
 * @param timeout_ms Connection timeout
 * @return 0 on success
 */
int networking_mqtt_connect(uint32_t timeout_ms = 10000);

/**
 * Check if MQTT is connected
 */
bool networking_mqtt_is_connected();

/**
 * Publish binary data to MQTT topic
 * @param topic Topic string
 * @param data Binary data
 * @param len Data length
 * @param qos Quality of service (0, 1, or 2)
 * @return 0 on success
 */
int networking_mqtt_publish(const char* topic, const uint8_t* data, size_t len, int qos = 0);

/**
 * Disconnect from MQTT broker
 */
void networking_mqtt_disconnect();

/**
 * Get the device MAC address as a string
 * @param buffer Output buffer (at least 18 bytes for "XX:XX:XX:XX:XX:XX\0")
 */
void networking_get_mac_string(char* buffer);

/**
 * Get a unique device ID based on MAC address
 */
uint64_t networking_get_device_id();

#endif // NETWORKING_HPP
