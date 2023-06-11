#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.common.kafka import KafkaManager
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType


def write_data():
    manager = KafkaManager.create()

    topic_names = manager.query_topic_names()
    for i, topic_name in enumerate(topic_names):
        print("({}) {}".format(i, topic_name))
    print("({}) - New Topic\n".format(len(topic_names)))
    print("({}) - Exit\n".format(len(topic_names)+1))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(topic_names))))
    if selection == len(topic_names):
        data_topic_name = TopicName(type=TopicType.DATA)
        meta_topic_name = TopicName(type=TopicType.META)
        manager.create_topic(data_topic_name.topic_string)
        manager.create_topic(meta_topic_name.topic_string)
        return
    elif selection > len(topic_names):
        return

    topic_connection = manager.get_topic_connection(topic_names[selection])
    print("Writing data to: {}".format(topic_connection.topic_name.topic_string))
    try:
        while True:
            data = input("")
            topic_connection.write(data)
    except Exception as e:
        print(e)
        topic_connection.stop()


if __name__ == "__main__":
    write_data()
