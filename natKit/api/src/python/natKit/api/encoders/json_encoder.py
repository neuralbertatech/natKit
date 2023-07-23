#!/usr/bin/env python3

import json

from .encoder import Encoder

from typing import Any
from typing import Dict
from typing import NoReturn
from typing import Optional


class JsonEncoder(Encoder[Dict[str, Any]]):
    def __init__(self) -> NoReturn:
        pass

    @staticmethod
    def get_name() -> str:
        return "JsonEncoder"

    @staticmethod
    def encode(dictionary: Dict[str, Any]) -> bytes:
        return json.dumps(dictionary).encode("UTF-8")

    @staticmethod
    def decode(msg: Optional[bytes]) -> Optional[Dict[str, Any]]:
        if msg is None:
            return None
        else:
            return json.loads(msg.decode("UTF-8"))
