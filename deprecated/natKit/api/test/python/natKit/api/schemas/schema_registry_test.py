#!/usr/bin/env python3

import unittest

from natKit.api import SchemaRegistry

from typing import NoReturn


class SchemaRegistryTest(unittest.TestCase):
    def test_encoder_registry(self) -> NoReturn:
        registry = SchemaRegistry.create()
        self.assertIsNotNone(registry.lookup("SimpleMessageSchema"))


if __name__ == "__main__":
    unittest.main()
