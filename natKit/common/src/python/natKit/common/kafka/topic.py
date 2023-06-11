from confluent_kafka import Consumer
from confluent_kafka import Producer
from confluent_kafka import TopicPartition

from dataclasses import dataclass

from enum import Enum

from multiprocessing import Process

from natKit.api import Encoding
from natKit.api import SchemaRegistry
from natKit.api import Serializer
from natKit.common.util import Fifo

from threading import Thread

from time import sleep

from typing import List
from typing import NoReturn

from random import randint

import re
import sys


class TopicType(Enum):
    UNKNOWN = 0
    META = 1
    DATA = 2


@dataclass
class TopicName:
    id: int
    type: TopicType
    topic_string: str

    def __init__(
        self,
        id: int,
        type: TopicType,
        encoder_name: str,
        schema_name: str,
        topic_string: str = None,
    ):
        self.id = id
        self.type = type
        self.encoder_name = encoder_name
        self.schema_name = schema_name
        self.topic_string = topic_string

        if self.id is None:
            self.id = randint(1, 2**31)

        # TODO This check is pretty clumsy and should be removed
        if self.topic_string is None:
            self.topic_string = TopicName.topic_name_to_topic_string(self)

    def __str__(self):
        return 'Topic: [id: {}, type: {}, topic_string: "{}", encoder_name: "{}", schema_name: "{}"]'.format(
            self.id, self.type, self.topic_string, self.encoder_name, self.schema_name
        )

    @staticmethod
    def topic_name_to_topic_string(topic) -> str:
        topic_type_string = ""
        if topic.type == TopicType.META:
            topic_type_string = "meta"
        elif topic.type == TopicType.DATA:
            topic_type_string = "data"
        else:
            print(topic)
            assert 0, "Missing Enum type!"

        return "{}-{}-{}-{}".format(topic_type_string, topic.id, topic.encoder_name, topic.schema_name)

    @staticmethod
    def parse_from_topic_string(topic_string: str):
        topic_id = None
        topic_type = TopicType.UNKNOWN
        topic_encoding = Encoding.RAW
        topic_schema = None

        split_topic_string = topic_string.split("-")
        assert len(split_topic_string) == 4, "Invalid topic string {}".format(topic_string)

        topic_id = int(split_topic_string[1])
        topic_type_string = split_topic_string[0]
        topic_encoding = split_topic_string[2]
        topic_schema = split_topic_string[3]
        if topic_type_string == "meta":
            topic_type = TopicType.META
        elif topic_type_string == "data":
            topic_type = TopicType.DATA
        else:
            assert 0, 'Invalid topic type "{}"'.format(topic_type_string)

        return TopicName(id=topic_id, type=topic_type, topic_string=topic_string, encoder_name=topic_encoding, schema_name=topic_schema)


class PartitionMetadata:
    def __init__(self):
        pass


class TopicMetadata:
    def __init__(self, topic_name: str, partition_metadata: List[PartitionMetadata], error) -> NoReturn:
        self.topic_name = topic_name
        self.partition_metadata = partition_metadata
        self.error = error


class Topic(Thread):
    def __init__(
        self,
        topic_name: TopicName,
        topic_partitions: TopicPartition,
        consumer_config: dict,
        producer_config: dict,
    ):
        super().__init__()

        self.topic_name = topic_name
        self.topic_partitions = topic_partitions
        self.consumer_config = consumer_config
        self.producer_config = producer_config
        self.consumer = Consumer(self.consumer_config)
        self.producer = Producer(self.producer_config)

        self._do_read_data = True
        self.ready_to_read = False
        self.fifo = Fifo(4096)
        self.last_message = None
        self.messages_sent_since_last_flush = 0
        self.max_messages_between_flushes = 64
        self.start()

    def run(self):
        partition_topics = [partition.topic for partition in self.topic_partitions]
        if partition_topics != []:
            self.consumer.subscribe(
                [partition.topic for partition in self.topic_partitions]
            )

        while True:
            messages = self.consumer.consume(8, timeout=5.0)
            if messages != []:
                messages_to_keep = []
                for msg in messages:
                    if msg is None:
                        continue
                    elif msg.error():
                        # TODO: Add error logging here
                        print(msg.error())
                    else:
                        messages_to_keep.append(msg)
                if len(messages_to_keep) > 0:
                    self.last_message = messages_to_keep[-1]
                    self.fifo.extend(messages_to_keep)
            self.ready_to_read = True
            if not self._do_read_data:
                break

    def write(self, data: bytes) -> NoReturn:
        self.producer.produce(self.topic_name.topic_string, data)
        self._increment_write_count()

    def pop(self):
        data = self.fifo.pop_one()
        return data

    def close(self):
        self.do_read_data = False
        self.reader_process.join()

    def _increment_write_count(self):
        self.messages_sent_since_last_flush += 1
        if self.messages_sent_since_last_flush > self.max_messages_between_flushes:
            self.producer.flush()
