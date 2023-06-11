#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.api.schemas import MetaSchema
from natKit.common.kafka import KafkaManager
from natKit.common.kafka import Messenger


def read_data():
    manager = KafkaManager.create()
    topic = "data-124891479184-json-MetaSchema"
    messenger = manager.create_messenger(topic)

    while True:
        metaSchema = messenger.read()
        if metaSchema is not None:
            print(metaSchema)
        time.sleep(0.1)

def find_streams():
    manager = KafkaManager.create()
    streams = manager.find_streams()

    print(streams)
    return
    while True:
        metaSchema = messenger.read()
        if metaSchema is not None:
            print(metaSchema)
        time.sleep(0.1)


if __name__ == "__main__":
    find_streams()
