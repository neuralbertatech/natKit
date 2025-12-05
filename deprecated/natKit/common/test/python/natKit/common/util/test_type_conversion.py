from src.utility.type_conversion import string_to_float
from typing import NoReturn

import unittest


class TestTypeConversion(unittest.TestCase):
    def test_string_to_float_valid(self) -> NoReturn:
        self.assertEqual(string_to_float("1"), 1.0)
        self.assertEqual(string_to_float("2.123"), 2.123)
        self.assertEqual(string_to_float("1231213.123123"), 1231213.123123)

    def test_invalid_string_to_float(self) -> NoReturn:
        self.assertEqual(string_to_float(""), 0.0)
        self.assertEqual(string_to_float(None), 0.0)


if __name__ == "__main__":
    unittest.main()
