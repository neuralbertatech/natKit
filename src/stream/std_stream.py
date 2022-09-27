from typing import NoReturn
from src.stream.stream import Stream


class StdStream(Stream):
    def __init__(self) -> NoReturn:
        pass

    def read(self) -> str:
        return input()

    def write(self, data: str) -> NoReturn:
        print(data)

    def close(self) -> NoReturn:
        pass
