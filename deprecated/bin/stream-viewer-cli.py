#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.api import BasicMetaInfoSchema
from natKit.api import CsvEncoder
from natKit.api import SimpleMessageSchema
from natKit.common.kafka import KafkaManager


def read_stream():
    manager = KafkaManager.create()
    streams = manager.find_streams()

    for i, stream in enumerate(streams):
        print("({}) - {} -- ({})".format(i, stream.get_name(), stream.get_id()))
    print("({}) - Exit\n".format(len(streams)))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(streams))))
    if selection >= len(streams):
        return

    for i, stream in enumerate(streams):
        if i != selection:
            stream.close()

    stream = streams[selection]
    try:
        while True:
            data = stream.read_data()
            if data is not None:
                print(data)
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        stream.close()


if __name__ == "__main__":
    read_stream()
