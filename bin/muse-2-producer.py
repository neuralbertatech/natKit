#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

import time
import random

from natKit.api import Meta
from natKit.common.board import Muse2
from natKit.common.connector import Serial
from natKit.common.kafka import TopicManager


def read_data():
    muse2 = Muse2("/dev/ttyACM0")
    manager = TopicManager()
    meta = Meta(
        name="Muse2",
        number_of_channels=(
            len(muse2.get_exg_channels) + len(muse2.get_marker_channels)
        ),
    )
    stream = manager.build_stream(meta)
    print("Writing to {}-{}".format(stream.meta.name, stream.get_id()))
    stream.write_meta()
    while True:
        data = muse2.get_data_quantity(1)
        if data is None:
            time.sleep(0.001)
            continue
        try:
            stream.write_data(data)
        except Exception as e:
            print(e)
            print('Warning: Malformed data "{}"'.format(data))


if __name__ == "__main__":
    read_data()
