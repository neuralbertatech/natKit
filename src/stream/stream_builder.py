from __future__ import annotations
from src.connector.serial import Serial
from src.data.stream.supported import StreamType, get_stream_type
from src.stream.file_stream import FileStream
from src.stream.serial_stream import SerialStream
from src.stream.std_stream import StdStream
from src.stream.stream import Stream
from typing import NoReturn

import argparse


class StreamBuilder:
    def __init__(self, args: argparse.Namespace) -> NoReturn:
        self.args: argparse.Namespace = args
        self.stream: str = None
        self.stream_type: StreamType = None
        self.com_port: str = None

    def _expect_argument(self, arg, msg: str) -> NoReturn:
        if arg is None:
            print("CLI argument error: " + msg)
            exit(1)

    def _parse_stream_args(self) -> NoReturn:
        self.stream = self.args.stream
        self.stream_type = get_stream_type(self.stream)
        self.com_port = self.args.com_port if self.args.com_port is not None else None
        self.number_of_channels = (
                self.args.channels if self.args.channels is not None else None
            )

    def _set_stream_defaults(self) -> NoReturn:
        if self.stream_type is None:
            return

        match self.stream_type:
            case StreamType.FILE:
                pass

            case StreamType.SERIAL:
                self.com_port = 'COM4' if self.com_port is None else self.com_port
                self.number_of_channels = (
                        5 if self.number_of_channels is None else self.number_of_channels
                    )

            case StreamType.STD:
                pass

            case _:
                print('TODO: Handle StreamBuilder._set_stream_defaults')

    @staticmethod
    def create(args: argparse.Namespace) -> StreamBuilder:
        return StreamBuilder(args)

    def build_input_stream(self) -> Stream:
        self._parse_stream_args()
        self._set_stream_defaults()

        match self.board_type:
            case StreamType.FILE:
                self._expect_argument(self.file_name, "File not specified")
                return FileStream(self.file_name)

            case StreamType.SERIAL:
                serial: Serial = Serial(self.com_port, self.baud_rate)
                return SerialStream(serial, self.sample_rate)

            case StreamType.STD:
                return StdStream()

            case _:
                print('TODO: Handle BoardBuilder.build')
