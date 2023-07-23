import random

from natKit.api import BasicMetaInfoSchema
from natKit.api import ImuDataSchema
from natKit.api import JsonEncoder
from natKit.api import SimpleMessageSchema
from natKit.common.kafka import KafkaManager

from typing import NoReturn


class Trigger:
    def __init__(self, name: str, default_value: int = 0) -> NoReturn:
        self.name = name
        self.value = default_value
        self.meta = BasicMetaInfoSchema(name)
        self.kafka_manager = KafkaManager.create()
        self.encoder = JsonEncoder()
        # TODO Redo this!
        random.seed()
        tmp_id = random.randint(0, 1000000)
        self.stream = self.kafka_manager.create_new_stream(
            "meta-{}-{}-{}".format(
                tmp_id, self.encoder.get_name(), BasicMetaInfoSchema.get_name()
            ),
            "data-{}-{}-{}".format(
                tmp_id, self.encoder.get_name(), SimpleMessageSchema.get_name()
            ),
        )
        # TODO use Messenger instead of raw stream
        self.stream.write_meta(self.meta)
        self.ref_count = 0

    def set_value(self, new_value: int) -> NoReturn:
        self.value = new_value

    def get_value(self) -> int:
        return self.value

    def get_id(self) -> int:
        return self.stream.get_id()

    def write(self) -> NoReturn:
        self.stream.write_data(SimpleMessageSchema(str(self.value)))
