#!/usr/bin/env python3

from __future__ import annotations

from .encoder import Encoder
from .csv_encoder import CsvEncoder
from .json_encoder import JsonEncoder

from typing import NoReturn
from typing import Optional


class EncoderRegistry:
    def __init__(self) -> NoReturn:
        self.registered_encoders = {}

    def register(
        self, encoder: Encoder, encoder_name: Optional[str] = None
    ) -> NoReturn:
        if encoder_name is None:
            encoder_name = encoder.get_name()
        self.registered_encoders[encoder_name] = encoder

    def lookup(self, encoder_name: str) -> Optional[Encoder]:
        if encoder_name in self.registered_encoders:
            return self.registered_encoders[encoder_name]
        else:
            return None

    @staticmethod
    def register_defaults(registry: EncoderRegistry) -> EncoderRegistry:
        registry.register(CsvEncoder())
        registry.register(JsonEncoder())
        return registry

    @staticmethod
    def create() -> EncoderRegistry:
        registry = EncoderRegistry()
        return EncoderRegistry.register_defaults(registry)
