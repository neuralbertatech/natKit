#pragma once

#include <iostream>
#include <memory>
#include <kafka/AdminClient.h>
#include <kafka/Properties.h>


namespace natKit {

class KafkaConnection {
  kafka::Properties properties;
  std::unique_ptr<kafka::clients::admin::AdminClient> client;
  public:
    KafkaConnection() {
      properties.put<std::string>("bootstrap.servers",  "127.0.0.1:9092");
      client = std::make_unique<kafka::clients::admin::AdminClient>(properties);
    }

    void printTopics() const {
      for (const auto& topic : client->listTopics().topics)
        std::cout << topic << ' ';
      std::cout << '\n';
    }

    void addTopic(const std::string& topicName) {
      client->createTopics({topicName}, 1, 1);
    }
};

}
