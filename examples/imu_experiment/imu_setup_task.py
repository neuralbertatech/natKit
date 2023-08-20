#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "..", ".."))

from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)

from typing import NoReturn

from src.widgets.setup_task_widget import SetupTaskWidgetBuilder


def main() -> NoReturn:

    builder = SetupTaskWidgetBuilder()

    build_and_launch_window_single_process(builder)


if __name__ == "__main__":
    main()
