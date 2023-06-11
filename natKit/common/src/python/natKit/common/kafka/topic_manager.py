import concurrent
import logging
import os
import random
import time

from confluent_kafka import Consumer
from confluent_kafka import KafkaException
from confluent_kafka import Producer
from confluent_kafka import TopicPartition
from confluent_kafka.admin import AdminClient
from confluent_kafka.admin import NewTopic
from confluent_kafka.schema_registry import SchemaRegistryClient

from natKit.api import Deserializer
from natKit.api import EncoderRegistry
from natKit.api import Encoder
from natKit.api import Meta
from natKit.api import Schema
from natKit.api import SchemaRegistry
from natKit.api import Serializer
from natKit.api.schemas import MetaSchema
from .messenger import Messenger
from natKit.common.kafka import Stream
from natKit.common.kafka import StreamHelper
from natKit.common.kafka import Topic
from natKit.common.kafka import TopicConnection
from natKit.common.kafka import TopicMetadata
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType
from natKit.common.util import global_variables

from time import sleep

from typing import NoReturn


random.seed(random.seed(time.time()))


def read_schema(path):
    with open(path, "r") as f:
        return f.read()


class KafkaManager:
    def __init__(self, host: str, port: str, broker: str, admin_client: AdminClient):
        self.host = host
        self.port = port
        self.broker = broker
        self.admin_client = admin_client
        self.producer_conf = {
            "bootstrap.servers": self.broker,
            "queue.buffering.max.ms": 5,
        }

        # schemas = [
        #        Schema("MetaSchema", Encoding.JSON, MetaSchema.toDict, MetaSchema.createFromDict, read_schema(global_variables.lookup("JSON_SCHEMA_PATH") + "MetaSchema.json")),
        #    ]
        self.encoder_registry = EncoderRegistry.create()
        self.schema_registry = SchemaRegistry.create()

    @staticmethod
    def create(host: str = None, port: str = None):
        if host is None:
            host = os.environ.get("NATKIT_SERVER_ADDRESS", "localhost")
        if port is None:
            port = os.environ.get("NATKIT_SERVER_PORT", "29092")

        broker = "{}:{}".format(host, port)
        return KafkaManager(
            host, port, broker, AdminClient({"bootstrap.servers": broker})
        )

    def query_topic(self, topic_name: str) -> TopicConnection:
        pass

    def query_topic_names(self) -> []:
        cluster_metadata = self.admin_client.list_topics(timeout=3)
        topic_metadata = []
        topic_keys = []
        for name, partitions in cluster_metadata.topics.items():
            if name != "__consumer_offsets" and name != "_schemas":
                topic_metadata.append(TopicMetadata(name, partitions, None))
                topic_keys.append(name)

        return topic_keys

    def get_topic_connection(self, topic_string: str) -> TopicConnection:
        return self._build_topic_connection(topic_string)

    def create_messenger(self, topic_string: str):
        topic_name = TopicName.parse_from_topic_string(topic_string)
        encoder = self.encoder_registry.lookup(topic_name.encoder_name)
        schema = self.schema_registry.lookup(topic_name.schema_name)
        # schema_regsitry_client = SchemaRegistryClient({"url": "http://SOME_URL:38081"})
        # serializer = Serializer(schema.encoding, schema.source, schema_regsitry_client, schema.serializer)
        # deserializer = Deserializer(schema.encoding, schema.source, schema.deserializer)
        # return Messenger(topic_name, self._create_data_consumer_conf(), self.producer_conf, serializer, deserializer)
        return Messenger(
            topic_name,
            self._create_data_consumer_conf(),
            self.producer_conf,
            encoder,
            schema,
        )

    def create_topic(self, topic_string: str):
        new_topic = NewTopic(topic_string, num_partitions=3, replication_factor=1)
        futures = self.admin_client.create_topics([new_topic])
        while futures[topic_string].running():
            sleep(0.001)
        print(futures[topic_string].exception())

    def _build_topic_connection(self, topic_string: str) -> TopicConnection:
        topic_name = TopicName.parse_from_topic_string(topic_string)
        consumer_conf = self._create_data_consumer_conf()
        consumer = Consumer(consumer_conf)
        producer = Producer(self.producer_conf)
        # return TopicConnection(topic_name, consumer, producer, self.registry)
        return TopicConnection(topic_name, consumer, producer, print)

    def _create_data_consumer_conf(self):
        return {
            "bootstrap.servers": self.broker,
            "group.id": str(random.randint(0, 2**64)),
            "session.timeout.ms": 6000,
            "auto.offset.reset": "earliest",
            "enable.auto.offset.store": False,
            # "fetch.wait.max.ms": 5,
        }

    def _create_stream(self, meta_topic_string: str, data_topic_string: str):
        return Stream(
            meta_messenger=self.create_messenger(meta_topic_string),
            data_messenger=self.create_messenger(data_topic_string),
        )

    def find_streams(self):
        topic_string_pairs = StreamHelper.find_topic_stream_pairs(
            self.query_topic_names()
        )
        return [
            self._create_stream(topic_string_pair["meta"], topic_string_pair["data"])
            for topic_string_pair in topic_string_pairs
        ]

    def delete_all_topics(self):
        self.admin_client.delete_topics(self.query_topic_names())

    def delete_topic(self, topic_string):
        self.admin_client.delete_topics([topic_string])

    def create_new_stream(self, meta_topic_string, data_topic_string):
        self.create_topic(meta_topic_string)
        self.create_topic(data_topic_string)
        return self._create_stream(meta_topic_string, data_topic_string)

    def create_stream(
        self,
        name: str,
        data_encoder: Encoder,
        data_schema: Schema,
        meta_encoder: Encoder,
        meta_schema: Schema,
    ):
        random_id = random.randint(0, 2**64)
        data_topic_name = TopicName(
            id=random_id,
            type=TopicType.DATA,
            encoder_name=data_encoder.get_name(),
            schema_name=data_schema.get_name(),
        )
        meta_topic_name = TopicName(
            id=random_id,
            type=TopicType.META,
            encoder_name=meta_encoder.get_name(),
            schema_name=meta_schema.get_name(),
        )
        self.create_topic(data_topic_name.topic_string)
        self.create_topic(meta_topic_name.topic_string)
        return self._create_stream(
            meta_topic_name.topic_string, data_topic_name.topic_string
        )


