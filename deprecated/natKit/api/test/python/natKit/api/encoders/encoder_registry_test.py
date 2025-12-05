#!/usr/bin/env python3

import unittest

from natKit.api import EncoderRegistry

from typing import NoReturn


class EncoderRegistryTest(unittest.TestCase):
    def test_encoder_registry(self) -> NoReturn:
        registry = EncoderRegistry.create()
        self.assertIsNotNone(registry.lookup("CsvEncoder"))


if __name__ == "__main__":
    unittest.main()
