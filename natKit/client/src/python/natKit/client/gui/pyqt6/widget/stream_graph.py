import pyqtgraph as pg

from natKit.api import ImuDataSchema
from natKit.api import SimpleMessageSchema
from natKit.client.gui.pyqt6 import GraphLine
from natKit.common.kafka import Stream
from natKit.common.util import Point

from PyQt6 import QtCore
from PyQt6 import QtWidgets

from typing import NoReturn


# class StreamGraph(QtWidgets.QWidget):
class StreamGraph(pg.PlotWidget):
    def __init__(
        self, stream: Stream, number_of_channels: int = 1, parent=None
    ) -> NoReturn:
        super(StreamGraph, self).__init__(parent)

        self.stream = stream
        self.number_of_channels = number_of_channels

        # self.graphWidget = pg.PlotWidget()
        self.layout = QtWidgets.QVBoxLayout()
        self.view = pg.GraphicsView()
        # self.layout.addWidget(self.graphWidget)
        self.layout.addWidget(self)

        # self.layout = pg.GraphicsLayout()
        # self.view.setCentralItem(self)
        # self.view.show()

        self.max_x = 1024

        # self.graphWidget.setBackground('w')
        self.setBackground("w")
        colors = ["red", "blue", "green", "yellow", "purple"]
        self.lines = []
        self.data_lines = []
        for i in range(self.number_of_channels):
            self.lines.append(GraphLine(self.max_x))
            self.data_lines.append(
                self.plot(
                    [], [], name=str(i), pen=pg.mkPen(color=colors[i % len(colors)])
                )
            )
            # self.data_lines.append(self.addPlot(i, 0))
            # if i > 0:
            #    self.data_lines[i].setXLink(self.data_lines[0])

        self.index = 0

        self.timer = QtCore.QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update_plot_data)
        self.timer.start()

    def update_plot_values(self, x, y) -> NoReturn:
        if len(self.x) == self.max_x:
            self.x = self.x[1:]
            self.y = self.y[1:]

        self.x.append(x)
        self.y.append(y)

    def update_plot_data(self) -> NoReturn:
        while True:
            data = self.stream.read_data()
            if data is None:
                break

            if isinstance(data, ImuDataSchema):
                values = data.data
                for i in range(self.number_of_channels):
                    value = values[i]
                    self.lines[i].append(Point(x=data.timestamp / 1000000, y=value))
            elif isinstance(data, SimpleMessageSchema):
                self.lines[0].append(Point(x=self.index, y=float(data.message)))
            self.index += 1

        for i in range(self.number_of_channels):
            self.data_lines[i].setData(*self.lines[i].to_split_list())

    def change_stream(self, new_stream) -> NoReturn:
        self.stream = new_stream
