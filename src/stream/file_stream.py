from typing import NoReturn
from src.stream.stream import Stream


class FileStream(Stream):
    def __init__(self, file_name: str, options: str = 'r') -> NoReturn:
        self.file = open(file_name, options)

    def read(self) -> str:
        return self.file.readline()

    def write(self, data: str) -> NoReturn:
        self.file.write(data)

    def close(self) -> NoReturn:
        self.file.close()
