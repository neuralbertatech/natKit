from __future__ import annotations

import numpy as np

from natKit.common.board import Board
from natKit.common.connector import Serial
from natKit.common.util import Fifo
from natKit.common.util import Result
from natKit.common.util import string_to_int
from natKit.common.stream import Stream

from typing import NoReturn


class ExgPill(Board):
    """
    An implementation of Board for the Exg-Pill Bio Amp from UpsideDown Labs
    """

    def __init__(
        self,
        in_stream: Stream,
        out_stream: Stream,
        number_of_channels: int = 5,
        sample_rate: int = 125,
    ) -> NoReturn:
        self.number_of_channels: np.array = np.array([number_of_channels + 1])
        self.sample_rate: int = sample_rate
        self.exg_channels: np.array = np.array(
            [x + 1 for x in range(number_of_channels)]
        )
        self.description: str = "UpsideDown Labs EXG Pill"
        self.in_stream = in_stream
        self.out_stream = out_stream

    def _format_data(self, data: np.array) -> np.array:
        """
        Formats the data with zeros in the first column (the marker column) and the range in the
        last column

        Args:
            data: A two dimentional array containing an array of samples for each channels

        Returns:
            Returns a formated copy of data

        TODO: This function should not be needed anymore, refactor and remove it.
        """
        if data.shape[0] == 0:
            return data

        formatted_data: np.array = np.array([])
        if len(data.shape) == 1:
            size: int = 1
            new_data = [
                [x for x in range(size)],
                *[[x] for x in data],
                [0 for x in range(size)],
            ]
            formatted_data = np.array(new_data)
        else:
            size: int = data.shape[1]
            formatted_data: np.array = np.array(
                [np.arange(size), *data, np.zeros(size)]
            )
        return formatted_data

    def start(self):
        """
        Start the data aquasition
        """
        self.in_stream.open()
        self.out_stream.open()

    def stop(self) -> NoReturn:
        """
        Stop the aquasition of data
        """
        self.in_stream.close()
        self.out_stream.close()

    def get_new_data(self) -> np.array:
        """
        Check how much data has been added to the ringbuffer since last call
        (to this function) and grab that much data

        Returns:
            A np array of all the new data
        """
        return self._format_data(np.transpose(self.in_stream.read()))

    def get_data_quantity(self, number_of_points: int) -> np.array:
        """
        Get only a specified amount of most recent board data.

        Returns:
            A np array of the amount of new data less than or equal to
            number_of_points
        """
        return self._format_data(np.transpose(self.in_stream.read()))

    def get_exg_channels(self) -> np.array:
        """
        Get the indexes of the exg channels

        Returns:
            Returns an array of indexes that describe the exg channels
        """
        return self.exg_channels

    def get_marker_channels(self) -> np.array:
        """
        Get the indexes of the marker channels

        Returns:
            Returns an array of indexes that describe the marker channels
        """
        return self.number_of_channels

    def get_sampling_rate(self) -> int:
        """
        Get the current sampling rate

        Returns:
            The sample rate
        """
        return self.sample_rate

    # TODO: Make this match what brainflow does
    def get_board_description(self) -> str:
        """
        Returns a description of the board

        Returns:
            The board description
        """
        return self.description
