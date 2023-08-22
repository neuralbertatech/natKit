#!/usr/bin/env python

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "..", ".."))

from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QStackedWidget

from src.tasks import QueryTaskWidgetBuilder
from src.widgets import SetupTaskWidgetBuilder

from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)
from natKit.common.kafka import KafkaManager


class ImuExperiment(QMainWindow):
    def __init__(
        self,
        parent=None,
        query_task: QueryTaskWidgetBuilder = None,
        setup_task: SetupTaskWidgetBuilder = None,
    ):
        super().__init__(parent)

        self.query_task = query_task.build()
        self.setup_task = setup_task.build()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.query_task)
        self.stacked_widget.addWidget(self.setup_task)

        self.query_task.onNext.connect(self.switch_to_setup_task)
        self.setup_task.onPrev.connect(self.switch_to_query_task)

        self.setWindowTitle("Imu Experiment")

        self.setCentralWidget(self.stacked_widget)
        self.switch_to_query_task()
        self.show()

    def switch_to_setup_task(self):
        self.setup_task.set_imu_streams(self.query_task.get_selected_streams())
        self.setup_task.setup()
        self.stacked_widget.setCurrentWidget(self.setup_task)

    def switch_to_query_task(self):
        self.query_task.setup()
        self.stacked_widget.setCurrentWidget(self.query_task)


class ImuExperimentBuilder:
    def __init__(self):
        self.query_task = None
        self.setup_task = None

    def build(self) -> ImuExperiment:
        return ImuExperiment(query_task=self.query_task, setup_task=self.setup_task)

    def set_query_task(
        self, query_task: QueryTaskWidgetBuilder
    ) -> ImuExperimentBuilder:
        self.query_task = query_task
        return self

    def set_setup_task(
        self, setup_task: SetupTaskWidgetBuilder
    ) -> ImuExperimentBuilder:
        self.setup_task = setup_task
        return self


if __name__ == "__main__":
    manager = KafkaManager.create()

    builder = (
        ImuExperimentBuilder()
        .set_query_task(QueryTaskWidgetBuilder().set_kafka_manager(manager))
        .set_setup_task(SetupTaskWidgetBuilder().set_kafka_manager(manager))
    )
    build_and_launch_window_single_process(builder)
