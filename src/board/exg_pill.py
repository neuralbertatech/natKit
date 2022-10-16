from __future__ import annotations
from src.board.board import Board
from src.connector.serial import Serial
from src.core.argument_parser import (
    get_channels,
    get_baud_rate,
    get_com_port,
    get_in_file,
    get_out_file,
    is_simulate_command,
    is_connect_command,
)
from src.utility.result import Result
from src.utility.type_conversion import string_to_int
from src.stream.file_stream import FileStream
from src.stream.serial_stream import SerialStream
from src.stream.std_stream import StdStream
from src.stream.stream import Stream
from typing import NoReturn

import argparse

import numpy as np


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

    @staticmethod
    def create(args: argparse.Namespace) -> ExgPill:
        in_stream: Stream = StdStream()
        out_stream: Stream = StdStream()

        out_file: str = get_out_file(args)
        if out_file.success:
            out_stream = FileStream(out_file.value, "w")

        in_file: str = get_in_file(args)
        sample_rate: int = 0
        if is_simulate_command(args) and in_file.success:
            in_stream = FileStream(in_file.value, "r")
        elif is_connect_command:
            com_port: str = "COM6"
            baud_rate: int = 115200
            sample_rate = 125
            buffer_size: int = 1024
            com_port_arg: Result[str] = get_com_port(args)
            baud_rate_arg: Result[str] = get_baud_rate(args)
            if com_port_arg.success:
                com_port = com_port_arg.value
            if baud_rate_arg.success:
                baud_rate = string_to_int(baud_rate_arg.value)

            serial: Serial = Serial(com_port, baud_rate)
            in_stream = SerialStream(serial, sample_rate, buffer_size)

        channels: int = 5
        channels_arg: Result[str] = get_channels(args)
        if channels_arg.success:
            channels = string_to_int(channels_arg.value)

        return ExgPill(in_stream, out_stream, channels, sample_rate)

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
        self.in_stream.start()
        self.out_stream.start()

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
