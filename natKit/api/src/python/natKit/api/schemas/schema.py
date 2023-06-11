#!/usr/bin/env python3

from __future__ import annotations

from natKit.api import Encoder

from typing import Generic
from typing import Optional


class Schema:
    @staticmethod
    def get_name() -> str:
        assert 0, "Abstract Method not Implemented!"

    def serialize(encoding: Optional[Encoder] = None) -> bytes:
        assert 0, "Abstract Method not Implemented!"

    @staticmethod
    def deserialize(encoding: Encoder, msg: bytes) -> Schema:
        assert 0, "Abstract Method not Implemented!"
