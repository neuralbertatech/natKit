from PyQt5 import QtWidgets
from src.gui.window.window import Window
from src.gui.widget.graph_widget import GraphWidget
from src.stream.data_stream import DataStream
from src.utility.fifo import Fifo
from time import sleep

import sys


app = QtWidgets.QApplication(sys.argv)
graph = GraphWidget(DataStream(Fifo(128)), 5)
window = Window(graph)
window.start_widgets()
app.exit(app.exec_())

sleep(30)
