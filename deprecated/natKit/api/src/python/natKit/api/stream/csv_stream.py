from __future__ import annotations

from natKit.api.stream import Stream
from natKit.codegen.api import schema_pb2


class CsvStream(Stream):
    def __init__(self, number_of_channels: int):
        self.number_of_channels = number_of_channels
        self.csv_stream = schema_pb2.CsvStream()

    @staticmethod
    def create_from_proto_message(self, number_of_channels: int, message) -> CsvStream:
        data = [
            int(channel) for channel in message.data.split(",")[:number_of_channels]
        ]
        return CsvStream(number_of_channels, data)

    def serialize(self, data: str) -> bytes:
        self.csv_stream.data = data
        return self.csv_stream.SerializeToString()
