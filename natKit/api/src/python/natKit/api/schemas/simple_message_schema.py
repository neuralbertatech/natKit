#!/usr/bin/env python3

from natKit.api import CsvEncoder
from natKit.api import Encoder
from natKit.api import JsonEncoder
from .schema import Schema

from typing import NoReturn
from typing import Optional


class SimpleMessageSchema(Schema):
    def __init__(self, message: str) -> NoReturn:
        self.message = str(message)

    def __str__(self) -> str:
        return "{}: Message={}".format(self.get_name(), self.message)

    @staticmethod
    def get_name() -> str:
        return "SimpleMessageSchema"

    def serialize(self, encoder: Optional[Encoder] = None) -> bytes:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, CsvEncoder):
            return CsvEncoder.encode([self.message])
        elif isinstance(encoder, JsonEncoder):
            return JsonEncoder.encode({"message": self.message})
        else:
            assert 0, "{} does not support {} encoding".format(
                SimpleMessageSchema.get_name(), encoder.get_name()
            )

    def deserialize(encoder: Encoder, msg: bytes) -> Schema:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, CsvEncoder):
            return SimpleMessageSchema(",".join(encoder.decode(msg)))
        elif isinstance(encoder, JsonEncoder):
            print(encoder.decode(msg))
            return SimpleMessageSchema(encoder.decode(msg)["message"])
        else:
            assert 0, "{} does not support {} encoding".format(
                SimpleMessageSchema.get_name(), encoder.get_name()
            )
