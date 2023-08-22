from __future__ import annotations

from natKit.client.gui.pyqt6 import Experiment

from PyQt6 import QtCore
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from random import shuffle

from typing import List
from typing import NoReturn
from typing import Tuple


class ExperimentWindow(QMainWindow):
    def __init__(
        self,
        parent=None,
        window_size: Tuple[int, int] = None,
        experiment: Experiment = None,
    ) -> NoReturn:
        super().__init__(parent)
        self.layout = QVBoxLayout()
        self.container = QWidget()
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        self.experiment = experiment

        # self.training_stimuli = training_stimuli
        self.current_training_stimuli = None
        self.current_training_stimuli_index = 0
        self.finished_training = False
        # self.trial_prompt = trial_prompt
        self.current_trial_stimuli = None
        self.current_trial = 0
        self.current_block = 0
        self.finished_trial = False
        self.state = "train"

        # self.triggers = triggers

        if window_size is not None:
            self.setFixedWidth(window_size[0])
            self.setFixedHeight(window_size[1])

        # if intro_prompt is not None:
        #     prompt = QMessageBox()
        #     prompt.setText(intro_prompt)
        #     prompt.exec()

        # self.inter_trial_timer = QtCore.QTimer()
        # self.inter_trial_timer.setInterval(int(self.inter_trial_interval * 1000))
        # self.inter_trial_timer.setSingleShot(True)
        # self.inter_trial_timer.timeout.connect(self._next_trial)
        #
        # self.inter_block_timer = QtCore.QTimer()
        # self.inter_block_timer.setInterval(int(self.inter_block_interval * 1000))
        # self.inter_block_timer.setSingleShot(True)
        # self.inter_block_timer.timeout.connect(self._next_block)
        #
        # self.timer = QtCore.QTimer()
        # self.timer.setInterval(5)
        # self.timer.timeout.connect(self.on_update)
        # self.timer.start()


class ExperimentWindowBuilder:
    def __init__(self) -> NoReturn:
        self.window_size = None
        self.experiment = None

    def build(self) -> ExperimentWindow:
        return ExperimentWindow(
            window_size=self.window_size, experiment=self.experiment
        )

    def set_window_size(
        self,
        as_absolute_value: Tuple[int, int] = None,
        as_percent_of_current_screen: Tuple[float, float] = None,
    ) -> ExperimentWindowBuilder:
        if as_absolute_value is not None:
            self.window_size = as_absolute_value
        elif as_percent_of_current_screen is not None:
            assert False, "as_percent_of_current_screen is not implemented yet"
        else:
            assert False, "Error: No arguments passed to set_size()"
        return self

    def set_experiment(self, experiment: Experiment) -> ExperimentWindowBuilder:
        self.experiment = experiment
        return self
