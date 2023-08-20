from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPainter
from PyQt6.QtGui import QPen
from PyQt6.QtGui import QBrush
from PyQt6.QtGui import QColor

from examples.imu_experiment.src.util import ImuConnectionStatus
from examples.imu_experiment.src.util import Point


class StatusDrawingWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scaling_factor = 0.012
        self.imu_connection_positions = [
            Point(20, 25),
            Point(22, 0),
            Point(18, -25),
            Point(-5, -18),
            Point(-28, -25),
            Point(-32, 0),
            Point(-30, 25),
        ]
        self.status_circle_radius = 10

    def paintEvent(self, event):
        qp = QPainter(self)

        scale = min(self.size().width(), self.size().height()) * self.scaling_factor
        convert_scaledPoints = [
            self.convert_cartesian_to_gui(position.scale(scale))
            for position in self.imu_connection_positions
        ]

        for i in range(len(convert_scaledPoints) - 1):
            self.draw_line(qp, convert_scaledPoints[i], convert_scaledPoints[i + 1])

        for i, position in enumerate(convert_scaledPoints):
            self.draw_circle(
                qp,
                position,
                self.status_circle_radius,
                ImuConnectionStatus.get_random_status(),
            )
        qp.end()

    def getCenterPoint(self):
        return Point(self.size().width() / 2, self.size().height() / 2)

    def convert_gui_to_cartesian(self, point: Point):
        width = self.size().width()
        height = self.size().height()
        return Point(point.x - (width / 2), (height / 2) - point.y)

    def convert_cartesian_to_gui(self, point: Point):
        width = self.size().width()
        height = self.size().height()
        return Point(point.x + (width / 2), (height / 2) + point.y)

    def draw_line(self, qp: QPainter, p1: Point, p2: Point):
        qp.setPen(QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine))
        qp.drawLine(int(p1.x), int(p1.y), int(p2.x), int(p2.y))

    def draw_circle(
        self, qp: QPainter, center: Point, radius: float, status: ImuConnectionStatus
    ):
        # qp.setRenderHint(QPainter.renderHints.Antialiasing)
        qp.setPen(QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine))
        brush = QBrush()
        print("status.get_color(): {}".format(status.get_color()))
        brush.setColor(QColor(status.get_color()))
        brush.setStyle(Qt.BrushStyle.Dense1Pattern)
        qp.setBrush(brush)
        qp.drawEllipse(
            int(center.x - radius),
            int(center.y - radius),
            int(radius * 2),
            int(radius * 2),
        )


class ImuConnectionWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout()

        self._title_label = QLabel(
            "Sensor Connection", alignment=Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(self._title_label, 0)

        self._imu_connection_widget_status_drawing = StatusDrawingWidget()
        layout.addWidget(self._imu_connection_widget_status_drawing, 5)

        self.setLayout(layout)

    def sizeHint(self):
        return QSize(150, 120)
