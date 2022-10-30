from src.stream.stream import Stream
from src.utility.fifo import Fifo
from typing import NoReturn, TypeVar


T = TypeVar("T")


class DataStream(Stream[T]):
    def __init__(self, buffer: Fifo[T]) -> NoReturn:
        self.buffer = buffer

    def open(self) -> NoReturn:
        pass

    def read(self) -> T:
        return self.buffer.pop_one()

    def write(self, data: T) -> NoReturn:
        self.buffer.push(data)

    def close(self) -> NoReturn:
        pass
