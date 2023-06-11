#!/usr/bin/env python3

from natKit.api import CsvEncoder
from natKit.api import Encoder
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
        if isinstance(encoder, CsvEncoder) or encoder is CsvEncoder or encoder is None:
            return CsvEncoder.encode([self.stream_name])
        else:
            assert 0, "{} does not support {} encoding".format(BasicMetaInfoSchema.get_name(), encoder.get_name())

    def deserialize(encoder: Encoder, msg: bytes) -> Schema:
        if isinstance(encoder, CsvEncoder) or encoder is CsvEncoder:
            return BasicMetaInfoSchema(stream_name=",".join(encoder.decode(msg)))
        else:
            assert 0, "{} does not support {} encoding".format(BasicMetaInfoSchema.get_name(), encoder.get_name())
