#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "..",".."))

from natKit.client.gui.pyqt6.window.window_launcher import (
    build_and_launch_window_single_process,
)

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from time import sleep 
from typing import NoReturn

# imu_selector_num = 7
imu_selector_labels = ["IMU 1 (Left Wrist)","IMU 2 (Left Elbow)","IMU 3 (Left Shoulder)","IMU 4 (Trunk)","IMU 5 (Right Shoulder)","IMU 6 (Right Elbow)","IMU 7 (Right Wrist)"]


class _ImuSelectorsWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        layout = QtWidgets.QGridLayout() # Y Rows, X Columns
        
        for i, imu in enumerate(imu_selector_labels):  

            self._title_label = QtWidgets.QLabel(imu)
            layout.addWidget(self._title_label,i,0)
        
            self._drop_down = QtWidgets.QComboBox() # lots of things
            layout.addWidget(self._drop_down,i,2)
            
        self.setLayout(layout)


    def sizeHint(self):
        return QtCore.QSize(40,120)
    
    
class QueryTaskWidget(QtWidgets.QWidget):
    """

    """

    def __init__(self, steps=5, *args, **kwargs):
        super(QueryTaskWidget, self).__init__(*args, **kwargs)

        layout = QtWidgets.QVBoxLayout()
        
        self._title_label = QtWidgets.QLabel("IMU Query Task Window", alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)
        
        self._imu_selectors_wdiget = _ImuSelectorsWidget()
        layout.addWidget(self._imu_selectors_wdiget)
        
        self._next_task_button = QtWidgets.QPushButton("")

        self.setLayout(layout)

class QueryTaskWidgetBuilder():
    def __init__(self) -> NoReturn:
        pass

    def build(self) -> QueryTaskWidget:
        return QueryTaskWidget(

        )

def main() -> NoReturn:
    
    builder = (
        QueryTaskWidgetBuilder()
    )

    build_and_launch_window_single_process(builder)

if __name__ == "__main__":
    main()
