#!/usr/bin/env python

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from natKit.common.kafka import KafkaManager


def delete_topics():
    manager = KafkaManager.create()
    manager.delete_all_topics()
    time.sleep(10)


if __name__ == "__main__":
    delete_topics()
