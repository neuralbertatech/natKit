from src.board.board_builder import BoardBuilder
from src.board.board import Board
from src.core.argument_parser import (
    is_gui_enabled,
    is_connect_command,
    is_simulate_command,
)
from src.gui.widget.graph_widget import GraphWidget
from src.gui.window.window import Window
from threading import Thread
from typing import NoReturn
from PyQt5.QtWidgets import QApplication

import argparse
import time

import numpy as np


RUNNING: bool = True


def handle_command(args: argparse.Namespace) -> NoReturn:
    builder: BoardBuilder = BoardBuilder.create(args)
    board: Board = builder.build_board()
    board.start()
    global RUNNER_THREAD
    RUNNER_THREAD = Thread(target=run_board, args=(board,))
    RUNNER_THREAD.start()

    if is_connect_command(args):
        handle_connect(args)
    elif is_simulate_command(args):
        handle_simulate(args)

    if is_gui_enabled(args):
        handle_graph(board, args)


def run_board(board: Board):
    global RUNNING
    while RUNNING:
        data: np.array = board.get_new_data()
        for d in data:
            board.out_stream.write(d)
        time.sleep(0.001)


def handle_connect(args: argparse.Namespace) -> NoReturn:
    print("Connect")


def handle_simulate(args: argparse.Namespace) -> NoReturn:
    print("Simulate")


def handle_graph(board: Board, args: argparse.Namespace) -> NoReturn:
    global RUNNING
    app = QApplication([""])
    graph: GraphWidget = GraphWidget(board.out_stream, 5)
    graph.start()
    window = Window(graph)
    window.show()

    app.exec()
    RUNNING = False
