from typing import Generic, NoReturn, TypeVar


T = TypeVar("T")


class Stream(Generic[T]):
    def open(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def read(self) -> T:
        assert 0, "Abstract function not implemented!"

    def write(self, data: T) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def close(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"
