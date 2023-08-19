#!/usr/bin/env python3

from natKit.api import JsonEncoder
from natKit.api import Encoder
from .schema import Schema

from typing import List
from typing import NoReturn
from typing import Optional


class ImuDataSchema(Schema):
    def __init__(self, timestamp: str, data: List[float], calibration: int) -> NoReturn:
        self.timestamp = timestamp
        self.data = data
        self.calibration = calibration

    def __str__(self) -> str:
        return "{}: Timestamp={}, Data={}, Calibration={}".format(
            self.get_name(), self.timestamp, self.data, self.calibration
        )

    @staticmethod
    def get_name() -> str:
        return "ImuDataSchema"

    def serialize(self, encoder: Optional[Encoder] = None) -> bytes:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, JsonEncoder):
            return encoder.encode(
                {
                    timestamp: self.timestamp,
                    data: self.data,
                    calibration: self.calibration,
                }
            )
        else:
            assert 0, "{} does not support {} encoding".format(
                ImuDataSchema.get_name(), encoder.get_name()
            )

    def deserialize(encoder: Encoder, msg: bytes) -> Schema:
        if encoder is None:
            encoder = JsonEncoder()

        if isinstance(encoder, JsonEncoder):
            decoded_json = JsonEncoder.decode(msg)
            return ImuDataSchema(
                decoded_json["timestamp"],
                decoded_json["data"],
                decoded_json["calibration"],
            )
        else:
            assert 0, "{} does not support {} encoding".format(
                ImuDataSchema.get_name(), encoder.get_name()
            )
