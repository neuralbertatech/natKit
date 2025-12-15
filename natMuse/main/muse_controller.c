#include "muse_controller.h"
#include "muse_protocol.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "nvs_flash.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"

// Forward declaration for NimBLE store initialization
void ble_store_config_init(void);

static const char *TAG = "MUSE_CTRL";

// Internal state
static muse_config_t config;
static muse_status_t current_status = MUSE_STATUS_DISCONNECTED;
static uint16_t conn_handle = BLE_HS_CONN_HANDLE_NONE;
static bool initialized = false;

// Characteristic handles
static struct {
    uint16_t control;
    uint16_t tp9;
    uint16_t af7;
    uint16_t af8;
    uint16_t tp10;
    uint16_t gyro;
    uint16_t accel;
} char_handles = {0};

// Service discovery state
static uint16_t muse_svc_start_handle = 0;
static uint16_t muse_svc_end_handle = 0;

// Track if we've already requested our preferred connection parameters
static bool params_updated_by_us = false;

// Muse service UUID (16-bit)
#define MUSE_SERVICE_UUID_16 0xFE8D

// Forward declarations
static void ble_host_task(void *param);
static void on_ble_sync(void);
static void on_ble_reset(int reason);
static int gap_event_handler(struct ble_gap_event *event, void *arg);
static int svc_disc_handler(uint16_t conn_handle, const struct ble_gatt_error *error,
                            const struct ble_gatt_svc *service, void *arg);
static int chr_disc_handler(uint16_t conn_handle, const struct ble_gatt_error *error,
                            const struct ble_gatt_chr *chr, void *arg);

// Set status and notify callback
static void set_status(muse_status_t status) {
    if (current_status != status) {
        current_status = status;
        if (config.on_status_change) {
            config.on_status_change(status);
        }
    }
}

// Send command to Muse
static int send_command(const char *cmd_str) {
    size_t len = strlen(cmd_str);
    uint8_t cmd[16];
    cmd[0] = (uint8_t)(len + 1);
    for (size_t i = 0; i < len; i++) {
        cmd[i + 1] = (uint8_t)cmd_str[i];
    }
    cmd[len + 1] = 0x0a;
    
    int rc = ble_gattc_write_no_rsp_flat(conn_handle, char_handles.control, cmd, len + 2);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to send command '%s': %d", cmd_str, rc);
    }
    vTaskDelay(pdMS_TO_TICKS(200));
    return rc;
}

// Subscribe to a characteristic
static int subscribe_char(uint16_t handle) {
    if (handle == 0) return -1;
    
    uint16_t cccd_handle = handle + 1;
    uint8_t value[2] = {0x01, 0x00};
    
    int rc = ble_gattc_write_flat(conn_handle, cccd_handle, value, sizeof(value), NULL, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to subscribe to handle %d: %d", handle, rc);
    }
    vTaskDelay(pdMS_TO_TICKS(200));
    return rc;
}

// Task to handle subscriptions and start streaming
static void streaming_task(void *arg) {
    // Subscribe to EEG channels
    subscribe_char(char_handles.tp9);
    subscribe_char(char_handles.af7);
    subscribe_char(char_handles.af8);
    subscribe_char(char_handles.tp10);
    
    // Subscribe to motion sensors if enabled
    if (config.enable_accelerometer && char_handles.accel) {
        subscribe_char(char_handles.accel);
    }
    if (config.enable_gyroscope && char_handles.gyro) {
        subscribe_char(char_handles.gyro);
    }
    
    // Wait for subscriptions to settle
    vTaskDelay(pdMS_TO_TICKS(500));
    
    // Start streaming
    send_command("k");    // Keep alive
    send_command("v1");   // Version
    send_command("p21");  // Preset
    send_command("d");    // Start data
    
    set_status(MUSE_STATUS_STREAMING);
    ESP_LOGI(TAG, "Streaming started");
    
    vTaskDelete(NULL);
}

