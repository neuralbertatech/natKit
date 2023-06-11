#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.common.kafka import KafkaManager


def read_data():
    manager = KafkaManager.create()

    topic_names = manager.query_topic_names()
    for i, topic_name in enumerate(topic_names):
        print("({}) {}".format(i, topic_name))
    print("({}) - Exit\n".format(len(topic_names)))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(topic_names))))
    if selection >= len(topic_names):
        return

    topic_connection = manager.get_topic_connection(topic_names[selection])
    print("Reading data from: {}".format(topic_connection.topic_name.topic_string))
    try:
        while True:
            data = topic_connection.read()
            if data is not None:
                print("{}".format(data.value()))
    except Exception as e:
        print(e)
        topic_connection.stop()


if __name__ == "__main__":
    read_data()
