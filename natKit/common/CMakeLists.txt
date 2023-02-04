set(common-source-files
  cxx/kafka/topic.hpp
  cxx/util/result.hpp
  cxx/util/toString.hpp
)

target_sources(natKitCommon PRIVATE ${common-source-files})

SET(common-test-files
  cxx/kafka/topicTest.cpp
  cxx/util/toStringTest.cpp
  cxx/util/resultTest.cpp
)

add_executable(common-test ${common-test-files})
target_include_directories(common-test PUBLIC ${COMMON_CPP_INCLUDES_DIR})
target_link_libraries(common-test PRIVATE Catch2::Catch2WithMain)
add_test(
  NAME common-test
  COMMAND $<TARGET_FILE:common-test>
  )
