from __future__ import annotations
from typing import Generic, NoReturn, TypeVar


T = TypeVar("T")


class Result(Generic[T]):
    def __init__(self, value: T, success: bool, msg: str = None) -> NoReturn:
        self.value: T = value
        self.message: str = msg
        self.success: bool = success

    @staticmethod
    def success(value) -> Result:
        return Result(value, True)

    @staticmethod
    def failure(msg: str) -> Result:
        return Result(None, False, msg)
