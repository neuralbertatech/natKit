idf_component_register(
    SRCS
        "main.cpp"
        "networking.cpp"
    INCLUDE_DIRS
        "."
    REQUIRES
        esp_adc
        esp_event
        esp_netif
        esp_wifi
        json
        mqtt
        nvs_flash
)

# Transport selection. Build the USB-serial backup image with:
#   idf.py -DNATVR_TRANSPORT_SERIAL=1 build
# Default (unset / 0) builds the WiFi/MQTT image. networking.cpp is always
# compiled (it still provides the local clock accessor), so the esp_wifi/mqtt
# components stay required regardless of transport.
if(NATVR_TRANSPORT_SERIAL)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE NATVR_TRANSPORT_SERIAL=1)
endif()
