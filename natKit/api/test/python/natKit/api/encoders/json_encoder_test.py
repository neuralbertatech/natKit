#!/usr/bin/env python3

import unittest

from natKit.api import JsonEncoder

from numpy.testing import assert_array_equal

from typing import Any
from typing import Dict
from typing import NoReturn


class JsonEncoderTest(unittest.TestCase):
    def test_dictionary_of_strings(self) -> NoReturn:
        message = {"Hello": "World", "Goodbye": "You"}
        self.assert_message_can_be_encoded_and_decoded(message)

    def test_dictionary_of_arrays(self) -> NoReturn:
        message = {"Hello": [1, 2, 3], "World": ["a", "b", "c"]}
        self.assert_message_can_be_encoded_and_decoded(message)

    def test_mixed_dictionary(self) -> NoReturn:
        message = {"Hello": "There", "World": ["a", "b", "c"]}
        self.assert_message_can_be_encoded_and_decoded(message)

    def assert_message_can_be_encoded_and_decoded(
        self, message: Dict[str, Any]
    ) -> NoReturn:
        encoded_message = JsonEncoder.encode(message)
        decoded_message = JsonEncoder.decode(encoded_message)
        self.assertTrue(isinstance(encoded_message, bytes))
        self.assertEqual(message, decoded_message)


if __name__ == "__main__":
    unittest.main()