// Handle incoming notifications
static void handle_notification(uint16_t attr_handle, struct os_mbuf *om) {
    uint16_t len = OS_MBUF_PKTLEN(om);
    if (len != MUSE_PACKET_SIZE) return;
    
    uint8_t data[MUSE_PACKET_SIZE];
    os_mbuf_copydata(om, 0, len, data);
    
    if (attr_handle == char_handles.tp9 || attr_handle == char_handles.af7 ||
        attr_handle == char_handles.af8 || attr_handle == char_handles.tp10) {
        
        if (config.on_eeg_data) {
            muse_eeg_packet_t packet;
            if (muse_decode_eeg(data, &packet)) {
                muse_eeg_data_t eeg_data;
                eeg_data.sequence = packet.packet_num;
                memcpy(eeg_data.samples, packet.samples, sizeof(eeg_data.samples));
                
                muse_eeg_channel_t channel;
                if (attr_handle == char_handles.tp9) channel = MUSE_EEG_TP9;
                else if (attr_handle == char_handles.af7) channel = MUSE_EEG_AF7;
                else if (attr_handle == char_handles.af8) channel = MUSE_EEG_AF8;
                else channel = MUSE_EEG_TP10;
                
                config.on_eeg_data(channel, &eeg_data);
            }
        }
    } else if (attr_handle == char_handles.accel && config.on_accel_data) {
        muse_accel_packet_t packet;
        if (muse_decode_accel(data, &packet)) {
            muse_accel_data_t accel_data;
            accel_data.sequence = packet.packet_num;
            memcpy(accel_data.x, packet.x, sizeof(accel_data.x));
            memcpy(accel_data.y, packet.y, sizeof(accel_data.y));
            memcpy(accel_data.z, packet.z, sizeof(accel_data.z));
            config.on_accel_data(&accel_data);
        }
    } else if (attr_handle == char_handles.gyro && config.on_gyro_data) {
        muse_gyro_packet_t packet;
        if (muse_decode_gyro(data, &packet)) {
            muse_gyro_data_t gyro_data;
            gyro_data.sequence = packet.packet_num;
            memcpy(gyro_data.x, packet.x, sizeof(gyro_data.x));
            memcpy(gyro_data.y, packet.y, sizeof(gyro_data.y));
            memcpy(gyro_data.z, packet.z, sizeof(gyro_data.z));
            config.on_gyro_data(&gyro_data);
        }
    }
}

