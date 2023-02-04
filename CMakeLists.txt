cmake_minimum_required(VERSION 3.13.0)
project(natKit CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O0 -g -Wall -Wshadow -Wunused-function -Wunused -Wno-system-headers -Wno-deprecated")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
set(NAT_KIT_CXX_FLAGS "")
option(ENABLE_TESTS "Enable tests" ON)
find_program(LLVM_COV_PATH llvm-cov)

if(CMAKE_BUILD_TYPE STREQUAL "Coverage" OR CODE_COVERAGE)
    if("${CMAKE_C_COMPILER_ID}" MATCHES "(Apple)?[Cc]lang" OR "${CMAKE_CXX_COMPILER_ID}" MATCHES "(Apple)?[Cc]lang")
        message("Building with llvm Code Coverage Tools")

        # Warning/Error messages
        if(NOT LLVM_COV_PATH)
            message(FATAL_ERROR "llvm-cov not found! Aborting.")
        endif()

        # set Flags
        #set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -fprofile-instr-generate -fcoverage-mapping")
        set(NAT_KIT_CXX_FLAGS "${NAT_KIT_CXX_FLAGS} -fprofile-instr-generate -fcoverage-mapping")

    elseif(CMAKE_COMPILER_IS_GNUCXX)
        message("Building with lcov Code Coverage Tools")

        # Warning/Error messages
        if(NOT (CMAKE_BUILD_TYPE STREQUAL "Debug"))
            message(WARNING "Code coverage results with an optimized (non-Debug) build may be misleading")
        endif()
        if(NOT LCOV_PATH)
            message(FATAL_ERROR "lcov not found! Aborting...")
        endif()
        if(NOT GENHTML_PATH)
            message(FATAL_ERROR "genhtml not found! Aborting...")
        endif()

        #set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} --coverage -fprofile-arcs -ftest-coverage")
        set(NAT_KIT_CXX_FLAGS "${NAT_KIT_CXX_FLAGS} --coverage -fprofile-arcs -ftest-coverage")
    else()
        message(FATAL_ERROR "Code coverage requires Clang or GCC. Aborting.")
    endif()
endif()

#add_library(natKitCommon SHARED)
#add_subdirectory(src/common)

set(KAFKA_CPP_INCLUDES_DIR "${PROJECT_SOURCE_DIR}/third-party/modern-cpp-kafka/include")
set(COMMON_CPP_INCLUDES_DIR "${PROJECT_SOURCE_DIR}/src")
add_subdirectory(src/server)


if(${ENABLE_TESTS})
  add_subdirectory(third-party/Catch2)
  add_subdirectory(test)
endif()
