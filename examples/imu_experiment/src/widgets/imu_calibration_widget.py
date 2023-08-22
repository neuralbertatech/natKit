from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QSize

from examples.imu_experiment.src.util import ImuCalibrationStatus

from ..util import ImuStreams

imu_selector_labels = [
    "IMU 1 (Left Wrist)",
    "IMU 2 (Left Elbow)",
    "IMU 3 (Left Shoulder)",
    "IMU 4 (Trunk)",
    "IMU 5 (Right Shoulder)",
    "IMU 6 (Right Elbow)",
    "IMU 7 (Right Wrist)",
]


class ImuCalibrationWidget(QWidget):
    def __init__(self, imu_streams: ImuStreams, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imu_streams = imu_streams

        layout = QGridLayout()  # Y Rows, X Columns

        for i, imu in enumerate(imu_selector_labels):
            self._title_label = QLabel(imu)
            layout.addWidget(self._title_label, i, 0)

            self._calibration_label = QLabel(
                ImuStreams.get_calibration_status(
                    self.imu_streams.get_at_index(i)
                ).to_string()
            )  # lots of things
            layout.addWidget(self._calibration_label, i, 2)

        self.setLayout(layout)

    def sizeHint(self):
        return QSize(40, 120)
