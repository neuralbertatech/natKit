from __future__ import annotations
from src.board.board import Board
from src.core.argument_parser import get_board
from src.board.exg_pill import ExgPill
from src.data.board.supported import BoardType, get_board_type
from typing import NoReturn

import argparse


class BoardBuilder:
    def __init__(self, args: argparse.Namespace) -> NoReturn:
        self.args: argparse.Namespace = args

    @staticmethod
    def create(args: argparse.Namespace) -> BoardBuilder:
        return BoardBuilder(args)

    def build_board(self) -> Board:
        board_type: BoardType = BoardType.NONE
        board_arg = get_board(self.args)
        if board_arg.success:
            board_type = get_board_type(board_arg.value)

        match board_type:
            case BoardType.EXG_PILL:
                return ExgPill.create(self.args)

            case _:
                print("TODO: Handle BoardBuilder.build")
