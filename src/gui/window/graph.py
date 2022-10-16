import random
import sys

import pyqtgraph as pg

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from fifo import Fifo


class Graph(QWidget):
    def __init__(self, plots=1):
        super().__init__()

        self.graphLabel = QLabel("Graph")
        self.graphWidget = pg.GraphicsLayoutWidget()
        self.__init_setup_plots(plots)

        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.on_tick)
        self.tmp = Fifo(128)

    def __init_setup_plots(self, number_of_plots):
        self.plot_data: [pg.PlotDataItem] = list()
        for i in range(number_of_plots):
            plot = self.graphWidget.addPlot(row=i, col=0)
            plot.showAxis("left", False)
            plot.setMenuEnabled("left", False)
            plot.showAxis("bottom", False)
            self.plot_data.append(plot.plot())

    def get_widgets(self) -> [QWidget]:
        return [self.graphLabel, self, self.graphWidget]

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def on_tick(self):
        self.tmp.push(random.random())
        for data in self.plot_data:
            data.setData(self.tmp.to_list())


class GraphWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("natKit")
        self.graph = Graph()

        layout = QVBoxLayout()
        for widget in self.graph.get_widgets():
            layout.addWidget(widget)

        widget = QWidget()
        widget.setLayout(layout)

        # Set the central widget of the Window. Widget will expand
        # to take up all the space in the window by default.
        self.setCentralWidget(widget)
        self.graph.start()


app = QApplication(sys.argv)
window = GraphWindow()
window.show()

app.exec()