// GAP event handler
static int gap_event_handler(struct ble_gap_event *event, void *arg) {
    switch (event->type) {
        case BLE_GAP_EVENT_DISC: {
            struct ble_hs_adv_fields fields;
            int parse_rc = ble_hs_adv_parse_fields(&fields, event->disc.data, event->disc.length_data);
            
            // Log all discovered devices for debugging
            if (parse_rc == 0 && fields.name != NULL && fields.name_len > 0) {
                ESP_LOGD(TAG, "Discovered device: %.*s (RSSI: %d)", 
                         fields.name_len, fields.name, event->disc.rssi);
            }
            
            if (parse_rc != 0) {
                return 0;
            }
            
            // Check for Muse device
            if (fields.name != NULL && fields.name_len >= 4 &&
                strncmp((char *)fields.name, "Muse", 4) == 0) {
                
                ESP_LOGI(TAG, "Found Muse: %.*s (RSSI: %d)", fields.name_len, fields.name, event->disc.rssi);
                ble_gap_disc_cancel();
                
                set_status(MUSE_STATUS_CONNECTING);
                
                // Use relaxed connection parameters from the start
                struct ble_gap_conn_params conn_params = {
                    .scan_itvl = 16,           // 10ms
                    .scan_window = 16,         // 10ms
                    .itvl_min = 24,            // 30ms
                    .itvl_max = 40,            // 50ms
                    .latency = 0,
                    .supervision_timeout = 400, // 4 seconds
                    .min_ce_len = 0,
                    .max_ce_len = 0,
                };
                
                int rc = ble_gap_connect(BLE_OWN_ADDR_PUBLIC, &event->disc.addr, 30000, 
                                        &conn_params, gap_event_handler, NULL);
                if (rc != 0) {
                    ESP_LOGE(TAG, "Failed to initiate connection: %d", rc);
                    set_status(MUSE_STATUS_ERROR);
                }
            }
            break;
        }
        
        case BLE_GAP_EVENT_CONNECT: {
            if (event->connect.status == 0) {
                ESP_LOGI(TAG, "Connected to Muse");
                conn_handle = event->connect.conn_handle;
                set_status(MUSE_STATUS_CONNECTED);
                
                // Request more relaxed connection parameters for stability
                // Using longer intervals to give Muse more time to respond
                struct ble_gap_upd_params conn_params = {
                    .itvl_min = 24,           // 30ms (24 * 1.25ms)
                    .itvl_max = 40,           // 50ms (40 * 1.25ms)
                    .latency = 0,             // No slave latency
                    .supervision_timeout = 400, // 4 seconds (400 * 10ms)
                    .min_ce_len = 0,
                    .max_ce_len = 0,
                };
                int rc = ble_gap_update_params(conn_handle, &conn_params);
                if (rc != 0) {
                    ESP_LOGW(TAG, "Failed to update connection params: %d", rc);
                }
                
                // Small delay before service discovery to let connection stabilize
                vTaskDelay(pdMS_TO_TICKS(200));
                
                // Discover only the Muse service (faster than discovering all services)
                muse_svc_start_handle = 0;
                muse_svc_end_handle = 0;
                
                // Muse service UUID: 0xFE8D (16-bit)
                ble_uuid16_t muse_svc_uuid = BLE_UUID16_INIT(MUSE_SERVICE_UUID_16);
                
                ESP_LOGI(TAG, "Discovering Muse service (0x%04X)...", MUSE_SERVICE_UUID_16);
                rc = ble_gattc_disc_svc_by_uuid(conn_handle, &muse_svc_uuid.u, 
                                                 svc_disc_handler, NULL);
                if (rc != 0) {
                    ESP_LOGE(TAG, "Failed to start service discovery: %d", rc);
                }
            } else {
                ESP_LOGE(TAG, "Connection failed: %d", event->connect.status);
                set_status(MUSE_STATUS_ERROR);
            }
            break;
        }
        
        case BLE_GAP_EVENT_DISCONNECT: {
            ESP_LOGW(TAG, "Disconnected! reason=%d (0x%02x)", 
                     event->disconnect.reason, event->disconnect.reason);
            // Common reasons:
            // 0x13 (19) = Remote User Terminated Connection
            // 0x08 (8) = Connection Timeout
            // 0x16 (22) = Connection Terminated due to MIC Failure
            // 0x3E (62) = Connection Failed to be Established
            conn_handle = BLE_HS_CONN_HANDLE_NONE;
            memset(&char_handles, 0, sizeof(char_handles));
            params_updated_by_us = false;  // Reset for next connection
            set_status(MUSE_STATUS_DISCONNECTED);
            
            // Auto-reconnect: start scanning again
            ESP_LOGI(TAG, "Attempting to reconnect - restarting scan...");
            struct ble_gap_disc_params params = {
                .itvl = 0,
                .window = 0,
                .filter_policy = 0,
                .limited = 0,
                .passive = 0,
                .filter_duplicates = 1,
            };
            set_status(MUSE_STATUS_SCANNING);
            ble_gap_disc(BLE_OWN_ADDR_PUBLIC, config.scan_timeout_ms, &params, gap_event_handler, NULL);
            break;
        }
        
        case BLE_GAP_EVENT_DISC_COMPLETE: {
            if (current_status == MUSE_STATUS_SCANNING) {
                ESP_LOGW(TAG, "Scan timeout - Muse not found");
                set_status(MUSE_STATUS_DISCONNECTED);
            }
            break;
        }
        
        case BLE_GAP_EVENT_NOTIFY_RX: {
            handle_notification(event->notify_rx.attr_handle, event->notify_rx.om);
            break;
        }
        
        case BLE_GAP_EVENT_CONN_UPDATE: {
            ESP_LOGI(TAG, "Connection parameters updated: status=%d", event->conn_update.status);
            
            // Log the actual connection parameters
            struct ble_gap_conn_desc desc;
            int rc = ble_gap_conn_find(event->conn_update.conn_handle, &desc);
            if (rc == 0) {
                ESP_LOGI(TAG, "Current params: itvl=%d latency=%d timeout=%d",
                         desc.conn_itvl, desc.conn_latency, desc.supervision_timeout);
            }
            
            // Only request our preferred params once, after Muse sets its aggressive params
            if (event->conn_update.status == 0 && 
                current_status == MUSE_STATUS_STREAMING && 
                !params_updated_by_us) {
                
                params_updated_by_us = true;  // Prevent infinite loop
                
                // After Muse updates connection params, request more relaxed parameters
                // The Muse uses 15ms interval and 2s timeout which is too aggressive with WiFi
                // Use the maximum allowed supervision timeout (32 seconds) for stability
                struct ble_gap_upd_params our_params = {
                    .itvl_min = 24,            // 30ms (24 * 1.25ms)
                    .itvl_max = 80,            // 100ms (80 * 1.25ms)
                    .latency = 10,             // Can skip up to 10 connection events
                    .supervision_timeout = 3200, // 32 seconds (3200 * 10ms) - maximum allowed
                    .min_ce_len = 0,
                    .max_ce_len = 0,
                };
                
                ESP_LOGI(TAG, "Requesting max stability params (30-100ms, latency=10, 32s timeout)...");
                rc = ble_gap_update_params(event->conn_update.conn_handle, &our_params);
                if (rc != 0) {
                    ESP_LOGW(TAG, "Failed to request param update: %d", rc);
                }
            }
            break;
        }
        
        case BLE_GAP_EVENT_CONN_UPDATE_REQ: {
            // The Muse requests very aggressive connection parameters (15ms interval)
            // which can be unstable with WiFi coexistence. Accept but adjust if needed.
            ESP_LOGI(TAG, "Connection update requested: itvl=%d-%d, latency=%d, timeout=%d",
                     event->conn_update_req.peer_params->itvl_min,
                     event->conn_update_req.peer_params->itvl_max,
                     event->conn_update_req.peer_params->latency,
                     event->conn_update_req.peer_params->supervision_timeout);
            
            // Accept the peer's parameters but ensure minimum supervision timeout
            // to tolerate occasional WiFi interference
            event->conn_update_req.self_params->itvl_min = event->conn_update_req.peer_params->itvl_min;
            event->conn_update_req.self_params->itvl_max = event->conn_update_req.peer_params->itvl_max;
            event->conn_update_req.self_params->latency = event->conn_update_req.peer_params->latency;
            
            // Use at least 4 second supervision timeout for stability
            uint16_t peer_timeout = event->conn_update_req.peer_params->supervision_timeout;
            event->conn_update_req.self_params->supervision_timeout = 
                (peer_timeout < 400) ? 400 : peer_timeout;  // 400 * 10ms = 4 seconds
            
            ESP_LOGI(TAG, "Responding with timeout=%d (was %d)",
                     event->conn_update_req.self_params->supervision_timeout, peer_timeout);
            break;
        }
    }
    return 0;
}

