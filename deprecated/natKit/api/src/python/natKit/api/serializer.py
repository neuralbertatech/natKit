from natKit.api import Encoding

from confluent_kafka.serialization import SerializationContext
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.serialization import MessageField
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.schema_registry.json_schema import JSONSerializer
from confluent_kafka.schema_registry.protobuf import ProtobufSerializer


class Serializer:
    def __init__(self, encoding: Encoding, schema: str, schema_registry_client: SchemaRegistryClient, obj_to_dict):
        assert encoding != Encoding.UNKNOWN, "Invalid encodings for the serializer"
        self.encoding = encoding
        self.schema = schema
        self.schema_registry_client = schema_registry_client
        self.obj_to_dict = obj_to_dict

        if encoding == Encoding.AVRO:
            assert 0, "TODO"
        elif encoding == Encoding.JSON:
            self.serializer = JSONSerializer(schema, schema_registry_client, obj_to_dict)
        elif encoding == Encoding.PROTOBUF:
            assert 0, "TODO"
        elif encoding == Encoding.RAW:
            assert 0, "TODO"
        else:
            assert 0, "Error, found unknown encoding type {}".format(encoding)

    def serialize(self, topic, obj):
        print("Topic: {}\nObject: {}\nEncoding: {}\nSchema: {}".format(topic, obj, self.encoding, self.schema))
        return self.serializer(obj, SerializationContext(topic, MessageField.VALUE))
