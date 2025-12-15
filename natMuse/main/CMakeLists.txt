idf_component_register(
    SRCS
        "main.cpp"
        "muse_controller.c"
        "muse_protocol.c"
        "muse_cpp_wrapper.cpp"
        "muse_data_buffer.cpp"
        "networking.cpp"
    PRIV_REQUIRES
        bt
        nvs_flash
        esp_wifi
        esp_event
        esp_netif
        mqtt
        libnatkit-core
    INCLUDE_DIRS "."
)
