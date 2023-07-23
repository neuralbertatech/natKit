#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.common.kafka import KafkaManager


def close_streams(streams):
    for stream in streams:
        stream.close()


def read_data():
    manager = KafkaManager.create()

    while True:
        streams = manager.find_streams()
        for i, stream in enumerate(streams):
            print("({}) - {}-{}".format(i, stream.get_name(), stream.get_id()))
        print("({}) - Exit".format(len(streams)))
        print("(all) - Delete all\n")

        input_string = input("Select an option [{}-{}]: ".format(0, len(streams)))
        selections = []
        if input_string == "all":
            selections = range(len(streams))
        else:
            selections = [int(s) for s in input_string.split(" ")]

        for selection in selections:
            if selection >= len(streams):
                close_streams(streams)
                return

            manager.delete_stream(streams[selection])

        time.sleep(0.5)


if __name__ == "__main__":
    read_data()
