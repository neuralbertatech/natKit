#!/usr/bin/env python3

from typing import Generic
from typing import TypeVar


T = TypeVar("T")


class Primative(Generic[T]):
    def get_value(self) -> T:
        assert 0, "Abstract Method not Implemented!"

    def to_formatted_string(self) -> str:
        assert 0, "Abstract Method not Implemented!"

    def to_string(self) -> str:
        assert 0, "Abstract Method not Implemented!"
