from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt

from .imu_plot_widget import ImuPlotWidget
from .imu_calibration_widget import ImuCalibrationWidget
from .imu_connection_widget import ImuConnectionWidget

from typing import NoReturn


class SetupTaskWidget(QWidget):
    """ """

    def __init__(self, steps=5, *args, **kwargs):
        super(SetupTaskWidget, self).__init__(*args, **kwargs)

        top_layout = QHBoxLayout()

        layout = QVBoxLayout()

        self._title_label = QLabel(
            "IMU Setup Task Window", alignment=Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(self._title_label, 0)

        self._imu_connection_widget = ImuConnectionWidget()
        top_layout.addWidget(self._imu_connection_widget)

        self._imu_calibration_widget = ImuCalibrationWidget()
        top_layout.addWidget(self._imu_calibration_widget)

        layout.addLayout(top_layout, 5)

        self._imu_plot_widget = ImuPlotWidget()
        layout.addWidget(self._imu_plot_widget, 5)

        self._next_task_button = QPushButton("")

        self.setLayout(layout)


class SetupTaskWidgetBuilder:
    def __init__(self) -> NoReturn:
        pass

    def build(self) -> SetupTaskWidget:
        return SetupTaskWidget()
