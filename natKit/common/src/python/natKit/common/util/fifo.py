from threading import Lock

from typing import Generic
from typing import List
from typing import NoReturn
from typing import TypeVar


T = TypeVar("T")


class Fifo(Generic[T]):
    """A First In First Out data structure that is thread safe"""

    def __init__(self, buffer_size: int = 1024) -> NoReturn:
        self.buffer_size: int = buffer_size + 1
        self.ring_buffer: List[T] = [0 for i in range(self.buffer_size)]
        self.buffer_lock: Lock = Lock()
        self.buffer_current_index: int = 0
        self.buffer_last_read_index: int = 0

    def __get_num_items_in_buffer(self) -> int:
        if self.buffer_current_index >= self.buffer_last_read_index:
            return self.buffer_current_index - self.buffer_last_read_index
        else:
            return (
                self.buffer_size
                - self.buffer_last_read_index
                + self.buffer_current_index
            )

    def __get_amt_from_buffer(self, amt: int) -> List[T]:
        if amt > (self.buffer_size - self.buffer_last_read_index):
            overflow: int = amt - (self.buffer_size - self.buffer_last_read_index)
            return (
                self.ring_buffer[self.buffer_last_read_index :]
                + self.ring_buffer[:overflow]
            )
        else:
            return self.ring_buffer[
                self.buffer_last_read_index : self.buffer_last_read_index + amt
            ]

    def __add_data_to_buffer(self, data: List[T]) -> NoReturn:
        # Add data to the buffer
        for i, datum in enumerate(data):
            self.ring_buffer[(self.buffer_current_index + i) % self.buffer_size] = datum

        # Readjust ring buffer pointers
        filled_buffer = False
        if self.buffer_last_read_index <= self.buffer_current_index:
            if (
                len(data)
                >= (self.buffer_last_read_index + self.buffer_size)
                - self.buffer_current_index
            ):
                filled_buffer = True
        else:
            if len(data) >= self.buffer_last_read_index - self.buffer_current_index:
                filled_buffer = True

        if filled_buffer:
            self.buffer_last_read_index = (
                self.buffer_current_index + len(data) + 1
            ) % self.buffer_size

        self.buffer_current_index = (
            self.buffer_current_index + len(data)
        ) % self.buffer_size
        if self.buffer_last_read_index == self.buffer_current_index:
            self.buffer_last_read_index = (
                self.buffer_last_read_index + 1
            ) % self.buffer_size

    def pop(self, amt: int = None) -> List[T]:
        """
        Grabs all of the data contained on the ring buffer

        Returns:
            An array containing all the data points stored in the buffer
        """
        self.buffer_lock.acquire()
        if amt is None:
            amt = self.__get_num_items_in_buffer()
        else:
            amt = min(amt, self.__get_num_items_in_buffer())

        ret_data: List[T] = self.__get_amt_from_buffer(amt)
        self.buffer_last_read_index = (
            self.buffer_last_read_index + amt
        ) % self.buffer_size
        self.buffer_lock.release()

        return ret_data

    def pop_one(self) -> T:
        data: T = self.pop(1)
        if data == [] or data is None:
            return None
        else:
            return data[0]

    def push(self, data: T) -> NoReturn:
        """Adds data to the buffer

        Parameters:
            data: The data to add
        """
        self.buffer_lock.acquire()
        self.__add_data_to_buffer([data])
        self.buffer_lock.release()

    def to_list(self) -> List[T]:
        """
        Grabs all of the data contained on the ring buffer

        Returns:
            An array containing all the data points stored in the buffer
        """
        amt: int = self.__get_num_items_in_buffer()

        self.buffer_lock.acquire()
        ret_data: List[T] = self.__get_amt_from_buffer(amt)
        self.buffer_lock.release()

        return ret_data

    def extend(self, data: List[T]) -> NoReturn:
        self.buffer_lock.acquire()
        self.__add_data_to_buffer(data)
        self.buffer_lock.release()
