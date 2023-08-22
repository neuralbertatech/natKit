#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "../../..", ".."))

from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)

from typing import NoReturn

from src.widgets.setup_task_widget import SetupTaskWidgetBuilder
from natKit.client.gui.pyqt6.widget import ExperimentBuilder, TaskBuilder
from natKit.client.gui.pyqt6.window import ExperimentWindowBuilder


# def build(self) -> Task:
#     return Task(
#         name=self.name,
#         stages=self.stages,
#         inter_stage_interval=self.inter_stage_interval,
#         prompt=self.prompt,
#         trigger=self.trigger,
#         events=self.events,
#         duration_events=self.duration_events,
#     )


def main() -> NoReturn:
    task = SetupTaskWidgetBuilder().set_prompt("Hi there")
    # experiment = ExperimentBuilder().add_task(task)
    build_and_launch_window_single_process(task)


if __name__ == "__main__":
    main()
