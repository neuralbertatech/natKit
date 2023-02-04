from __future__ import annotations

from natKit.client.gui.pyqt6.event import Event

from PyQt6 import QtWidgets
from PyQt6.QtCore import QPoint
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QPainter
from PyQt6.QtGui import QPen
from PyQt6.QtGui import QPolygon

from typing import List
from typing import NoReturn
from typing import Tuple


class FixationCross(QtWidgets.QWidget):
    def __init__(
        self, parent=None, width: int = 100, thickness: int = 10, color: str = "red"
    ) -> NoReturn:
        super(FixationCross, self).__init__(parent)
        self.width = width
        self.thickness = thickness
        self.color = color

    def paintEvent(self, event) -> NoReturn:
        painter = QPainter(self)
        painter.setPen(QPen(QColor(self.color), 8, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(QColor(self.color), Qt.BrushStyle.SolidPattern))

        points = FixationCross.get_points(self.get_center(), self.width, self.thickness)
        qt_points = [QPoint(p[0], p[1]) for p in points]
        poly = QPolygon(qt_points)
        painter.drawPolygon(poly)

    def get_center(self) -> Tuple[int, int]:
        width = self.frameGeometry().width()
        height = self.frameGeometry().height()
        return (width // 2, height // 2)

    # A cross with a cross_width of 15 and a line_thickness of 5. The center
    #   is marked by 'X' and the points start at '0' and end at 'B'
    #
    #    line_thickness
    #       .--^--.
    #       |     |
    #                    -.
    #        2---3        |
    #        |   |        |
    #        |   |        |
    #        |   |        |
    #        |   |        |
    #   0----1   4----5   |
    #   |             |   |
    #   |      X      |   > cross_width
    #   |             |   |
    #   B----A   7----6   |
    #        |   |        |
    #        |   |        |
    #        |   |        |
    #        |   |        |
    #        9---8        |
    #                    -.
    #
    @staticmethod
    def get_points(
        center: Tuple[int, int], cross_width: int, line_thickness: int
    ) -> List[Tuple[int, int]]:
        x = center[0]
        y = center[1]
        hw = cross_width // 2
        ht = line_thickness // 2
        return [
            (x - hw, y - ht),  # 0
            (x - ht, y - ht),  # 1
            (x - ht, y - hw),  # 2
            (x + ht, y - hw),  # 3
            (x + ht, y - ht),  # 4
            (x + hw, y - ht),  # 5
            (x + hw, y + ht),  # 6
            (x + ht, y + ht),  # 7
            (x + ht, y + hw),  # 8
            (x - ht, y + hw),  # 9
            (x - ht, y + ht),  # A
            (x - hw, y + ht),  # B
        ]


class FixationCrossBuilder:
    def __init__(self) -> NoReturn:
        self.width = 100
        self.thickness = 10
        self.color = "red"

    def build(self) -> FixationCross:
        return FixationCross(
            width=self.width, thickness=self.thickness, color=self.color
        )

    def set_width(self, width: int) -> FixationCrossBuilder:
        self.width = width
        return self

    def set_thickness(self, thickness: int) -> FixationCrossBuilder:
        self.thickness = thickness
        return self

    def set_color(self, color: str) -> FixationCrossBuilder:
        self.color = color
        return self


class DrawFixationCrossEvent(Event):
    def __init__(
        self,
        width: int = None,
        thickness: int = None,
        color: str = None,
        debug: bool = False,
    ) -> NoReturn:
        self.fixation_cross_builder = FixationCrossBuilder()
        if width is not None:
            self.fixation_cross_builder.set_width(width)
        if thickness is not None:
            self.fixation_cross_builder.set_thickness(thickness)
        if color is not None:
            self.fixation_cross_builder.set_color(color)
        self.debug = debug

    def start(self, layout) -> NoReturn:
        if self.debug:
            print("Drawing Fixation Cross")

        self.fixation_cross = self.fixation_cross_builder.build()
        layout.addWidget(self.fixation_cross)

    def end(self) -> NoReturn:
        self.fixation_cross.deleteLater()
