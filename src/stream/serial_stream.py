from src.connector.serial import Serial
from src.stream.stream import Stream
from src.utility.fifo import Fifo
from src.utility.type_conversion import string_to_float
from threading import Thread
from typing import NoReturn

import time

ns_per_second: int = 1000000000


class SerialStream(Thread, Stream):
    """Streams data from a serial connection

    Parameters:
        serial_connection[Serial]: A connector to the serial device
        sample_rate[int]: The sampling rate used to poll the stream
        buffer_size[int]: The size to set the buffer
    """

    def __init__(
        self, serial_connection: Serial, sample_rate: int, buffer_size: int = 1024
    ):
        Thread.__init__(self, daemon=True)
        self.serial_connection = serial_connection

        self.buffer: Fifo = Fifo(buffer_size)
        self.ns_per_sample: int = 1 / (sample_rate * 2) * ns_per_second

    def run(self) -> NoReturn:
        """Starts the data acquisition from the given com port"""
        self.thread_running: bool = True
        while self.thread_running:
            start: int = time.time_ns()
            sample: str = self.serial_connection.readline()
            if sample != "":
                split_sample: [str] = [string_to_float(x) for x in sample.split(",")]
                self.buffer.push(split_sample)

            time_diff: int = time.time_ns() - start
            if time_diff < self.ns_per_sample:
                time.sleep((self.ns_per_sample - time_diff) / ns_per_second)

    def read(self) -> [int]:
        return self.buffer.pop(1)

    def write(self, data: [int]) -> NoReturn:
        self.buffer.push(data)

    def close(self) -> NoReturn:
        self.stop()

    def pop_data(self) -> [int]:
        """
        Grabs the most recent data from the ring buffer

        Returns:
            An array containing the most recent, unread, data points aquired from the stream
        """
        return self.buffer.pop()

    def fetch_data(self, number_of_samples: int) -> [int]:
        """
        Grabs all of the data contained on the ring buffer

        Returns:
            An array containing all the data points stored in the buffer
        """
        return self.buffer.pop(number_of_samples)

    def stop(self) -> NoReturn:
        """
        Stops the stream from aquiring data
        """
        self.thread_running = False
