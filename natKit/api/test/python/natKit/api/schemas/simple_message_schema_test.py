#!/usr/bin/env python3

import unittest

from natKit.api import CsvEncoder
from natKit.api import SimpleMessageSchema

from numpy.testing import assert_array_equal

from typing import NoReturn


class TestSimpleMessageSchema(unittest.TestCase):
    def test_simple_message_schema(self) -> NoReturn:
        encoder = CsvEncoder()
        original_message = SimpleMessageSchema("Hi there World")
        serialized_message = original_message.serialize(encoder)
        deserialized_message = SimpleMessageSchema.deserialize(encoder, serialized_message)
        self.assertTrue(isinstance(serialized_message, bytes))
        self.assertEqual(original_message.message, deserialized_message.message)

    def test_simple_message_schema_with_comma(self) -> NoReturn:
        encoder = CsvEncoder()
        original_message = SimpleMessageSchema("Hi there, World")
        serialized_message = original_message.serialize(encoder)
        deserialized_message = SimpleMessageSchema.deserialize(encoder, serialized_message)
        self.assertTrue(isinstance(serialized_message, bytes))
        self.assertEqual(original_message.message, deserialized_message.message)


if __name__ == "__main__":
    unittest.main()
