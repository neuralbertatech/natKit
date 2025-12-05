#pragma once

#include <iostream>
#include <memory>
#include <kafka/AdminClient.h>
#include <kafka/Properties.h>
#include <common/cxx/kafka/topic.hpp>
#include <common/cxx/util/result.hpp>


namespace natKit {

class KafkaManager {
  const kafka::Properties properties;
  kafka::clients::admin::AdminClient client;
    KafkaManager(const kafka::Properties& props) : properties(props), client(props) {}

  public:
    static KafkaManager create(int brokerPort=9092, const std::string& brokerIp="127.0.0.1") {
      kafka::Properties props;
      const auto brokerAddress = brokerIp + ":" + std::to_string(brokerPort);
      props.put("bootstrap.servers", brokerAddress);
      return KafkaManager(props);
    }

    Result<std::set<Topic>, std::string> getTopics() {
      std::set<Topic> topics;
      const auto topicsList = client.listTopics();
      if (topicsList.error) {
        return Err(topicsList.error.toString());
      }

      for (const auto& topic : client.listTopics().topics) {
        topics.emplace(topic);
      }
      return Ok(topics);
    }

    void addTopic(const std::string& topicName) {
      client.createTopics({topicName}, 1, 1);
    }
};

}
