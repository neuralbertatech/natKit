import time

from natKit.api import Data
from natKit.api import Meta
from natKit.common.kafka import DataMessage
from natKit.common.kafka import Topic
from natKit.common.kafka import TopicType

from typing import NoReturn
from typing import Optional


class Stream:
    def __init__(self, meta: Meta, meta_topic: Topic, data_topic: Topic):
        self.meta = meta
        self.data = None
        self.meta_topic = meta_topic
        self.data_topic = data_topic
        self.id = meta_topic.topic_name.id

        self._set_meta()
        self._set_data()

    def _set_meta(self):
        if self.meta is None:
            meta_attempt = self.get_last_meta()
            if meta_attempt is not None:
                self.meta = meta_attempt
                self._set_data()
                return True
            else:
                return False
        else:
            return True

    def _set_data(self):
        if self.data is not None:
            return True
        elif self.meta is None:
            return False
        else:
            self.data = Data.create_from_meta(self.meta)
            return True

    def read_meta(self) -> Meta:
        # Block until initalized
        while not self.meta_topic.ready_to_read:
            time.sleep(0.01)

        data = self.meta_topic.pop()
        if data is not None:
            return Meta.create_from_binary(data)
        return None

    def get_last_meta(self) -> Meta:
        # Block until initalized
        while not self.meta_topic.ready_to_read:
            time.sleep(0.01)

        data = self.meta_topic.last_message
        if data is not None:
            try:
                return Meta.create_from_binary(data.value())
            except Exception as e:
                print(e)
                return None
        return None

    def read_data(self) -> Optional[DataMessage]:
        # Block until initalized
        while not self.data_topic.ready_to_read:
            time.sleep(0.01)

        value = self.data_topic.pop()
        if value is not None:
            return DataMessage(value)
        return None

    def write_meta(self) -> NoReturn:
        # Block until initalized
        while not self.data_topic.ready_to_read:
            time.sleep(0.01)

        self.meta_topic.write(self.meta.serialize())

    def write_data(self, data: []) -> NoReturn:
        # Block until initalized
        while not self.data_topic.ready_to_read:
            time.sleep(0.01)

        self.data_topic.write(self.data.serialize(data))

    def get_name(self) -> str:
        last_meta = self.get_last_meta()
        if last_meta is not None:
            return last_meta.name
        return ""

    def get_id(self) -> int:
        return self.meta_topic.topic_name.id

    def __str__(self) -> str:
        return "{}-{}".format(self.get_name(), self.get_id())
