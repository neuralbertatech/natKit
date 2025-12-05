#!/usr/bin/env python3

from typing import Generic
from typing import TypeVar

T = TypeVar("T")

class Encoder(Generic[T]):
    @staticmethod
    def get_name() -> str:
        assert 0, "Abstract Method not Implemented!"

    @staticmethod
    def encode(T) -> bytes:
        assert 0, "Abstract Method not Implemented!"

    @staticmethod
    def decode(b: bytes) -> T:
        assert 0, "Abstract Method not Implemented!"
