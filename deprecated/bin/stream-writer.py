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


def write_stream():
    manager = KafkaManager.create()
    streams = manager.find_streams()

    for i, stream in enumerate(streams):
        print("({}) - {} -- ({})".format(i, stream.get_name(), stream.get_id()))
    print("({}) - Exit\n".format(len(streams)))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(streams))))
    if selection >= len(streams):
        return

    stream = streams[selection]
    while True:
        data_to_write = input("> ")
        message = SimpleMessageSchema(data_to_write)
        stream.write_data(message)


if __name__ == "__main__":
    write_stream()
