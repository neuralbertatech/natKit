#!/usr/bin/env python

import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "..",".."))

from enum import Enum
from dataclasses import dataclass
from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from random import randint
from time import sleep 
from typing import NoReturn

# imu_selector_num = 7
imu_selector_labels = ["IMU 1 (Left Wrist)","IMU 2 (Left Elbow)","IMU 3 (Left Shoulder)","IMU 4 (Trunk)","IMU 5 (Right Shoulder)","IMU 6 (Right Elbow)","IMU 7 (Right Wrist)"]

@dataclass
class _Point:
    x: float = 0.0
    y: float = 0.0
    
    def scale(self, scaling_factor: float):
        return _Point(self.x * scaling_factor, self.y * scaling_factor)
    
    
class _ImuConnectionStatus(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    
    def get_color(self):        
        if self == _ImuConnectionStatus.DISCONNECTED:
            return "#FF0000"
        elif self == _ImuConnectionStatus.CONNECTING:
            return "#FFFF00"
        elif self == _ImuConnectionStatus.CONNECTED:
            return "#00FF00"
        
    @staticmethod
    def get_random_status():
        random_status = randint(0, 2)
        if random_status == 0:
            return _ImuConnectionStatus.DISCONNECTED
        elif random_status == 1:
            return _ImuConnectionStatus.CONNECTING
        elif random_status == 2:
            return _ImuConnectionStatus.CONNECTED
        
        
class _ImuConnectionWidgetStatusDrawing(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scaling_factor = 0.012
        self.imu_connection_positions = [
            _Point(20,25),
            _Point(22,0),
            _Point(18,-25),
            _Point(-5, -18),
            _Point(-28,-25),
            _Point(-32,0),
            _Point(-30,25),
            ]
        self.status_circle_radius = 10 
            
    def paintEvent(self, event):
        qp = QPainter(self)
        
        scale = min(self.size().width(), self.size().height()) * self.scaling_factor
        convert_scaled_points = [self.convert_cartesian_to_gui(position.scale(scale)) for position in self.imu_connection_positions]     
        
        for i in range(len(convert_scaled_points) - 1): 
             self.draw_line(qp, convert_scaled_points[i], convert_scaled_points[i + 1])
             
        for i, position in enumerate(convert_scaled_points): 
             self.draw_circle(qp, position, self.status_circle_radius, _ImuConnectionStatus.get_random_status())
        qp.end()
        
    def getCenterPoint(self):
        return _Point(self.size().width()/2, self.size().height()/2)
    
    def convert_gui_to_cartesian(self, point: _Point):
        width = self.size().width()
        height = self.size().height()
        return _Point(point.x - (width/2), (height/2) - point.y)
        
    def convert_cartesian_to_gui(self, point: _Point):
        width = self.size().width()
        height = self.size().height()
        return _Point(point.x + (width/2), (height/2) + point.y)
       
    def draw_line(self, qp: QPainter, p1: _Point, p2: _Point ):
        qp.setPen(QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine))
        qp.drawLine(int(p1.x), int(p1.y), int(p2.x), int(p2.y))
        
    def draw_circle(self, qp: QPainter, center: _Point, radius: float, status: _ImuConnectionStatus):
        # qp.setRenderHint(QPainter.renderHints.Antialiasing)
        qp.setPen(QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine))
        brush = QBrush()
        print("status.get_color(): {}".format(status.get_color()))
        brush.setColor(QColor(status.get_color()))
        brush.setStyle(Qt.BrushStyle.Dense1Pattern)
        qp.setBrush(brush)
        qp.drawEllipse(int(center.x - radius), int(center.y - radius), int(radius*2), int(radius*2))


class _ImuConnectionWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QtWidgets.QVBoxLayout()
        
        self._title_label = QtWidgets.QLabel("Sensor Connection", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label, 0)
                        
        self._imu_connection_widget_status_drawing = _ImuConnectionWidgetStatusDrawing()
        layout.addWidget(self._imu_connection_widget_status_drawing, 5)
        
        self.setLayout(layout)

    def sizeHint(self):
        return QtCore.QSize(150,120)


class _ImuCalibrationStatus(Enum):
    UNKNOWN = 0
    UNRELIABLE = 1
    ACCURACY_LOW = 2
    ACCURACY_MEDIUM = 3
    ACCURACY_HIGH = 4
        
    @staticmethod
    def get_random_status():
        random_status = randint(0, 4)
        if random_status == 0:
            return _ImuCalibrationStatus.UNKNOWN
        elif random_status == 1:
            return _ImuCalibrationStatus.UNRELIABLE
        elif random_status == 2:
            return _ImuCalibrationStatus.ACCURACY_LOW
        elif random_status == 3:
            return _ImuCalibrationStatus.ACCURACY_MEDIUM
        elif random_status == 4:
            return _ImuCalibrationStatus.ACCURACY_HIGH
    
    def to_string(self):
        if self == _ImuCalibrationStatus.UNKNOWN:
            return "UNKNOWN"
        elif self == _ImuCalibrationStatus.UNRELIABLE:
            return "UNRELIABLE"
        elif self == _ImuCalibrationStatus.ACCURACY_LOW:
            return "ACCURACY_LOW"
        elif self == _ImuCalibrationStatus.ACCURACY_MEDIUM:
            return "ACCURACY_MEDIUM"
        elif self == _ImuCalibrationStatus.ACCURACY_HIGH:
            return "ACCURACY_HIGH"
        

class _ImuCalibrationWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QtWidgets.QGridLayout() # Y Rows, X Columns
        
        for i, imu in enumerate(imu_selector_labels):  

            self._title_label = QtWidgets.QLabel(imu)
            layout.addWidget(self._title_label,i,0)
        
            self._calibration_label = QtWidgets.QLabel(str(_ImuCalibrationStatus.get_random_status().to_string())) # lots of things
            layout.addWidget(self._calibration_label,i,2)
            
        self.setLayout(layout)


    def sizeHint(self):
        return QtCore.QSize(40,120)
    
    
class _ImuPlotWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QtWidgets.QGridLayout() # Y Rows, X Columns
        
        self.setLayout(layout)


    def sizeHint(self):
        return QtCore.QSize(40,120)
    
    
class SetupTaskWidget(QtWidgets.QWidget):
    """

    """

    def __init__(self, steps=5, *args, **kwargs):
        super(SetupTaskWidget, self).__init__(*args, **kwargs)

        top_layout = QtWidgets.QHBoxLayout()

        layout = QtWidgets.QVBoxLayout()
        
        self._title_label = QtWidgets.QLabel("IMU Setup Task Window", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label, 0)
        
        self._imu_connection_widget = _ImuConnectionWidget()
        top_layout.addWidget(self._imu_connection_widget)

        self._imu_calibration_widget = _ImuCalibrationWidget()
        top_layout.addWidget(self._imu_calibration_widget)
        
        layout.addLayout(top_layout, 5)
        
        self._imu_plot_widget = _ImuPlotWidget()
        layout.addWidget(self._imu_plot_widget, 5)
        
        self._next_task_button = QtWidgets.QPushButton("")

        self.setLayout(layout)

class SetupTaskWidgetBuilder():
    def __init__(self) -> NoReturn:
        pass

    def build(self) -> SetupTaskWidget:
        return SetupTaskWidget(

        )

def main() -> NoReturn:
    
    builder = (
        SetupTaskWidgetBuilder()
    )

    build_and_launch_window_single_process(builder)

if __name__ == "__main__":
    main()
