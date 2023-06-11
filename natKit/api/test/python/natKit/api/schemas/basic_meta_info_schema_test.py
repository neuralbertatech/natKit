#!/usr/bin/env python3

import unittest

from natKit.api import CsvEncoder
from natKit.api import BasicMetaInfoSchema

from numpy.testing import assert_array_equal

from typing import NoReturn


class BasicMetaInfoSchemaTest(unittest.TestCase):
    def test_basic_meta_info_schema(self) -> NoReturn:
        encoder = CsvEncoder()
        original_message = BasicMetaInfoSchema("MyName")
        serialized_message = original_message.serialize(encoder)
        deserialized_message = BasicMetaInfoSchema.deserialize(
            encoder, serialized_message
        )
        self.assertTrue(isinstance(serialized_message, bytes))
        self.assertEqual(original_message.stream_name, deserialized_message.stream_name)

    def test_basic_meta_info_schema_with_comma(self) -> NoReturn:
        encoder = CsvEncoder()
        original_message = BasicMetaInfoSchema("My,Name")
        serialized_message = original_message.serialize(encoder)
        deserialized_message = BasicMetaInfoSchema.deserialize(
            encoder, serialized_message
        )
        self.assertTrue(isinstance(serialized_message, bytes))
        self.assertEqual(original_message.stream_name, deserialized_message.stream_name)


if __name__ == "__main__":
    unittest.main()
