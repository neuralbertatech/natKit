from src.stream.stream import Stream
from typing import NoReturn


class FileStream(Stream[str]):
    def __init__(self, file_name: str, options: str = "r") -> NoReturn:
        self.file_name = file_name
        self.options = options

    def open(self) -> NoReturn:
        self.file = open(self.file_name, self.options)

    def read(self) -> str:
        return self.file.readline()

    def write(self, data: str) -> NoReturn:
        self.file.write(data)

    def close(self) -> NoReturn:
        self.file.close()
