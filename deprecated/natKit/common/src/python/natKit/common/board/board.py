from typing import NoReturn

import numpy as np


class Board:
    """
    An interface for the various boards to implement
    """

    def start(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def stop(self) -> NoReturn:
        assert 0, "Abstract function not implemented!"

    def get_new_data(self) -> np.array:
        assert 0, "Abstract function not implemented!"

    def get_data_quantity(self, number_of_point: int) -> np.array:
        assert 0, "Abstract function not implemented!"

    def get_exg_channels(self) -> np.array:
        assert 0, "Abstract function not implemented!"

    def get_marker_channels(self) -> np.array:
        assert 0, "Abstract function not implemented!"

    def get_sampling_rate(self) -> int:
        assert 0, "Abstract function not implemented!"

    def get_board_description(self) -> str:
        assert 0, "Abstract function not implemented!"
