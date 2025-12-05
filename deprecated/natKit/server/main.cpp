#include <iostream>
#include <server/cxx/KafkaManager.hpp>
#include <common/cxx/util/toString.hpp>

int main() {
  std::cout << "Welcome to natKit\n";
  auto kafkaManager = natKit::KafkaManager::create();
  const auto topics = kafkaManager.getTopics();
  const auto topicListingTopic = natKit::Topic::createTopicListingTopic();

  if (topics.isOk()) {
    std::cout << "Topics on the broker are: " <<
      natKit::toString(topics.getValue()) << '\n';

    if (not topics.getValue().contains(topicListingTopic)) {
      std::cout << "Adding " << natKit::toString(topicListingTopic) << " to the broker\n";
      kafkaManager.addTopic(topicListingTopic.topic);
    }
  } else {
    std::cout << "Error when attempting to connect to the broker: "
      << topics.getError() << '\n';
  }


  return 0;
}
