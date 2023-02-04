from natKit.api import Meta
from natKit.common.kafka import TopicManager

from typing import NoReturn


class Trigger:
    def __init__(self, name: str, default_value: int = 0) -> NoReturn:
        self.name = name
        self.value = default_value
        self.meta = Meta(name=self.name, number_of_channels=1)
        self.topic_manager = TopicManager()
        self.stream = self.topic_manager.build_stream(self.meta)
        self.stream.write_meta()
        self.ref_count = 0

    def set_value(self, new_value: int) -> NoReturn:
        self.value = new_value

    def get_value(self) -> int:
        return self.value

    def get_id(self) -> int:
        return self.stream.get_id()

    def write(self) -> NoReturn:
        self.stream.write_data([self.value])