// Service discovery handler
static int svc_disc_handler(uint16_t conn_hdl, const struct ble_gatt_error *error,
                            const struct ble_gatt_svc *service, void *arg) {
    ESP_LOGI(TAG, "Service discovery callback: status=%d", error->status);
    
    if (error->status == 0 && service != NULL) {
        ESP_LOGI(TAG, "Found service: start=%d end=%d", 
                 service->start_handle, service->end_handle);
        muse_svc_start_handle = service->start_handle;
        muse_svc_end_handle = service->end_handle;
    } else if (error->status == BLE_HS_EDONE) {
        if (muse_svc_start_handle != 0) {
            ESP_LOGI(TAG, "Muse service found (handles %d-%d), discovering characteristics...",
                     muse_svc_start_handle, muse_svc_end_handle);
            int rc = ble_gattc_disc_all_chrs(conn_hdl, muse_svc_start_handle, 
                                             muse_svc_end_handle, chr_disc_handler, NULL);
            if (rc != 0) {
                ESP_LOGE(TAG, "Failed to start characteristic discovery: %d", rc);
            }
        } else {
            ESP_LOGE(TAG, "Muse service (0x%04X) not found!", MUSE_SERVICE_UUID_16);
            set_status(MUSE_STATUS_ERROR);
        }
    } else {
        ESP_LOGE(TAG, "Service discovery error: %d", error->status);
    }
    return 0;
}

