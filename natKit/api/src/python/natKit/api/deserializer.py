from natKit.api import Encoding

from confluent_kafka.serialization import SerializationContext
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.serialization import MessageField
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.schema_registry.protobuf import ProtobufDeserializer


class Deserializer:
    def __init__(self, encoding: Encoding, schema: str, dict_to_obj):
        assert encoding != Encoding.UNKNOWN, "Invalid encodings for the serializer"
        self.encoding = encoding
        self.schema = schema
        self.dict_to_obj = dict_to_obj

        if encoding == Encoding.AVRO:
            assert 0, "TODO"
        elif encoding == Encoding.JSON:
            self.deserializer = JSONDeserializer(schema, dict_to_obj)
        elif encoding == Encoding.PROTOBUF:
            assert 0, "TODO"
        elif encoding == Encoding.RAW:
            assert 0, "TODO"
        else:
            assert 0, "Error, found unknown encoding type {}".format(encoding)

    def deserialize(self, topic, message):
        return self.deserializer(message, SerializationContext(topic, MessageField.VALUE))
