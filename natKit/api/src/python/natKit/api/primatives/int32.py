#!/usr/bin/env python3

from .Primative import Primative

from typing import NoReturn


class Int32(Primitive[int]):
    def __init__(integer: int) -> NoReturn:
        self.value = integer

    def get_value(self) -> int:
        return value

    def to_formatted_string(self) -> str:
        return "Int32: {}".format(self.value)

    def to_string(self) -> str:
        return "{}".format(value)
