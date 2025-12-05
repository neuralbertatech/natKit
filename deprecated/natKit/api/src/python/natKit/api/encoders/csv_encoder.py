#!/usr/bin/env python3

from .encoder import Encoder

from typing import List
from typing import NoReturn
from typing import Optional


class CsvEncoder(Encoder[List[str]]):
    def __init__(self) -> NoReturn:
        pass

    @staticmethod
    def get_name() -> str:
        return "CsvEncoder"

    @staticmethod
    def encode(strings: List[str]) -> bytes:
        return ",".join(strings).encode("UTF-8")

    @staticmethod
    def decode(msg: Optional[bytes]) -> List[str]:
        if msg is None:
            return []
        else:
            return msg.decode("UTF-8").split(",")
