from typing import NoReturn
from natKit.common.stream import Stream


class StdStream(Stream[str]):
    def __init__(self) -> NoReturn:
        pass

    def open(self) -> NoReturn:
        pass

    def read(self) -> str:
        return input()

    def write(self, data: str) -> NoReturn:
        print(data)

    def close(self) -> NoReturn:
        pass
