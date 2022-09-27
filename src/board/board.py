from typing import NoReturn

import numpy as np


class Board:
    """
    An interface for the various boards to implement
    """

    def start(self) -> NoReturn:
        pass

    def stop(self) -> NoReturn:
        pass

    def get_new_data(self) -> np.array:
        pass

    def get_data_quantity(self, number_of_point: int) -> np.array:
        pass

    def get_exg_channels(self) -> np.array:
        pass

    def get_marker_channels(self) -> np.array:
        pass

    def get_sampling_rate(self) -> int:
        pass

    def get_board_description(self) -> str:
        pass
