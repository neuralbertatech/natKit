# Conditional source file selection based on target chip
# NATMUSE_TARGET is set in the parent CMakeLists.txt via CMakePresets

if(NATMUSE_TARGET STREQUAL "h2")
    # ESP32-H2: BLE controller
    # Handles Muse BLE connection and sends data to S3 via SPI
    set(NATMUSE_SRCS
        "h2/main_h2.cpp"
        "h2/spi_master.cpp"
        "muse_controller.c"
        "muse_protocol.c"
        "muse_cpp_wrapper.cpp"
    )
    set(NATMUSE_REQUIRES
        bt
        nvs_flash
        driver
        natmuse_common
    )
    set(NATMUSE_INCLUDE_DIRS
        "."
        "h2"
    )
elseif(NATMUSE_TARGET STREQUAL "s3")
    # ESP32-S3: WiFi controller
    # Receives data from H2 via SPI and publishes to MQTT
    set(NATMUSE_SRCS
        "s3/main_s3.cpp"
        "s3/spi_slave.cpp"
        "muse_data_buffer.cpp"
        "networking.cpp"
    )
    set(NATMUSE_REQUIRES
        nvs_flash
        esp_wifi
        esp_event
        esp_netif
        mqtt
        driver
        libnatkit-core
        natmuse_common
    )
    set(NATMUSE_INCLUDE_DIRS
        "."
        "s3"
    )
else()
    message(FATAL_ERROR "Unknown NATMUSE_TARGET: ${NATMUSE_TARGET}. Expected 'h2' or 's3'.")
endif()

idf_component_register(
    SRCS
        ${NATMUSE_SRCS}
    PRIV_REQUIRES
        ${NATMUSE_REQUIRES}
    INCLUDE_DIRS
        ${NATMUSE_INCLUDE_DIRS}
)

# Add compile definition for target-specific code paths
if(NATMUSE_TARGET STREQUAL "s3")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE NATMUSE_TARGET_S3=1)
elseif(NATMUSE_TARGET STREQUAL "h2")
    target_compile_definitions(${COMPONENT_LIB} PRIVATE NATMUSE_TARGET_H2=1)
endif()
