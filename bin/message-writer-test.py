#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.api.schemas import MetaSchema
from natKit.common.kafka import KafkaManager
from natKit.common.kafka import Messenger


def write_data():
    manager = KafkaManager.create()
    topic = "data-124891479184-json-MetaSchema"
    manager.create_topic(topic)
    messenger = manager.create_messenger(topic)

    #topic_names = manager.query_topic_names()
    #for i, topic_name in enumerate(topic_names):
    #    print("({}) {}".format(i, topic_name))
    #print("({}) - New Topic\n".format(len(topic_names)))
    #print("({}) - Exit\n".format(len(topic_names)+1))

    #selection = int(input("Select an option [{}-{}]: ".format(0, len(topic_names))))
    #if selection == len(topic_names):
    #    return
    #elif selection > len(topic_names):
    #    return

    #topic_connection = manager.get_topic_connection(topic_names[selection])
    #print("Writing data to: {}".format(topic_connection.topic_name.topic_string))
    while True:
        name = input("Name: ")
        schema = input("Schema: ")
        metaSchema = MetaSchema(name, schema)
        messenger.write(metaSchema)


if __name__ == "__main__":
    write_data()
