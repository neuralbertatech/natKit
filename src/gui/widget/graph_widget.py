import random

import pyqtgraph as pg

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout
from src.gui.widget.widget import Widget
from src.stream.stream import Stream
from src.utility.fifo import Fifo


class GraphWidget(Widget):
    def __init__(self, stream: Stream, plots=1):
        super().__init__()

        self.stream = stream
        self.data_buffer = Fifo(128)
        self.data_buffer.push(1)
        self.graphLabel = QLabel("Graph")
        self.graphWidget = pg.GraphicsLayoutWidget()
        self.__init_setup_plots(plots)

        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.on_tick)

    def __init_setup_plots(self, number_of_plots):
        self.plot_data: [pg.PlotDataItem] = list()
        for i in range(number_of_plots):
            plot = self.graphWidget.addPlot(row=i, col=0)
            plot.showAxis("left", False)
            plot.setMenuEnabled("left", False)
            plot.showAxis("bottom", False)
            self.plot_data.append(plot.plot())

    def get_layout(self):
        print("Setup Layout")
        widgets = [self.graphLabel, self.graphWidget]
        layout = QVBoxLayout()
        for widget in widgets:
            print("Adding widget")
            layout.addWidget(widget)
        print("Finished Setup Layout")
        return layout

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def on_tick(self):
        # self.stream.write(int(random.random() * 100))  # TODO: Delete me
        data = self.stream.read()
        if data is not None:
            self.data_buffer.push(data)
        for data in self.plot_data:
            data_list = self.data_buffer.to_list()
            print(data_list)
            data.setData(data_list)
