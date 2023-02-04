#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.common.kafka import TopicManager


def read_data():
    manager = TopicManager()

    streams = manager.find_all_streams()
    for i, stream in enumerate(streams):
        print("({}) - {}-{}".format(i, stream.get_name(), stream.get_id()))
    print("({}) - Exit\n".format(len(streams)))

    selection = int(input("Select an option [{}-{}]: ".format(0, len(streams))))
    if selection >= len(streams):
        return

    stream = streams[selection]
    while True:
        data = stream.read_data()
        if data is not None:
            print(data.value())
        time.sleep(0.001)


if __name__ == "__main__":
    read_data()
