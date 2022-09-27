from src.utility.fifo import Fifo
from numpy.testing import assert_array_equal
from typing import NoReturn

import unittest


class TestFifo(unittest.TestCase):
    def setUp(self):
        self.buffer_size: int = 8
        self.fifo: Fifo = Fifo(self.buffer_size)

    def test_single_element_pop_automatic(self) -> NoReturn:
        self.fifo.push(20)

        data: [int] = self.fifo.pop()
        expected: [int] = [20]
        assert_array_equal(data, expected)

    def test_single_element_pop_manual(self) -> NoReturn:
        self.fifo.push(20)

        data: [int] = self.fifo.pop(1)
        expected: [int] = [20]
        assert_array_equal(data, expected)

    def test_multiple_elements_pop_automatic(self) -> NoReturn:
        for i in range(5):
            self.fifo.push(i)

        data: [int] = self.fifo.pop()
        expected: [int] = [0, 1, 2, 3, 4]
        assert_array_equal(data, expected)

    def test_filling_buffer_pop_all_automatic(self) -> NoReturn:
        for x in range(self.buffer_size):
            self.fifo.push(x)

        data: [int] = self.fifo.pop()
        expected: [int] = [
                0, 1, 2, 3, 4, 5, 6, 7
            ]
        assert_array_equal(data, expected)

    def test_filling_buffer_pop_all_manual(self) -> NoReturn:
        for x in range(self.buffer_size):
            self.fifo.push(x)

        data: [int] = self.fifo.pop(self.buffer_size)
        expected: [int] = [
                0, 1, 2, 3, 4, 5, 6, 7
            ]
        assert_array_equal(data, expected)

    def test_overfilling_buffer_pop_all_automatic(self) -> NoReturn:
        for x in range(9):
            self.fifo.push(x)

        data: [int] = self.fifo.pop()
        expected: [int] = [
                1, 2, 3, 4, 5, 6, 7, 8
            ]
        assert_array_equal(data, expected)

    def test_overfilling_buffer_pop_all_manual(self) -> NoReturn:
        for x in range(9):
            self.fifo.push(x)

        data: [int] = self.fifo.pop(self.buffer_size)
        expected: [int] = [
                1, 2, 3, 4, 5, 6, 7, 8
            ]
        assert_array_equal(data, expected)

    def test_empty_pop_initail(self) -> NoReturn:
        data: [int] = self.fifo.pop()
        expected: [int] = []
        assert_array_equal(data, expected)

    def test_empty_pop_after_push(self) -> NoReturn:
        self.fifo.push(20)
        self.fifo.pop()
        data: [int] = self.fifo.pop()
        expected: [int] = []
        assert_array_equal(data, expected)

    def test_partial_pop(self) -> NoReturn:
        for i in range(8):
            self.fifo.push(i)

        data: [int] = self.fifo.pop(1)
        expected: [int] = [0]
        assert_array_equal(data, expected)

        data = self.fifo.pop(1)
        expected = [1]
        assert_array_equal(data, expected)

        data = self.fifo.pop(2)
        expected = [2, 3]
        assert_array_equal(data, expected)

        data = self.fifo.pop(4)
        expected = [4, 5, 6, 7]
        assert_array_equal(data, expected)


if __name__ == '__main__':
    unittest.main()
