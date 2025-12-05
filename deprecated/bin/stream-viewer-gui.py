#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from natKit.client.gui.pyqt6 import StreamGraph
from natKit.common.kafka import KafkaManager


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.manager = KafkaManager.create()

        combobox = QComboBox()

        self.streams = self.manager.find_streams()
        self.stream_names = [stream.get_name() for stream in self.streams]
        combobox.addItems(self.stream_names)
        combobox.currentTextChanged.connect(self.stream_selected)

        layout = QVBoxLayout()
        layout.addWidget(combobox)

        self.graph = StreamGraph(self.streams[0])
        layout.addWidget(self.graph)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    def stream_selected(self, stream_name):
        for i, name in enumerate(self.stream_names):
            if name == stream_name:
                self.graph.change_stream(self.streams[i])
                return
        print("Warning: Stream '{}' was not found!".format(stream_name))


def main():
    app = QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
