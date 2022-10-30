from typing import NoReturn, TypeVar


T = TypeVar("T")


class Transform:
    def read(self) -> T:
        assert 0, "Abstract function not implemented!"

    def write(self, data: T) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def process(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"
