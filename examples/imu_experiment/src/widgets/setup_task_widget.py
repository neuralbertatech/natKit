from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal

from natKit.client.gui.pyqt6.widget import Task, TaskBuilder, ExperimentBuilder
from natKit.client.gui.pyqt6.window import ExperimentWindow

from .imu_plot_widget import ImuPlotWidget
from .imu_connection_widget import ImuConnectionWidget
from .imu_calibration_widget import ImuCalibrationWidget

from ..util import ImuStreams

from typing import NoReturn


class SetupTaskWidget(Task):
    """ """

    onNext = pyqtSignal()
    onPrev = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imu_streams = ImuStreams()

    def set_imu_streams(self, imu_streams) -> NoReturn:
        self.imu_streams = imu_streams

    def setup(self):
        top_layout = QHBoxLayout()

        button_layout = QHBoxLayout()

        self.layout = QVBoxLayout()

        self._title_label = QLabel(
            "IMU Setup Task Window", alignment=Qt.AlignmentFlag.AlignCenter
        )
        self.layout.addWidget(self._title_label, 0)

        self._imu_connection_widget = ImuConnectionWidget(self.imu_streams)
        top_layout.addWidget(self._imu_connection_widget)

        self._imu_calibration_widget = ImuCalibrationWidget(self.imu_streams)
        top_layout.addWidget(self._imu_calibration_widget)

        self.layout.addLayout(top_layout, 5)

        self._imu_plot_widget = ImuPlotWidget(self.imu_streams)
        self.layout.addWidget(self._imu_plot_widget, 5)

        self._previous_task_button = QPushButton(text="<- Change IMU Associations")
        self._previous_task_button.clicked.connect(lambda: self.onPrev.emit())
        button_layout.addWidget(
            self._previous_task_button, alignment=Qt.AlignmentFlag.AlignLeft
        )

        self._next_task_button = QPushButton(text="Data Collection ->")
        self._next_task_button.clicked.connect(lambda: self.onNext.emit())
        button_layout.addWidget(
            self._next_task_button, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.layout.addLayout(button_layout, 0)

        self.setLayout(self.layout)


class SetupTaskWidgetBuilder(TaskBuilder):
    def __init__(self) -> NoReturn:
        super().__init__()

    def build(self) -> Task:
        return SetupTaskWidget(
            name=self.name,
            stages=self.stages,
            inter_stage_interval=self.inter_stage_interval,
            prompt=self.prompt,
            trigger=self.trigger,
            events=self.events,
            duration_events=self.duration_events,
        )
