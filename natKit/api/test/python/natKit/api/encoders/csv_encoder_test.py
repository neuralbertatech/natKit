#!/usr/bin/env python3

import unittest

from natKit.api import CsvEncoder

from numpy.testing import assert_array_equal

from typing import NoReturn


class CsvEncoderTest(unittest.TestCase):
    def test_array_of_strings(self) -> NoReturn:
        original_message = ["Hi", "There", "World"]
        encoded_message = CsvEncoder.encode(original_message)
        decoded_message = CsvEncoder.decode(encoded_message)
        self.assertTrue(isinstance(encoded_message, bytes))
        self.assertEqual(original_message, decoded_message)
        assert_array_equal(original_message, decoded_message)


if __name__ == "__main__":
    unittest.main()
