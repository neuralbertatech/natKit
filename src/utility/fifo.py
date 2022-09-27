from threading import Lock
from typing import Generic, List, NoReturn, TypeVar


T = TypeVar('T')


class Fifo(Generic[T]):
    """ A First In First Out data structure that is thread safe """

    def __init__(self, buffer_size: int = 1024) -> NoReturn:
        self.buffer_size: int = buffer_size + 1
        self.ring_buffer: List[T] = [None for i in range(self.buffer_size)]
        self.buffer_lock: Lock = Lock()
        self.buffer_current_index: int = 0
        self.buffer_last_read_index: int = 0

    def pop(self, amt: int = None) -> List[T]:
        """
        Grabs all of the data contained on the ring buffer

        Returns:
            An array containing all the data points stored in the buffer
        """
        if amt is None:
            if self.buffer_current_index >= self.buffer_last_read_index:
                amt = self.buffer_current_index - self.buffer_last_read_index
            else:
                amt = (
                        self.buffer_size -
                        self.buffer_last_read_index +
                        self.buffer_current_index
                    )

        ret_data: List[T] = []

        self.buffer_lock.acquire()
        if amt > self.buffer_size - self.buffer_last_read_index:
            overflow: int = amt - (self.buffer_size - self.buffer_last_read_index)
            ret_data = (
                    self.ring_buffer[self.buffer_last_read_index:] +
                    self.ring_buffer[:overflow]
                )
        else:
            ret_data = self.ring_buffer[
                    self.buffer_last_read_index:self.buffer_last_read_index + amt
                ]
        self.buffer_last_read_index = (self.buffer_last_read_index + amt) % self.buffer_size
        self.buffer_lock.release()

        return ret_data

    def push(self, data: T) -> NoReturn:
        """ Adds data to the buffer

        Parameters:
            data: The data to add
        """
        self.buffer_lock.acquire()
        self.ring_buffer[self.buffer_current_index] = data
        self.buffer_current_index = (self.buffer_current_index + 1) % self.buffer_size
        if self.buffer_last_read_index == self.buffer_current_index:
            self.buffer_last_read_index = (
                    (self.buffer_last_read_index + 1) % self.buffer_size
                )
        self.buffer_lock.release()
