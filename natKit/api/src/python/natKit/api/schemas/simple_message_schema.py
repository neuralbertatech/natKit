#!/usr/bin/env python3

from natKit.api import CsvEncoder
from natKit.api import Encoder
from .schema import Schema

from typing import NoReturn
from typing import Optional


class SimpleMessageSchema(Schema):
    def __init__(self, message: str) -> NoReturn:
        self.message = message

    def __str__(self) -> str:
        return "{}: Message={}".format(self.get_name(), self.message)

    @staticmethod
    def get_name() -> str:
        return "SimpleMessageSchema"

    def serialize(self, encoder: Optional[Encoder] = None) -> bytes:
        if isinstance(encoder, CsvEncoder) or encoder is CsvEncoder or encoder is None:
            return CsvEncoder.encode([self.message])
        else:
            assert 0, "{} does not support {} encoding".format(SimpleMessageSchema.get_name(), encoder.get_name())

    def deserialize(encoder: Encoder, msg: bytes) -> Schema:
        if isinstance(encoder, CsvEncoder) or encoder is CsvEncoder:
            return SimpleMessageSchema(",".join(encoder.decode(msg)))
        else:
            assert 0, "{} does not support {} encoding".format(SimpleMessageSchema.get_name(), encoder.get_name())
