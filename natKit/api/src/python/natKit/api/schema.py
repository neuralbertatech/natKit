from natKit.api import Encoding

from typing import Callable
from typing import NoReturn


class Schema:
    def __init__(self, name: str, encoding: Encoding, serializer: Callable, decerializer: Callable, source: str) -> NoReturn:
        assert encoding != Encoding.UNKNOWN, "Invalid encoding for Schema"
        self.name = name
        self.encoding = encoding
        self.serializer = serializer
        self.deserializer = decerializer
        self.source = source
