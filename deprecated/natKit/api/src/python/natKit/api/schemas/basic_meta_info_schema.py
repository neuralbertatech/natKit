#!/usr/bin/env python3

from natKit.api import CsvEncoder
from natKit.api import Encoder
from natKit.api import JsonEncoder
from .schema import Schema

from typing import NoReturn
from typing import Optional


class BasicMetaInfoSchema(Schema):
    def __init__(self, stream_name: str) -> NoReturn:
        self.stream_name = stream_name

    def __str__(self) -> str:
        return "{}: stream_name={}".format(self.get_name(), self.stream_name)

    @staticmethod
    def get_name() -> str:
        return "BasicMetaInfoSchema"

    def serialize(self, encoder: Optional[Encoder] = None) -> bytes:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, JsonEncoder):
            return encoder.encode({"Stream Name": self.stream_name})
        elif isinstance(encoder, CsvEncoder):
            return CsvEncoder.encode([self.stream_name])
        else:
            assert 0, "{} does not support {} encoding".format(
                BasicMetaInfoSchema.get_name(), encoder.get_name()
            )

    def deserialize(encoder: Encoder, msg: bytes) -> Schema:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, JsonEncoder):
            decoded_json = encoder.decode(msg)
            return BasicMetaInfoSchema(stream_name=decoded_json["Stream Name"])
        elif isinstance(encoder, CsvEncoder):
            return BasicMetaInfoSchema(stream_name=",".join(encoder.decode(msg)))
        else:
            assert 0, "{} does not support {} encoding".format(
                BasicMetaInfoSchema.get_name(), encoder.get_name()
            )
