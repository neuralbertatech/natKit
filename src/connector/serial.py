from typing import NoReturn

import serial


class Serial:
    """ Connect to a serial port to send and receive data"""

    def __init__(self, com_port: str, baud_rate: int) -> NoReturn:
        self.com_port: str = com_port
        self.baud_rate: int = baud_rate
        self.serial_connection: serial.Serial = serial.Serial(com_port, baud_rate)

    def readline(self) -> str:
        return self.serial_connection.readline().decode('utf-8')
