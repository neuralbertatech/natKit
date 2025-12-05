import sys

from multiprocessing import Process

from PyQt6.QtWidgets import QApplication

from typing import NoReturn


def _launch_window(window, *args) -> NoReturn:
    app = QApplication(sys.argv)
    main = window(args)
    main.show()
    sys.exit(app.exec())


def _build_and_launch_window(window_builder) -> NoReturn:
    app = QApplication(sys.argv)
    main = window_builder.build()
    main.show()
    sys.exit(app.exec_())


def launch_window(window, *args) -> NoReturn:
    process = Process(target=_launch_window, args=(window, args))
    process.start()
    return process


def build_and_launch_window(window_builder) -> NoReturn:
    process = Process(target=_build_and_launch_window, args=(window_builder,))
    process.start()
    return process


def build_and_launch_window_single_process(window_builder) -> NoReturn:
    app = QApplication(sys.argv)
    main = window_builder.build()
    main.show()
    sys.exit(app.exec())
