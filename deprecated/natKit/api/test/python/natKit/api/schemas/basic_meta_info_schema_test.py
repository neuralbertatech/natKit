#!/usr/bin/env python3

import unittest

from natKit.api import CsvEncoder
from natKit.api import Encoder
from natKit.api import JsonEncoder
from natKit.api import BasicMetaInfoSchema

from numpy.testing import assert_array_equal

from typing import NoReturn


class BasicMetaInfoSchemaTest(unittest.TestCase):
    def test_basic_meta_info_schema(self) -> NoReturn:
        encoder = CsvEncoder()
        schema = BasicMetaInfoSchema("MyName")
        self.assert_schema_can_be_encoded_and_decoded(schema, encoder)

    def test_basic_meta_info_schema_with_comma(self) -> NoReturn:
        encoder = CsvEncoder()
        schema = BasicMetaInfoSchema("My,Name")
        self.assert_schema_can_be_encoded_and_decoded(schema, encoder)

    def test_with_json_encoder(self) -> NoReturn:
        encoder = JsonEncoder()
        schema = BasicMetaInfoSchema("Hi there")
        self.assert_schema_can_be_encoded_and_decoded(schema, encoder)

    def assert_schema_can_be_encoded_and_decoded(
        self, schema: BasicMetaInfoSchema, encoder: Encoder
    ) -> NoReturn:
        serialized_message = schema.serialize(encoder)
        deserialized_message = BasicMetaInfoSchema.deserialize(
            encoder, serialized_message
        )
        self.assertTrue(isinstance(serialized_message, bytes))
        self.assertEqual(schema.stream_name, deserialized_message.stream_name)


if __name__ == "__main__":
    unittest.main()
