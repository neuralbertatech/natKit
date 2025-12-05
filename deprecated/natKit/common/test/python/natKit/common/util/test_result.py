from src.utility.result import Result
from typing import NoReturn

import unittest


class TestResult(unittest.TestCase):
    def test_success_int(self) -> NoReturn:
        result: Result[int] = Result.success(10)
        self.assertEqual(result.success, True)
        self.assertEqual(result.value, 10)

    def test_success_str(self) -> NoReturn:
        result: Result[str] = Result.success("hi")
        self.assertEqual(result.success, True)
        self.assertEqual(result.value, "hi")

    def test_failure_int(self) -> NoReturn:
        result: Result[int] = Result.failure("operation failed")
        self.assertEqual(result.success, False)
        self.assertEqual(result.message, "operation failed")

    def test_failure_str(self) -> NoReturn:
        result: Result[str] = Result.failure("operation failed")
        self.assertEqual(result.success, False)
        self.assertEqual(result.message, "operation failed")


if __name__ == "__main__":
    unittest.main()