// Characteristic discovery handler  
static int chr_disc_handler(uint16_t conn_hdl, const struct ble_gatt_error *error,
                            const struct ble_gatt_chr *chr, void *arg) {
    if (error->status == 0 && chr != NULL) {
        if (chr->uuid.u.type == BLE_UUID_TYPE_128) {
            const ble_uuid128_t *uuid128 = (const ble_uuid128_t *)&chr->uuid;
            uint16_t char_id = uuid128->value[12] | (uuid128->value[13] << 8);
            
            switch (char_id) {
                case MUSE_CHAR_CONTROL: char_handles.control = chr->val_handle; break;
                case MUSE_CHAR_TP9:     char_handles.tp9 = chr->val_handle; break;
                case MUSE_CHAR_AF7:     char_handles.af7 = chr->val_handle; break;
                case MUSE_CHAR_AF8:     char_handles.af8 = chr->val_handle; break;
                case MUSE_CHAR_TP10:    char_handles.tp10 = chr->val_handle; break;
                case MUSE_CHAR_GYRO:    char_handles.gyro = chr->val_handle; break;
                case MUSE_CHAR_ACCEL:   char_handles.accel = chr->val_handle; break;
            }
        }
    } else if (error->status == BLE_HS_EDONE) {
        if (char_handles.control && char_handles.tp9 && char_handles.af7 &&
            char_handles.af8 && char_handles.tp10) {
            // Start subscription task
            xTaskCreate(streaming_task, "muse_stream", 4096, NULL, 5, NULL);
        } else {
            ESP_LOGE(TAG, "Missing required characteristics");
            set_status(MUSE_STATUS_ERROR);
        }
    }
    return 0;
}

// BLE host task
static void ble_host_task(void *param) {
    ESP_LOGI(TAG, ">>> BLE HOST TASK STARTED <<<");
    ESP_LOGI(TAG, "Task priority: %d, Core: %d", uxTaskPriorityGet(NULL), xPortGetCoreID());
    ESP_LOGI(TAG, "Calling nimble_port_run()...");
    nimble_port_run();
    ESP_LOGI(TAG, "nimble_port_run() returned, deinitializing...");
    nimble_port_freertos_deinit();
}

static void on_ble_reset(int reason) {
    ESP_LOGE(TAG, "BLE reset: %d", reason);
}

static void on_ble_sync(void) {
    ESP_LOGI(TAG, "=== BLE SYNC CALLBACK INVOKED ===");
    ESP_LOGI(TAG, "BLE sync complete, starting scan...");
    
    // Start scanning with active scan to get device names
    struct ble_gap_disc_params params = {
        .itvl = 0,              // Use default interval
        .window = 0,            // Use default window  
        .filter_policy = 0,     // No whitelist
        .limited = 0,           // General discovery
        .passive = 0,           // Active scanning (sends scan requests)
        .filter_duplicates = 1, // Filter duplicate advertisements
    };
    
    set_status(MUSE_STATUS_SCANNING);
    ESP_LOGI(TAG, "Calling ble_gap_disc with timeout %lu ms...", (unsigned long)config.scan_timeout_ms);
    
    int rc = ble_gap_disc(BLE_OWN_ADDR_PUBLIC, config.scan_timeout_ms, &params, gap_event_handler, NULL);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to start scan, error code: %d", rc);
        if (rc == BLE_HS_EALREADY) {
            ESP_LOGE(TAG, "  -> Scan already in progress");
        } else if (rc == BLE_HS_EBUSY) {
            ESP_LOGE(TAG, "  -> BLE host is busy");
        } else if (rc == BLE_HS_EDONE) {
            ESP_LOGE(TAG, "  -> Operation already complete");
        }
    } else {
        ESP_LOGI(TAG, "BLE scan started successfully! Scanning for %lu ms...", (unsigned long)config.scan_timeout_ms);
    }
}

// Public API implementation

void muse_controller_get_default_config(muse_config_t *cfg) {
    memset(cfg, 0, sizeof(muse_config_t));
    cfg->enable_accelerometer = true;
    cfg->enable_gyroscope = true;
    cfg->scan_timeout_ms = 30000;
}

