#include <catch2/catch_test_macros.hpp>
#include <common/cxx/kafka/topic.hpp>
#include <common/cxx/util/toString.hpp>

namespace natKit {

TEST_CASE("Test UNKNOWN Topic", "[Topic]") {
  REQUIRE(TopicType::UNKNOWN == Topic("Hello World").type);
}

TEST_CASE("Test TOPIC_LISTING Topic", "[Topic]") {
  REQUIRE(TopicType::TOPIC_LISTING == Topic("data-stream-listing").type);
}

TEST_CASE("Test DATA_SCHEMA Topic", "[Topic]") {
  REQUIRE(TopicType::DATA_SCHEMA == Topic("Muse2-0000-schema").type);
}

TEST_CASE("Test RAW_INPUT_DATA Topic", "[Topic]") {
  REQUIRE(TopicType::RAW_INPUT_DATA == Topic("Muse2-0000-input-data-stream").type);
}

TEST_CASE("Test PROCESSED_DATA Topic", "[Topic]") {
  REQUIRE(TopicType::PROCESSED_DATA == Topic("Muse2-0000-processed-data-stream-0000").type);
}

TEST_CASE("Test toString", "[Topic]") {
  REQUIRE("Muse2-0000-processed-data-stream-0000" == toString(Topic("Muse2-0000-processed-data-stream-0000")));
}

}
