from natKit.api import Data
from natKit.api import Meta
from natKit.api import SchemaRegistry
from natKit.common.kafka import DataMessage
from natKit.common.kafka import Messenger
from natKit.common.kafka import Topic
from natKit.common.kafka import TopicConnection
from natKit.common.kafka import TopicName
from natKit.common.kafka import TopicType

from time import sleep

from threading import Thread

from typing import List
from typing import NoReturn
from typing import Optional


class StreamHelper:
    @staticmethod
    def find_topic_stream_pairs(topic_strings: List[str]) -> List[dict]:
        topic_names = [
            TopicName.parse_from_topic_string(topic_string)
            for topic_string in topic_strings
        ]
        sorted_topic_strings = sorted(topic_names, key=lambda x: x.id)

        topic_stream_pairs = []
        for i in range(len(sorted_topic_strings) - 1):
            t0 = sorted_topic_strings[i]
            t1 = sorted_topic_strings[i + 1]
            if (
                t0.id == t1.id
                and t0.type != t1.type
                and (t0.type == TopicType.META or t0.type == TopicType.DATA)
                and (t1.type == TopicType.META or t1.type == TopicType.DATA)
            ):
                if t0.type == TopicType.META:
                    topic_stream_pairs.append(
                        {"meta": t0.topic_string, "data": t1.topic_string}
                    )
                else:
                    topic_stream_pairs.append(
                        {"meta": t1.topic_string, "data": t0.topic_string}
                    )
        return topic_stream_pairs


class Stream(Thread):
    def __init__(self, data_messenger: Messenger, meta_messenger: Messenger):
        super().__init__()

        self.data_messenger = data_messenger
        self.meta_messenger = meta_messenger
        self.stream_id = TopicName.parse_from_topic_string(
            self.data_messenger.topic_str
        ).id
        self.stream_ready = False
        self.stream_name = "UNKNOWN"
        self.data_schema = "UNKNOWN"
        self.start()

    def run(self):
        meta_message = self.meta_messenger.read()
        retry_count = 0
        while meta_message is None and retry_count < 3000:
            sleep(0.001)
            meta_message = self.meta_messenger.read()
            retry_count += 1
        if meta_message is not None:
            self.stream_name = meta_message.stream_name
        else:
            # TODO: Add some sort of error message here
            pass
        self.stream_ready = True

    def close(self):
        self.data_messenger.close()
        self.meta_messenger.close()

    def get_name(self):
        while not self.stream_ready:
            sleep(0.001)
        return self.stream_name

    def get_id(self):
        return self.stream_id

    def read_data(self):
        while not self.stream_ready:
            sleep(0.001)
        return self.data_messenger.read()

    def write_data(self, data_msg) -> NoReturn:
        self.data_messenger.write(data_msg)

    def write_meta(self, meta_msg) -> NoReturn:
        self.meta_messenger.write(meta_msg)

    def get_data_topic_string(self) -> str:
        return self.data_messenger.topic_str

    def get_meta_topic_string(self) -> str:
        return self.meta_messenger.topic_str
