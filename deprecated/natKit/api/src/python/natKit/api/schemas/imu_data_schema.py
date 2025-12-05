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

    @staticmethod
    def csv_header() -> str:
        header = [
            "timestamp",
            "data0",
            "data1",
            "data2",
            "data3",
            "data4",
            "data5",
            "data6",
            "data7",
            "data8",
            "calibration",
        ]
        return ",".join(header)

    def to_csv(self) -> str:
        data = [0 for i in range(11)]
        data[0] = str(self.timestamp)
        for i, datum in enumerate(self.data):
            data[i + 1] = str(datum)
        data[10] = str(self.calibration)
        return ",".join(data)
