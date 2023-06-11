#!/usr/bin/env python3

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.api import BasicMetaInfoSchema
from natKit.api import CsvEncoder
from natKit.api import SimpleMessageSchema
from natKit.common.kafka import KafkaManager


def create_stream():
    manager = KafkaManager.create()

    name = input("Enter name for new string: ")
    encoder = CsvEncoder
    stream = manager.create_stream(name, encoder, SimpleMessageSchema, encoder, BasicMetaInfoSchema)
    time.sleep(5)
    stream.write_meta(BasicMetaInfoSchema(name))
    time.sleep(5)
    print("Done")


if __name__ == "__main__":
    create_stream()
