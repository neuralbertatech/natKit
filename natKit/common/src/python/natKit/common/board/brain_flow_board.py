from brainflow.board_shim import BoardShim
from natKit.common.board import Board
from typing import NoReturn, List

import numpy as np


class BrainFlowBoard(Board):
    """
    A superclass for Brainflow boards
    """

    def __init__(
        self,
        board: BoardShim,
        debug=False,
    ):
        self.board = board
        self.board_id = self.board.get_board_id()

        if debug:
            BoardShim.enable_dev_board_logger()

        self.board.prepare_session()

        self.exg_channels = np.array(BoardShim.get_exg_channels(self.board_id))
        self.marker_channel = np.array(BoardShim.get_marker_channel(self.board_id))
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.chan_num = len(self.exg_channels)
        self.last_board_data_count = 0

    def start(self) -> NoReturn:
        self.board.start_stream()

    def get_new_data(self) -> np.array:
        """
        Check how much data has been added to the ringbuffer since last call (to this function) and grab that much data
        """
        new_board_data_count = self.get_board_data_count()
        count_diff = new_board_data_count - self.last_board_data_count
        self.last_board_data_count = new_board_data_count
        return self.get_current_board_data(count_diff)

    def get_data_quantity(self, num_points: int) -> np.array:
        """
        Get only a specified amount of most recent board data
        """
        return self.get_current_board_data(num_points)

    def stop(self) -> NoReturn:
        """Stops the stream and releases the session all at once"""
        self.stop_stream()
        self.release_session()

    def get_exg_channels(self) -> np.array:
        """
        returns the indices of eeg channels in data (as a numpy array)
        """
        return self.exg_channels

    def get_marker_channels(self) -> List[int]:
        return self.marker_channel

    def get_sampling_rate(self) -> int:
        return self.sampling_rate

    def get_board_description(self) -> str:
        return BoardShim.get_board_descr(self.board_id)
