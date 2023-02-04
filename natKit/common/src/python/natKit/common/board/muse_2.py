from brainflow.board_shim import BoardShim, BrainFlowInputParams
from natKit.common.board import BrainFlowBoard
from typing import NoReturn


class Muse2(BrainFlowBoard):
    """
    An interface for the Muse2 via Brainflow
    """

    def __init__(self, serial_port, debug=False) -> NoReturn:
        board_id = 22
        params = BrainFlowInputParams()
        params.serial_port = serial_port
        super().__init__(BoardShim(board_id, params), debug)
