#pragma once

#include <string>

namespace natKit {

enum class TopicType {
  UNKNOWN,
  TOPIC_LISTING,
  DATA_SCHEMA,
  RAW_INPUT_DATA,
  PROCESSED_DATA,
};

struct Topic {
  const std::string topic;
  const TopicType type;

  explicit Topic(const std::string& topicString) : topic(topicString), type(Topic::getType(topicString)) {}

  auto operator<=>(const Topic&) const = default;

  static Topic createTopicListingTopic() {
    return Topic("data-stream-listing");
  }

  static Topic createDataSchemaTopic(const Topic& schemaOf) {
    return Topic(schemaOf.topic + "-schema");
  }

  static Topic createRawInputDataTopic(const std::string& dataDeviceName) {
    return Topic(dataDeviceName + "-XXXX-input-data-stream");
  }

  static Topic createProcessedDataTopic(const Topic& rawInputDataTopic) {
    return Topic(rawInputDataTopic.topic + "-processed-data-stream-XXXX");
  }

  static TopicType getType(const std::string& topic) {
    if (topic == "data-stream-listing") {
      return TopicType::TOPIC_LISTING;
    } else if (topic.ends_with("-schema")) {
      return TopicType::DATA_SCHEMA;
    } else if (topic.ends_with("-input-data-stream")) {
      return TopicType::RAW_INPUT_DATA;
    } else if (topic.find("-processed-data-stream-") != std::string::npos) {
      return TopicType::PROCESSED_DATA;
    } else {
      return TopicType::UNKNOWN;
    }
  }

  std::string toString() const {
    return topic;
  }
};

}
