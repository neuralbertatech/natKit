from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtCore import QSize


class ImuPlotWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QGridLayout()  # Y Rows, X Columns

        self.setLayout(layout)

    def sizeHint(self):
        return QSize(40, 120)
