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
        nvs_flash
)

# NOTE: cJSON (the old built-in `json` component) and esp-mqtt (the old built-in
# `mqtt` component) were removed from ESP-IDF core in v6.0 and moved to the ESP
# Component Registry. They are declared as managed dependencies in
# main/idf_component.yml (espressif/cjson, espressif/mqtt) instead of REQUIRES;
# the component manager fetches them and exposes them to this component. The
# cJSON.h / mqtt_client.h APIs are unchanged.

# Transport selection is now a *runtime* mode seeded from a menuconfig choice
# (see main/Kconfig.projbuild -> CONFIG_NATVR_TRANSPORT_WIRELESS|AUTO|SERIAL, and
# TransportMode in main.cpp). Select it interactively with `idf.py menuconfig` or
# headless via sdkconfig.defaults (e.g. sdkconfig.defaults.demo pins AUTO).
#
# Back-compat: the previous mutually-exclusive serial image built with
#   idf.py -DNATVR_TRANSPORT_SERIAL=1 build
# still works -- the define maps to the SERIAL choice at compile time.
if(NATVR_TRANSPORT_SERIAL)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE NATVR_TRANSPORT_SERIAL=1)
endif()
