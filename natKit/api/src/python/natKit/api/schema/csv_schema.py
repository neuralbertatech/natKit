from __future__ import annotations

from natKit.api import CsvStream
from natKit.api import Stream
from natKit.codegen.api import schema_pb2

from typing import NoReturn


class CsvSchema:
    def __init__(self, name: str, number_of_channels: int) -> NoReturn:
        self.name = name
        self.number_of_channels = number_of_channels

        self.stream_schema = self.build_schema_proto_message()

    @staticmethod
    def create_from_proto_schema(stream_schema: schema_pb2.StreamSchema) -> CsvSchema:
        return CsvSchema(stream_schema.name, stream_schema.number_of_channels)

    def __str__(self):
        return "CsvSchema: [name: {}, number_of_channels: {}]".format(
            self.name, self.number_of_channels
        )

    def serialize(self) -> bytes:
        return self.stream_schema.SerializeToString()

    def build_stream(self) -> Stream:
        return CsvStream(self.number_of_channels)

    def build_schema_proto_message(self) -> schema_pb2.StreamSchema:
        stream_schema = schema_pb2.StreamSchema()
        stream_schema.name = self.name
        stream_schema.channels = self.number_of_channels
        stream_schema.type = schema_pb2.SchemaType.CSV

        return stream_schema
