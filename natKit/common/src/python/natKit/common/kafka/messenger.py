# from natKit.api import Deserializer
from natKit.api import Encoder
from natKit.api import Schema

# from natKit.api import Serializer
from natKit.common.kafka import TopicConnection
from natKit.common.kafka import TopicName
from natKit.common.util import Fifo

from typing import Generic
from typing import NoReturn
from typing import Optional
from typing import TypeVar


T = TypeVar("T")


# @BadCode
#     This class needs to instanciate the topic_connection itsself in order to set the callback
#     leading to tight coupling between Messenger and TopicConnection
class Messenger(Generic[T]):
    def __init__(
        self,
        topic_name: TopicName,
        consumer_config: dict,
        producer_config: dict,
        encoder: Encoder,
        schema: Schema,
    ) -> NoReturn:
        self.topic_str = topic_name.topic_string
        self.fifo = Fifo(4096)
        self.topic_connection = TopicConnection.create_from_config(
            topic_name,
            consumer_config,
            producer_config,
            lambda msg: self.fifo.push(msg),
        )
        self.encoder = encoder
        self.schema = schema

    def close(self) -> NoReturn:
        self.topic_connection.stop()

    def read(self) -> Optional[T]:
        read_message = self.fifo.pop_one()
        if read_message is None:
            return None
        else:
            message = self.schema.deserialize(self.encoder, read_message)
            return message

    def write(self, obj: T):
        self.topic_connection.write(obj.serialize(self.encoder))
