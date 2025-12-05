add_executable(natKitServer main.cpp)

#find_package(RdKafka)
target_link_libraries(natKitServer PUBLIC rdkafka)
#target_link_libraries(natKitServer PUBLIC natKitCommon)
target_include_directories(natKitServer PUBLIC ${KAFKA_CPP_INCLUDES_DIR})
target_include_directories(natKitServer PUBLIC ${COMMON_CPP_INCLUDES_DIR})

add_subdirectory(cxx)
