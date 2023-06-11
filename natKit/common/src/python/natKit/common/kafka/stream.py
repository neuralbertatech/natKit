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
        topic_names = [TopicName.parse_from_topic_string(topic_string) for topic_string in topic_strings]
        sorted_topic_strings = sorted(topic_names, key=lambda x: x.id)

        topic_stream_pairs = []
        for i in range(len(sorted_topic_strings) - 1):
            t0 = sorted_topic_strings[i]
            t1 = sorted_topic_strings[i+1]
            if (t0.id == t1.id and
                t0.type != t1.type and
                (t0.type == TopicType.META or t0.type == TopicType.DATA) and
                (t1.type == TopicType.META or t1.type == TopicType.DATA)):
                if t0.type == TopicType.META:
                    topic_stream_pairs.append({"meta": t0.topic_string, "data": t1.topic_string})
                else:
                    topic_stream_pairs.append({"meta": t1.topic_string, "data": t0.topic_string})
        return topic_stream_pairs


class Stream(Thread):
    def __init__(self, data_messenger: Messenger, meta_messenger: Messenger):
        super().__init__()

        self.data_messenger = data_messenger
        self.meta_messenger = meta_messenger
        self.stream_id = TopicName.parse_from_topic_string(self.data_messenger.topic_str).id
        self.stream_ready = False
        self.stream_name = "UNKNOWN"
        self.data_schema = "UNKNOWN"
        self.start()

    def run(self):
        meta_message = self.meta_messenger.read()
        while meta_message is None:
            sleep(0.001)
            meta_message = self.meta_messenger.read()
        self.stream_name = meta_message.stream_name
        #self.data_schema = meta_message.data_schema
        self.stream_ready = True

    def get_name(self):
        while not self.stream_ready:
            sleep(0.001)
        return self.stream_name

    def get_id(self):
        return self.stream_id

    #def get_data_schema(self):
    #    while not self.stream_ready:
    #        sleep(0.001)
    #    return self.stream_schema

    def read_data(self):
        while not self.stream_ready:
            sleep(0.001)
        return self.data_messenger.read()

    def write_data(self, data_msg) -> NoReturn:
        self.data_messenger.write(data_msg)

    def write_meta(self, meta_msg):
        self.meta_messenger.write(meta_msg)

#class Stream:
#    def __init__(self, meta: Meta, meta_topic: Topic, data_topic: Topic):
#        self.meta = meta
#        self.data = None
#        self.meta_topic = meta_topic
#        self.data_topic = data_topic
#        self.id = meta_topic.topic_name.id
#
#        self._set_meta()
#        self._set_data()
#
#    def _set_meta(self):
#        if self.meta is None:
#            meta_attempt = self.get_last_meta()
#            if meta_attempt is not None:
#                self.meta = meta_attempt
#                self._set_data()
#                return True
#            else:
#                return False
#        else:
#            return True
#
#    def _set_data(self):
#        if self.data is not None:
#            return True
#        elif self.meta is None:
#            return False
#        else:
#            self.data = Data.create_from_meta(self.meta)
#            return True
#
#    def read_meta(self) -> Meta:
#        # Block until initalized
#        while not self.meta_topic.ready_to_read:
#            time.sleep(0.01)
#
#        data = self.meta_topic.pop()
#        if data is not None:
#            return Meta.create_from_binary(data)
#        return None
#
#    def get_last_meta(self) -> Meta:
#        # Block until initalized
#        while not self.meta_topic.ready_to_read:
#            time.sleep(0.01)
#
#        data = self.meta_topic.last_message
#        if data is not None:
#            try:
#                return Meta.create_from_binary(data.value())
#            except Exception as e:
#                print(e)
#                return None
#        return None
#
#    def read_data(self) -> Optional[DataMessage]:
#        # Block until initalized
#        while not self.data_topic.ready_to_read:
#            time.sleep(0.01)
#
#        value = self.data_topic.pop()
#        if value is not None:
#            return DataMessage(value)
#        return None
#
#    def write_meta(self) -> NoReturn:
#        # Block until initalized
#        while not self.data_topic.ready_to_read:
#            time.sleep(0.01)
#
#        self.meta_topic.write(self.meta.serialize())
#
#    def write_data(self, data: []) -> NoReturn:
#        # Block until initalized
#        while not self.data_topic.ready_to_read:
#            time.sleep(0.01)
#
#        self.data_topic.write(self.data.serialize(data))
#
#    def get_name(self) -> str:
#        last_meta = self.get_last_meta()
#        if last_meta is not None:
#            return last_meta.name
#        return ""
#
#    def get_id(self) -> int:
#        return self.meta_topic.topic_name.id
#
#    def __str__(self) -> str:
#        return "{}-{}".format(self.get_name(), self.get_id())
