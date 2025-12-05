from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtCore import QSize

from natKit.client.gui.pyqt6 import StreamGraph

from ..util import ImuStreams


class ImuPlotWidget(QWidget):
    def __init__(self, imu_streams: ImuStreams, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imu_streams = imu_streams

        streams_and_names = self.imu_streams.get_streams_and_names()
        self.streams = []
        self.stream_names = []
        for stream, name in streams_and_names:
            self.streams.append(stream)
            self.stream_names.append(name)

        combobox = QComboBox()

        combobox.addItems(self.stream_names)
        combobox.currentTextChanged.connect(self.stream_selected)
        layout = QVBoxLayout()
        layout.addWidget(combobox)

        self.graph = StreamGraph(self.streams[0], number_of_channels=3)
        layout.addWidget(self.graph)

        self.setLayout(layout)

    def stream_selected(self, stream_name):
        for i, name in enumerate(self.stream_names):
            if name == stream_name:
                self.graph.change_stream(self.streams[i])
                return
        print("Warning: Stream '{}' was not found!".format(stream_name))

    def sizeHint(self):
        return QSize(40, 120)
