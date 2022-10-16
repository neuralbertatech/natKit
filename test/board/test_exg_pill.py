from src.board.exg_pill import ExgPill
from numpy.testing import assert_array_equal
from unittest.mock import Mock
from typing import NoReturn

import unittest
import numpy as np


class TestExgPill(unittest.TestCase):
    def setUp(self):
        self.mock_in_stream = Mock()
        self.mock_out_stream = Mock()
        self.exg_pill: ExgPill = ExgPill(self.mock_in_stream, self.mock_out_stream)
        self.sample_data: np.array = np.array(
            [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11, 12, 13, 14]]
        )
        self.sample_data_point: np.array = np.array([0, 1, 2, 3, 4])

    def test_start(self) -> NoReturn:
        self.exg_pill.start()
        self.mock_in_stream.start.assert_called_once()

    def test_stop(self) -> NoReturn:
        self.exg_pill.stop()
        self.mock_in_stream.close.assert_called_once()

    def test_get_new_data(self) -> NoReturn:
        self.mock_in_stream.read = Mock(return_value=self.sample_data_point)
        data_received: np.array = self.exg_pill.get_new_data()

        self.mock_in_stream.read.assert_called_once()
        expected: np.array = np.array(
            [
                np.array([0]),
                np.array([0]),
                np.array([1]),
                np.array([2]),
                np.array([3]),
                np.array([4]),
                np.array([0]),
            ]
        )
        assert_array_equal(data_received, expected)

    def test_get_new_data_empty(self) -> NoReturn:
        self.mock_in_stream.read = Mock(return_value=np.array([]))
        data_received: np.array = self.exg_pill.get_new_data()

        self.mock_in_stream.read.assert_called_once()
        expected: np.array = np.array([])
        assert_array_equal(data_received, expected)

    def test_get_data_quantity(self) -> NoReturn:
        self.mock_in_stream.read = Mock(return_value=self.sample_data_point)
        data_received: np.array = self.exg_pill.get_data_quantity(3)

        self.mock_in_stream.read.assert_called_once()
        expected: np.array = np.array(
            [
                np.array([0]),
                np.array([0]),
                np.array([1]),
                np.array([2]),
                np.array([3]),
                np.array([4]),
                np.array([0]),
            ]
        )
        assert_array_equal(data_received, expected)

    def test_get_data_quantity_empty(self) -> NoReturn:
        self.mock_in_stream.read = Mock(return_value=np.array([]))
        data_received: np.array = self.exg_pill.get_data_quantity(3)

        self.mock_in_stream.read.assert_called_once()
        expected: np.array = np.array([])
        assert_array_equal(data_received, expected)

    def test_get_exg_channels(self) -> NoReturn:
        data_received: np.array = self.exg_pill.get_exg_channels()
        expected: np.array = np.array([1, 2, 3, 4, 5])
        assert_array_equal(data_received, expected)

    def test_get_marker_channels(self) -> NoReturn:
        data_received: np.array = self.exg_pill.get_marker_channels()
        expected: np.array = np.array([6])
        assert_array_equal(data_received, expected)

    def test_get_sampling_rate(self) -> NoReturn:
        self.assertEqual(self.exg_pill.get_sampling_rate(), 125)

    def test_get_board_description(self) -> NoReturn:
        self.assertEqual(
            self.exg_pill.get_board_description(), "UpsideDown Labs EXG Pill"
        )


if __name__ == "__main__":
    unittest.main()
