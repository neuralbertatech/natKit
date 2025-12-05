#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

import time
import random

from natKit.api import Meta
from natKit.common.board import ExgPill
from natKit.common.connector import Serial
from natKit.common.kafka import TopicManager


def read_data():
    exg_pill = Serial("/dev/ttyACM0", 115200)
    manager = TopicManager()
    meta = Meta(name="Exg-Pill", number_of_channels=5)
    stream = manager.build_stream(meta)
    print("Writing to {}-{}".format(stream.meta.name, stream.get_id()))
    stream.write_meta()
    while True:
        line = exg_pill.readline()
        try:
            split_string = line.split(",")
            data = [int(s) for s in split_string]
            stream.write_data(data)
        except Exception as e:
            print(e)
            print('Warning: Malformed data "{}"'.format(line))


if __name__ == "__main__":
    read_data()
