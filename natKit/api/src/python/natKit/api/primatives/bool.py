#!/usr/bin/env python3

from .Primative import Primative

from typing import NoReturn


class Bool(Primitive[bool]):
    def __init__(value: bool) -> NoReturn:
        self.value = value

    def get_value(self) -> bool:
        return value

    def to_formatted_string(self) -> str:
        return "Bool: {}".format(self.value)

    def to_string(self) -> str:
        return "{}".format(value)
