import concurrent
import logging
import os
import random

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient

from typing import NoReturn

from natKit.api import Meta
from natKit.common.kafka import Stream, Topic, TopicName, TopicType


class TopicManager:
    def __init__(self, host: str = None, port: str = None):
        self.host = host
        self.port = port
        if self.host is None:
            self.host = os.environ.get("NATKIT_SERVER_ADDRESS", "localhost")
        if self.port is None:
            self.port = os.environ.get("NATKIT_SERVER_PORT", "29092")
        self.broker = "{}:{}".format(self.host, self.port)
        self.admin_client = AdminClient({"bootstrap.servers": self.broker})
        self.producer_conf = {
            "bootstrap.servers": self.broker,
            "queue.buffering.max.ms": 5,
        }

    def create_data_consumer_conf(self):
        return {
            "bootstrap.servers": self.broker,
            "group.id": str(random.randint(0, 2**64)),
            "session.timeout.ms": 6000,
            "auto.offset.reset": "latest",
            "enable.auto.offset.store": True,
            "fetch.wait.max.ms": 5,
        }

    def create_meta_consumer_conf(self):
        return {
            "bootstrap.servers": self.broker,
            "group.id": str(random.randint(0, 2**64)),
            "session.timeout.ms": 6000,
            "auto.offset.reset": "earliest",
            "enable.auto.offset.store": True,
            "fetch.wait.max.ms": 5,
        }

    def get_topics(
        self, predicate=lambda topic: topic.type != TopicType.UNKNOWN
    ) -> [TopicName]:
        return_topics: [TopicName] = []
        cluster_metadata = self.admin_client.list_topics(timeout=10)
        topics = cluster_metadata.topics
        for t in topics.values():
            potential_topic = TopicName.parse_from_topic_string(str(t))
            if predicate(potential_topic):
                return_topics.append(potential_topic)
        return return_topics

    def build_stream(self, meta: Meta, stream_id: str = None) -> Stream:
        if stream_id is None:
            set_of_ids = set([topic.id for topic in self.get_topics()])
            topic_id = 0
            while True:
                topic_id = random.randint(0, 2**64)
                if topic_id not in set_of_ids:
                    stream_id = topic_id
                    break

        meta_topic_name = TopicName(stream_id, TopicType.META)
        data_topic_name = TopicName(stream_id, TopicType.DATA)
        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
            meta_topic_name.topic_string
        )
        data_topic_partitions = self.get_all_topic_partitions_for_topic(
            data_topic_name.topic_string
        )
        meta_topic = Topic(
            meta_topic_name,
            meta_topic_partitions,
            self.create_meta_consumer_conf(),
            self.producer_conf,
        )
        data_topic = Topic(
            data_topic_name,
            data_topic_partitions,
            self.create_data_consumer_conf(),
            self.producer_conf,
        )
        return Stream(meta, meta_topic, data_topic)

    def get_all_topic_partitions_for_topic(self, topic: str):
        cluster_metadata = self.admin_client.list_topics(timeout=10)
        topics = cluster_metadata.topics
        partitions = []
        for t in topics.values():
            if str(t) == topic:
                partitions = [
                    TopicPartition(topic, p.id, offset=0) for p in t.partitions.values()
                ]
                break

        return partitions

    def get_topic_partition_for_topic(self, topic: str):
        partitions = self.get_all_topic_partitions_for_topic(topic)
        if partitions is None or len(partitions) == 0:
            return None
        elif len(partitions) == 1:
            return next(iter(partitions))
        else:
            print(
                'Warning: Topic "{}" has multiple partitions, using the first one found'
            )
            return next(iter(partitions))

    def read_topic(self, stream_id: int) -> Topic:
        meta_topic_name = TopicName(stream_id, TopicType.META)
        data_topic_name = TopicName(stream_id, TopicType.DATA)
        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
            meta_topic_name.topic_string
        )
        data_topic_partitions = self.get_all_topic_partitions_for_topic(
            data_topic_name.topic_string
        )
        if meta_topic_partitions is None:
            print("Warning: No partitions found for topic meta")
            return None
        if data_topic_partitions is None:
            print("Warning: No partitions found for topic data")
            return None

        meta_topic = Topic(
            meta_topic_name,
            meta_topic_partitions,
            self.create_meta_consumer_conf(),
            self.producer_conf,
        )
        data_topic = Topic(
            data_topic_name,
            data_topic_partitions,
            self.create_data_consumer_conf(),
            self.producer_conf,
        )
        return (meta_topic, data_topic)

    def read_all_topics(self):
        meta_topics = self.get_topics(lambda topic: topic.type == TopicType.META)
        topics = []
        for topic in meta_topics:
            topic_pair = self.read_topic(topic.id)
            if topic_pair is not None:
                topics.append(topic_pair)
        return topics

    def _create_stream(self, meta_topic: Topic, data_topic: Topic):
        return Stream(None, meta_topic, data_topic)

    def find_stream(self, stream_id: int) -> Stream:
        meta_topic_name = TopicName(stream_id, TopicType.META)
        data_topic_name = TopicName(stream_id, TopicType.DATA)
        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
            meta_topic_name.topic_string
        )
        data_topic_partitions = self.get_all_topic_partitions_for_topic(
            data_topic_name.topic_string
        )
        if meta_topic_partitions is None:
            print("Warning: No partitions found for topic meta")
            return None
        if data_topic_partitions is None:
            print("Warning: No partitions found for topic data")
            return None

        meta_topic = Topic(
            meta_topic_name,
            meta_topic_partitions,
            self.create_meat_consumer_conf(),
            self.producer_conf,
        )
        data_topic = Topic(
            data_topic_name,
            data_topic_partitions,
            self.create_data_consumer_conf(),
            self.producer_conf,
        )
        return self._create_stream(meta_topic, data_topic)

    def find_all_streams(self) -> [Stream]:
        meta_topic_names = self.get_topics(lambda topic: topic.type == TopicType.META)
        topic_name_pairs = [
            (meta_topic_name, TopicName(meta_topic_name.id, TopicType.DATA))
            for meta_topic_name in meta_topic_names
        ]
        topic_name_pair_partitions = [
            (
                self.get_all_topic_partitions_for_topic(meta.topic_string),
                self.get_all_topic_partitions_for_topic(data.topic_string),
            )
            for meta, data in topic_name_pairs
        ]
        topic_pairs = [
            (
                Topic(
                    topic_name_pair[0],
                    partition_pair[0],
                    self.create_meta_consumer_conf(),
                    self.producer_conf,
                ),
                Topic(
                    topic_name_pair[1],
                    partition_pair[1],
                    self.create_data_consumer_conf(),
                    self.producer_conf,
                ),
            )
            for topic_name_pair, partition_pair in zip(
                topic_name_pairs, topic_name_pair_partitions
            )
        ]

        return [
            self._create_stream(meta_topic, data_topic)
            for meta_topic, data_topic in topic_pairs
        ]

    def delete_stream(self, stream) -> NoReturn:
        meta_topic_name = stream.meta_topic.topic_name.topic_string
        data_topic_name = stream.data_topic.topic_name.topic_string
        if meta_topic_name is not None:
            self.admin_client.delete_topics([meta_topic_name])

        if data_topic_name is not None:
            self.admin_client.delete_topics([data_topic_name])