int muse_controller_init(const muse_config_t *cfg) {
    if (initialized) {
        return -1;
    }
    
    // Copy config
    if (cfg) {
        memcpy(&config, cfg, sizeof(muse_config_t));
    } else {
        muse_controller_get_default_config(&config);
    }
    
    ESP_LOGI(TAG, "Scan timeout configured: %lu ms", (unsigned long)config.scan_timeout_ms);
    
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS needs erase, erasing...");
        nvs_flash_erase();
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: %d", ret);
        return -1;
    }
    ESP_LOGI(TAG, "NVS initialized");
    
    // Initialize NimBLE
    ESP_LOGI(TAG, "Initializing NimBLE port...");
    ret = nimble_port_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NimBLE init failed: %d", ret);
        return -1;
    }
    ESP_LOGI(TAG, "NimBLE port initialized");
    
    // Configure host
    ESP_LOGI(TAG, "Configuring BLE host callbacks...");
    ble_hs_cfg.reset_cb = on_ble_reset;
    ble_hs_cfg.sync_cb = on_ble_sync;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;
    
    // Initialize the NimBLE store (required for BLE host to sync)
    ESP_LOGI(TAG, "Initializing BLE store...");
    ble_store_config_init();
    
    initialized = true;
    ESP_LOGI(TAG, "Muse controller initialized successfully");
    
    return 0;
}

static TaskHandle_t ble_host_task_handle = NULL;

int muse_controller_start(void) {
    if (!initialized) {
        ESP_LOGE(TAG, "Cannot start - not initialized");
        return -1;
    }
    
    // Start BLE host task manually with error checking
    ESP_LOGI(TAG, "Creating BLE host task...");
    ESP_LOGI(TAG, "Free heap: %lu bytes, min free: %lu bytes", 
             (unsigned long)esp_get_free_heap_size(),
             (unsigned long)esp_get_minimum_free_heap_size());
    
    BaseType_t ret = xTaskCreatePinnedToCore(
        ble_host_task,
        "nimble_host",
        4096,
        NULL,
        (configMAX_PRIORITIES - 4),
        &ble_host_task_handle,
        0  // Core 0
    );
    
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create BLE host task! ret=%d (likely out of memory)", ret);
        ESP_LOGE(TAG, "Free heap after attempt: %lu bytes", (unsigned long)esp_get_free_heap_size());
        return -1;
    }
    
    ESP_LOGI(TAG, "BLE host task created successfully, handle=%p", (void*)ble_host_task_handle);
    
    // Give the BLE task time to start and sync
    // The sync callback may take a moment to fire
    for (int i = 0; i < 50; i++) {
        vTaskDelay(pdMS_TO_TICKS(100));
        if (current_status == MUSE_STATUS_SCANNING) {
            ESP_LOGI(TAG, "BLE sync complete, scanning started");
            break;
        }
        if (i % 10 == 0) {
            ESP_LOGI(TAG, "Waiting for BLE sync... (%d00ms)", i);
        }
    }
    
    if (current_status != MUSE_STATUS_SCANNING) {
        ESP_LOGW(TAG, "BLE sync did not complete within 5 seconds");
    }
    
    return 0;
}

int muse_controller_stop(void) {
    if (current_status == MUSE_STATUS_STREAMING) {
        send_command("h");
    }
    
    if (conn_handle != BLE_HS_CONN_HANDLE_NONE) {
        ble_gap_terminate(conn_handle, BLE_ERR_REM_USER_CONN_TERM);
    }
    
    return 0;
}

muse_status_t muse_controller_get_status(void) {
    return current_status;
}

bool muse_controller_is_streaming(void) {
    return current_status == MUSE_STATUS_STREAMING;
}

const char* muse_controller_get_channel_name(muse_eeg_channel_t channel) {
    switch (channel) {
        case MUSE_EEG_TP9:  return "TP9";
        case MUSE_EEG_AF7:  return "AF7";
        case MUSE_EEG_AF8:  return "AF8";
        case MUSE_EEG_TP10: return "TP10";
        default:           return "Unknown";
    }
}
