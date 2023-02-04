from confluent_kafka import Message as ConfluentMessage
from confluent_kafka import KafkaError

from natKit.api import Data

from typing import List
from typing import NoReturn
from typing import Optional
from typing import Tuple
from typing import Union


class DataMessage:
    def __init__(self, confluent_message: ConfluentMessage):
        self.confluent_message = confluent_message

    def __len__(self) -> int:
        return len(self.confluent_message)

    def error(self) -> Optional[KafkaError]:
        return self.confluent_message.error()

    def headers(self) -> Optional[List[Tuple[str, bytes]]]:
        return self.confluent_message.bytes()

    def key(self) -> Optional[Union[str, bytes]]:
        return self.confluent_message.key()

    def latency(self) -> Optional[float]:
        return self.confluent_message.latency()

    def offset(self) -> Optional[int]:
        return self.confluent_message.offset()

    def partition(self) -> Optional[int]:
        return self.confluent_message.partition

    def set_headers(self, value: object) -> NoReturn:
        self.confluent_message.set_headers(value)

    def set_key(self, value: object) -> NoReturn:
        self.confluent_message.set_key(value)

    def set_value(self, value: object) -> NoReturn:
        self.confluent_message.set_value(value)

    def timestamp(self) -> Tuple[int, int]:
        return self.confluent_message.timestamp()

    def topic(self) -> Optional[str]:
        return self.confluent_message.topic()

    def value(self) -> Optional[Union[str, bytes]]:
        return self.confluent_message.value()

    def deserialize(self) -> Data:
        return Data.create_from_bytes(self.confluent_message.value())
