from brainflow.board_shim import BoardShim, BrainFlowInputParameters
from src.board.brain_flow_board import BrainFlowBoard
from typing import NoReturn


class Muse2(BrainFlowBoard):
    """
    An interface for the Muse2 via Brainflow
    """

    def __init__(self, serial_port, debug=False) -> NoReturn:
        board_id = 22
        params = BrainFlowInputParameters()
        params.serial_port = serial_port
        super(BoardShim(board_id, params), debug)
