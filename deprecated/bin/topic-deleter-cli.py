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
    print("({}) - Exit\n".format(len(topic_names)))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(topic_names))))
    if selection >= len(topic_names):
        return

    manager.delete_topic(topic_names[selection])
    time.sleep(10)


if __name__ == "__main__":
    write_data()
