from __future__ import annotations

from natKit.codegen.api import schema_pb2

from typing import NoReturn


class Meta:
    def __init__(self, name: str, number_of_channels: int) -> NoReturn:
        self.name = name
        self.number_of_channels = number_of_channels

        self.message = schema_pb2.Meta()
        self.message.name = self.name
        self.message.numberOfChannels = self.number_of_channels

    @staticmethod
    def create_from_proto_message(meta_message: schema_pb2.Meta) -> Meta:
        return Meta(meta_message.name, meta_message.number_of_channels)

    @staticmethod
    def create_from_binary(blob: bytes) -> Meta:
        meta_message = schema_pb2.Meta()
        meta_message.ParseFromString(blob)
        return Meta(meta_message.name, meta_message.numberOfChannels)

    def __str__(self) -> str:
        return "Meta: [name: {}, number_of_channels: {}]".format(
            self.name, self.number_of_channels
        )

    def serialize(self) -> bytes:
        return self.message.SerializeToString()
