#!/usr/bin/env python

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "../../..", ".."))

from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)
from natKit.common.kafka import KafkaManager

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from time import sleep
from typing import NoReturn
from ..util import ImuStreams

# imu_selector_num = 7
imu_position_names = [
    "Left Wrist",
    "Left Elbow",
    "Left Shoulder",
    "Trunk",
    "Right Shoulder",
    "Right Elbow",
    "Right Wrist",
]
imu_selector_labels = [
    "IMU {} ({})".format(i, label) for i, label in enumerate(imu_position_names)
]
imu_dict = {"255771429458452": imu_position_names[0]}


class ComboBox(QtWidgets.QComboBox):
    popupAboutToBeShown = pyqtSignal()

    def showPopup(self):
        self.popupAboutToBeShown.emit()
        super().showPopup()


class _ImuSelectorsWidget(QtWidgets.QWidget):
    def __init__(self, kafka_manager: KafkaManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streams = kafka_manager.find_streams()
        self.stream_names = None
        self.stream_name_to_index_map = {}

        layout = QtWidgets.QGridLayout()  # Y Rows, X Columns
        self.combo_boxes = []
        self.combo_box_labels = []

        for i, imu in enumerate(imu_selector_labels):
            self.combo_box_labels.append(QtWidgets.QLabel(imu))
            layout.addWidget(self.combo_box_labels[i], i, 2)

            self.combo_boxes.append(ComboBox(self))  # lots of things
            layout.addWidget(self.combo_boxes[i], i, 4)

            self.combo_boxes[i].addItem("-")
            self.combo_boxes[i].popupAboutToBeShown.connect(
                lambda i=i: self.populateDropdowns()
            )

        self.setLayout(layout)

        self.populateDropdowns()

        self.start_query()

    def start_query(self) -> NoReturn:
        if self.stream_names is not None:
            for i in range(len(self.combo_boxes)):
                for stream in self.streams:
                    name = stream.stream_name
                    split_name = name.split("-")
                    if len(split_name) > 1:
                        lookup_name = ""
                        if split_name[1] in imu_dict:
                            lookup_name = imu_dict[split_name[1]]
                        if lookup_name == imu_position_names[i]:
                            self.combo_boxes[i].setCurrentIndex(i + 1)

    def populateDropdowns(self):
        if self.stream_names == None:
            self.stream_names = []
            for i, stream in enumerate(self.streams):
                while not stream.stream_ready:
                    pass

                readable_name = "UNKNOWN"
                split_stream_name = stream.stream_name.split("-")
                if len(split_stream_name) > 1:
                    stream_id = split_stream_name[1]
                    if stream_id in imu_dict:
                        readable_name = imu_dict[stream_id]
                formatted_stream_name = "{} ({})".format(
                    stream.stream_name, readable_name
                )
                self.stream_name_to_index_map[formatted_stream_name] = i
                self.stream_names.append(formatted_stream_name)
            for i in range(len(self.combo_boxes)):
                self.combo_boxes[i].addItems(self.stream_names)

    def get_selected_streams(self) -> ImuStreams:
        streams = []
        for combo in self.combo_boxes:
            text = combo.currentText()
            if text == "-" or text not in self.stream_name_to_index_map:
                streams.append(None)
            else:
                streams.append(self.streams[self.stream_name_to_index_map[text]])
        return ImuStreams.createFromList(streams)


class QueryTaskWidget(QtWidgets.QWidget):
    """ """

    onNext = pyqtSignal()

    def __init__(self, kafka_manager: KafkaManager, steps=5, *args, **kwargs):
        super(QueryTaskWidget, self).__init__(*args, **kwargs)
        self.kafka_manager = kafka_manager

    def setup(self):
        self.layout = QtWidgets.QVBoxLayout()
        self._title_label = QtWidgets.QLabel(
            "IMU Query Task Window", alignment=Qt.AlignmentFlag.AlignCenter
        )
        self.layout.addWidget(self._title_label)

        self._imu_selectors_wdiget = _ImuSelectorsWidget(self.kafka_manager)
        self.layout.addWidget(self._imu_selectors_wdiget)

        self._next_task_button = QtWidgets.QPushButton(text="Setup ->")
        self._next_task_button.clicked.connect(lambda: self.onNext.emit())
        self.layout.addWidget(
            self._next_task_button, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.setLayout(self.layout)

    def get_selected_streams(self) -> ImuStreams:
        return self._imu_selectors_wdiget.get_selected_streams()

    def sizeHint(self):
        return QtCore.QSize(220, 180)


class QueryTaskWidgetBuilder:
    def __init__(self) -> NoReturn:
        self._kafka_manager = None

    def build(self) -> QueryTaskWidget:
        return QueryTaskWidget(kafka_manager=self._kafka_manager)

    def set_kafka_manager(self, manager: KafkaManager):
        self._kafka_manager = manager
        return self


def main() -> NoReturn:

    manager = KafkaManager.create()

    builder = QueryTaskWidgetBuilder().set_kafka_manager(manager)

    build_and_launch_window_single_process(builder)


if __name__ == "__main__":
    main()
