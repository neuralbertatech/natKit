from src.transform.transform import Transform
from typing import NoReturn, TypeVar


T = TypeVar("T")


class FFT(Transform[T]):
    def __init__(self, window_size: int):
        assert 0, "TODO"
        pass

    def read(self) -> T:
        assert 0, "TODO"

    def write(self, data: T) -> NoReturn:
        assert 0, "TODO"

    def process(self) -> NoReturn:
        assert 0, "TODO"
