#!/usr/bin/env python3

from .Primative import Primative

from typing import NoReturn


class Float32(Primitive[float]):
    def __init__(value: float) -> NoReturn:
        self.value = value

    def get_value(self) -> float:
        return value

    def to_formatted_string(self) -> str:
        return "Float32: {}".format(self.value)

    def to_string(self) -> str:
        return "{}".format(value)
