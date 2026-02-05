# The following lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

# Determine target chip (h2 or s3)
# Set via CMakePresets.json or command line: -DNATMUSE_TARGET=h2
if(NOT DEFINED NATMUSE_TARGET)
    message(FATAL_ERROR "NATMUSE_TARGET not defined. Use CMake presets: --preset h2 or --preset s3")
endif()

message(STATUS "Building natMuse for target: ${NATMUSE_TARGET}")

# Add libnatkit-core as an extra component directory (S3 only - for schema serialization)
if(NATMUSE_TARGET STREQUAL "s3")
    set(EXTRA_COMPONENT_DIRS
        "${CMAKE_CURRENT_SOURCE_DIR}/../libnatkit/lib/libnatkit-core"
        "${CMAKE_CURRENT_SOURCE_DIR}/components"
    )
else()
    # H2 only needs the shared component
    set(EXTRA_COMPONENT_DIRS
        "${CMAKE_CURRENT_SOURCE_DIR}/components"
    )
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(natMuse)
