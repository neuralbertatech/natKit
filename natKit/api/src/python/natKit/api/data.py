from __future__ import annotations

from natKit.codegen.api import schema_pb2

from typing import List


class Data:
    def __init__(self, number_of_channels: int, data_message=schema_pb2.Data()):
        self.number_of_channels = number_of_channels
        self.data_message = data_message

    @staticmethod
    def create_from_meta(meta) -> Data:
        return Data(meta.number_of_channels)

    @staticmethod
    def create_from_bytes(message_in_bytes) -> Data:
        data_message = schema_pb2.Data()
        data_message.ParseFromString(message_in_bytes)
        return Data(len(data_message.data), data_message)

    def serialize(self, data: []) -> bytes:
        self.data_message.data[:] = data
        return self.data_message.SerializeToString()

    def get_data(self) -> List[int]:
        data = []
        for datum in self.data_message.data:
            data.append(datum)

        return data
