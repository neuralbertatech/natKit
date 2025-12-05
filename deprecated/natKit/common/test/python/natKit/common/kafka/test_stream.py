from natKit.common.kafka import Stream
from numpy.testing import assert_array_equal
from typing import NoReturn

import unittest


class TestStream(unittest.TestCase):
    def setUp(self):
        pass

    def test_pop__single_element_pop_automatic(self) -> NoReturn:
        self.fifo.push(20)

        data: [int] = self.fifo.pop()
        expected: [int] = [20]
        assert_array_equal(expected, data)


