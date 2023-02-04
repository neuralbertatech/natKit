from src.utility.fifo import Fifo
from numpy.testing import assert_array_equal
from typing import NoReturn

import unittest


class TestFifo(unittest.TestCase):
    def setUp(self):
        self.buffer_size: int = 8
        self.fifo: Fifo = Fifo(self.buffer_size)

    def test_pop__single_element_pop_automatic(self) -> NoReturn:
        self.fifo.push(20)

        data: [int] = self.fifo.pop()
        expected: [int] = [20]
        assert_array_equal(expected, data)

    def test_pop__single_element_pop_manual(self) -> NoReturn:
        self.fifo.push(20)

        data: [int] = self.fifo.pop(1)
        expected: [int] = [20]
        assert_array_equal(expected, data)

    def test_pop__multiple_elements_pop_automatic(self) -> NoReturn:
        for i in range(5):
            self.fifo.push(i)

        data: [int] = self.fifo.pop()
        expected: [int] = [0, 1, 2, 3, 4]
        assert_array_equal(expected, data)

    def test_pop__filling_buffer_pop_all_automatic(self) -> NoReturn:
        for x in range(self.buffer_size):
            self.fifo.push(x)

        data: [int] = self.fifo.pop()
        expected: [int] = [0, 1, 2, 3, 4, 5, 6, 7]
        assert_array_equal(expected, data)

    def test_pop__filling_buffer_pop_all_manual(self) -> NoReturn:
        for x in range(self.buffer_size):
            self.fifo.push(x)

        data: [int] = self.fifo.pop(self.buffer_size)
        expected: [int] = [0, 1, 2, 3, 4, 5, 6, 7]
        assert_array_equal(expected, data)

    def test_pop__overfilling_buffer_pop_all_automatic(self) -> NoReturn:
        for x in range(9):
            self.fifo.push(x)

        data: [int] = self.fifo.pop()
        expected: [int] = [1, 2, 3, 4, 5, 6, 7, 8]
        assert_array_equal(expected, data)

    def test_pop__overfilling_buffer_pop_all_manual(self) -> NoReturn:
        for x in range(9):
            self.fifo.push(x)

        data: [int] = self.fifo.pop(self.buffer_size)
        expected: [int] = [1, 2, 3, 4, 5, 6, 7, 8]
        assert_array_equal(expected, data)

    def test_pop__empty_pop_initail(self) -> NoReturn:
        data: [int] = self.fifo.pop()
        expected: [int] = []
        assert_array_equal(expected, data)

    def test_pop__empty_pop_after_push(self) -> NoReturn:
        self.fifo.push(20)
        self.fifo.pop()
        data: [int] = self.fifo.pop()
        expected: [int] = []
        assert_array_equal(expected, data)

    def test_pop__partial_pop(self) -> NoReturn:
        for i in range(8):
            self.fifo.push(i)

        data: [int] = self.fifo.pop(1)
        expected: [int] = [0]
        assert_array_equal(expected, data)

        data = self.fifo.pop(1)
        expected = [1]
        assert_array_equal(expected, data)

        data = self.fifo.pop(2)
        expected = [2, 3]
        assert_array_equal(expected, data)

        data = self.fifo.pop(4)
        expected = [4, 5, 6, 7]
        assert_array_equal(expected, data)

    def test_pop_one__empty_pop(self) -> NoReturn:
        self.assertIs(None, self.fifo.pop_one())

    def test_pop_one__normal_pop(self) -> NoReturn:
        items: [int] = [x for x in range(3)]
        data: [int] = []
        for i in items:
            self.fifo.push(i)
        for i in range(len(items)):
            data.append(self.fifo.pop_one())

        expected: [int] = items
        assert_array_equal(expected, data)

    def test_pop_one__empty_pop_after_push(self) -> NoReturn:
        items: [int] = [x for x in range(3)]
        data: [int] = []
        for i in items:
            self.fifo.push(i)
        for i in range(len(items)):
            data.append(self.fifo.pop_one())

        expected: [int] = items
        assert_array_equal(expected, data)
        self.assertIs(self.fifo.pop_one(), None)

    def test_to_list__empty_list(self) -> NoReturn:
        self.assertEqual(self.fifo.to_list(), [])

    def test_to_list__normal_list(self) -> NoReturn:
        items: [int] = [x for x in range(3)]
        for i in items:
            self.fifo.push(i)
        data: [int] = self.fifo.pop()

        expected: [int] = [0, 1, 2]
        assert_array_equal(expected, data)

    def test_to_list__overflowed_buffer(self) -> NoReturn:
        items: [int] = [x for x in range(12)]
        for i in items:
            self.fifo.push(i)
        data: [int] = self.fifo.pop()

        expected: [int] = [x for x in range(4, 12)]
        assert_array_equal(expected, data)

    def test_extend__normal(self) -> NoReturn:
        items: [int] = [x for x in range(3)]
        self.fifo.extend(items)

        data: [int] = self.fifo.pop()
        expected: [int] = items
        assert_array_equal(expected, data)

    def test_extend__overflow(self) -> NoReturn:
        items: [int] = [x for x in range(9)]
        self.fifo.extend(items)

        data: [int] = self.fifo.pop()
        expected: [int] = [x for x in range(1, 9)]
        assert_array_equal(expected, data)


if __name__ == "__main__":
    unittest.main()
