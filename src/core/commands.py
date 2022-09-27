from src.board.board_builder import BoardBuilder
from src.board.board import Board
from typing import NoReturn

import argparse
import time

import numpy as np


def handle_command(args: argparse.Namespace) -> NoReturn:
    builder: BoardBuilder = BoardBuilder.create(args)
    board: Board = builder.build_board()
    board.start()
    while True:
        data: np.array = board.get_new_data()
        for d in data:
            board.out_stream.write(str(d))
        time.sleep(0.001)

    # if args.command == 'connect':
    #     handle_connect(args)
    # elif args.command == 'simulate':
    #     handle_simulate(args)


# def handle_connect(args: argparse.Namespace) -> NoReturn:
#     print("Connect")
#
# def handle_simulate(args: argparse.Namespace) -> NoReturn:
#     print("simulate")
