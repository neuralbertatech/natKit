from typing import NoReturn


class Stream:
    def start(self) -> NoReturn:
        pass

    def read(self) -> str:
        pass

    def write(self, data: str) -> NoReturn:
        pass

    def close(self) -> NoReturn:
        pass