# class TopicManager:
#    def __init__(self, host: str = None, port: str = None):
#        self.host = host
#        self.port = port
#        if self.host is None:
#            self.host = os.environ.get("NATKIT_SERVER_ADDRESS", "localhost")
#        if self.port is None:
#            self.port = os.environ.get("NATKIT_SERVER_PORT", "9092")
#        self.broker = "{}:{}".format(self.host, self.port)
#        self.admin_client = AdminClient({"bootstrap.servers": self.broker})
#        self.producer_conf = {
#            "bootstrap.servers": self.broker,
#            "queue.buffering.max.ms": 5,
#        }
#
#    def create_data_consumer_conf(self):
#        return {
#            "bootstrap.servers": self.broker,
#            "group.id": str(random.randint(0, 2**64)),
#            "session.timeout.ms": 6000,
#            "auto.offset.reset": "latest",
#            "enable.auto.offset.store": True,
#            "fetch.wait.max.ms": 5,
#        }
#
#    def create_meta_consumer_conf(self):
#        return {
#            "bootstrap.servers": self.broker,
#            "group.id": str(random.randint(0, 2**64)),
#            "session.timeout.ms": 6000,
#            "auto.offset.reset": "earliest",
#            "enable.auto.offset.store": True,
#            "fetch.wait.max.ms": 5,
#        }
#
#    def get_topics(
#        self, predicate=lambda topic: topic.type != TopicType.UNKNOWN
#    ) -> [TopicName]:
#        return_topics: [TopicName] = []
#        cluster_metadata = self.admin_client.list_topics(timeout=10)
#        topics = cluster_metadata.topics
#        for t in topics.values():
#            potential_topic = TopicName.parse_from_topic_string(str(t))
#            if predicate(potential_topic):
#                return_topics.append(potential_topic)
#        return return_topics
#
#    def build_stream(self, meta: Meta, stream_id: str = None) -> Stream:
#        if stream_id is None:
#            set_of_ids = set([topic.id for topic in self.get_topics()])
#            topic_id = 0
#            while True:
#                topic_id = random.randint(0, 2**64)
#                if topic_id not in set_of_ids:
#                    stream_id = topic_id
#                    break
#
#        meta_topic_name = TopicName(stream_id, TopicType.META)
#        data_topic_name = TopicName(stream_id, TopicType.DATA)
#        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
#            meta_topic_name.topic_string
#        )
#        data_topic_partitions = self.get_all_topic_partitions_for_topic(
#            data_topic_name.topic_string
#        )
#        meta_topic = Topic(
#            meta_topic_name,
#            meta_topic_partitions,
#            self.create_meta_consumer_conf(),
#            self.producer_conf,
#        )
#        data_topic = Topic(
#            data_topic_name,
#            data_topic_partitions,
#            self.create_data_consumer_conf(),
#            self.producer_conf,
#        )
#        return Stream(meta, meta_topic, data_topic)
#
#    def get_all_topic_partitions_for_topic(self, topic: str):
#        cluster_metadata = self.admin_client.list_topics(timeout=10)
#        topics = cluster_metadata.topics
#        partitions = []
#        for t in topics.values():
#            if str(t) == topic:
#                partitions = [
#                    TopicPartition(topic, p.id, offset=0) for p in t.partitions.values()
#                ]
#                break
#
#        return partitions
#
#    def get_topic_partition_for_topic(self, topic: str):
#        partitions = self.get_all_topic_partitions_for_topic(topic)
#        if partitions is None or len(partitions) == 0:
#            return None
#        elif len(partitions) == 1:
#            return next(iter(partitions))
#        else:
#            print(
#                'Warning: Topic "{}" has multiple partitions, using the first one found'
#            )
#            return next(iter(partitions))
#
#    def read_topic(self, stream_id: int) -> Topic:
#        meta_topic_name = TopicName(stream_id, TopicType.META)
#        data_topic_name = TopicName(stream_id, TopicType.DATA)
#        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
#            meta_topic_name.topic_string
#        )
#        data_topic_partitions = self.get_all_topic_partitions_for_topic(
#            data_topic_name.topic_string
#        )
#        if meta_topic_partitions is None:
#            print("Warning: No partitions found for topic meta")
#            return None
#        if data_topic_partitions is None:
#            print("Warning: No partitions found for topic data")
#            return None
#
#        meta_topic = Topic(
#            meta_topic_name,
#            meta_topic_partitions,
#            self.create_meta_consumer_conf(),
#            self.producer_conf,
#        )
#        data_topic = Topic(
#            data_topic_name,
#            data_topic_partitions,
#            self.create_data_consumer_conf(),
#            self.producer_conf,
#        )
#        return (meta_topic, data_topic)
#
#    def read_all_topics(self):
#        meta_topics = self.get_topics(lambda topic: topic.type == TopicType.META)
#        topics = []
#        for topic in meta_topics:
#            topic_pair = self.read_topic(topic.id)
#            if topic_pair is not None:
#                topics.append(topic_pair)
#        return topics
#
#    def _create_stream(self, meta_topic: Topic, data_topic: Topic):
#        return Stream(None, meta_topic, data_topic)
#
#    def find_stream(self, stream_id: int) -> Stream:
#        meta_topic_name = TopicName(stream_id, TopicType.META)
#        data_topic_name = TopicName(stream_id, TopicType.DATA)
#        meta_topic_partitions = self.get_all_topic_partitions_for_topic(
#            meta_topic_name.topic_string
#        )
#        data_topic_partitions = self.get_all_topic_partitions_for_topic(
#            data_topic_name.topic_string
#        )
#        if meta_topic_partitions is None:
#            print("Warning: No partitions found for topic meta")
#            return None
#        if data_topic_partitions is None:
#            print("Warning: No partitions found for topic data")
#            return None
#
#        meta_topic = Topic(
#            meta_topic_name,
#            meta_topic_partitions,
#            self.create_meat_consumer_conf(),
#            self.producer_conf,
#        )
#        data_topic = Topic(
#            data_topic_name,
#            data_topic_partitions,
#            self.create_data_consumer_conf(),
#            self.producer_conf,
#        )
#        return self._create_stream(meta_topic, data_topic)
#
#    def find_all_streams(self) -> [Stream]:
#        meta_topic_names = self.get_topics(lambda topic: topic.type == TopicType.META)
#        topic_name_pairs = [
#            (meta_topic_name, TopicName(meta_topic_name.id, TopicType.DATA))
#            for meta_topic_name in meta_topic_names
#        ]
#        topic_name_pair_partitions = [
#            (
#                self.get_all_topic_partitions_for_topic(meta.topic_string),
#                self.get_all_topic_partitions_for_topic(data.topic_string),
#            )
#            for meta, data in topic_name_pairs
#        ]
#        topic_pairs = [
#            (
#                Topic(
#                    topic_name_pair[0],
#                    partition_pair[0],
#                    self.create_meta_consumer_conf(),
#                    self.producer_conf,
#                ),
#                Topic(
#                    topic_name_pair[1],
#                    partition_pair[1],
#                    self.create_data_consumer_conf(),
#                    self.producer_conf,
#                ),
#            )
#            for topic_name_pair, partition_pair in zip(
#                topic_name_pairs, topic_name_pair_partitions
#            )
#        ]
#
#        return [
#            self._create_stream(meta_topic, data_topic)
#            for meta_topic, data_topic in topic_pairs
#        ]
#
#    def delete_stream(self, stream) -> NoReturn:
#        meta_topic_name = stream.meta_topic.topic_name.topic_string
#        data_topic_name = stream.data_topic.topic_name.topic_string
#        if meta_topic_name is not None:
#            self.admin_client.delete_topics([meta_topic_name])
#
#        if data_topic_name is not None:
#            self.admin_client.delete_topics([data_topic_name])
