from __future__ import annotations

from natKit.client.gui.pyqt6 import Stimulus
from natKit.client.gui.pyqt6 import Trigger

from PyQt6 import QtCore
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from random import shuffle

from typing import List
from typing import NoReturn
from typing import Tuple


class MultiStageTaskWindow(QMainWindow):
    def __init__(
        self,
        parent=None,
        window_size: Tuple[int, int] = None,
        intro_prompt: str = None,
        trial_prompt: str = None,
        training_stimuli: [] = [],
        trial_stimuli: [] = [],
        triggers: [] = [],
        number_of_trials: int = None,
        number_of_blocks: int = None,
        inter_trial_interval: float = None,
        inter_block_interval: float = None,
        inter_stage_interval: float = None,

    ) -> NoReturn:
        super(MultiStageTaskWindow, self).__init__(parent)
        self.layout = QVBoxLayout()
        self.container = QWidget()
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        self.trial_stimuli = trial_stimuli
        self.inter_trial_interval = inter_trial_interval
        self.inter_block_interval = inter_block_interval
        stimulus_for_trial = []
        for i in range(number_of_trials):
            stimulus_for_trial.append(trial_stimuli[i % len(trial_stimuli)])

        self.trial_blocks = []
        for _ in range(number_of_blocks):
            shuffle(stimulus_for_trial)
            self.trial_blocks.append(stimulus_for_trial)

        self.training_stimuli = training_stimuli
        self.current_training_stimuli = None
        self.current_training_stimuli_index = 0
        self.finished_training = False
        self.trial_prompt = trial_prompt
        self.current_trial_stimuli = None
        self.current_trial = 0
        self.current_block = 0
        self.finished_trial = False
        self.state = "train"

        self.triggers = triggers

        if window_size is not None:
            self.setFixedWidth(window_size[0])
            self.setFixedHeight(window_size[1])

        if intro_prompt is not None:
            prompt = QMessageBox()
            prompt.setText(intro_prompt)
            prompt.exec()

        self.inter_trial_timer = QtCore.QTimer()
        self.inter_trial_timer.setInterval(int(self.inter_trial_interval * 1000))
        self.inter_trial_timer.setSingleShot(True)
        self.inter_trial_timer.timeout.connect(self._next_trial)

        self.inter_block_timer = QtCore.QTimer()
        self.inter_block_timer.setInterval(int(self.inter_block_interval * 1000))
        self.inter_block_timer.setSingleShot(True)
        self.inter_block_timer.timeout.connect(self._next_block)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(5)
        self.timer.timeout.connect(self.on_update)
        self.timer.start()

    def on_update(self) -> NoReturn:
        self.write_triggers()
        if self.state == "done":
            return
        elif self.state == "train":
            self.on_update_train()
        elif self.state == "trial":
            self.on_update_trial()

    def on_update_train(self) -> NoReturn:
        if (
            self.current_training_stimuli is None
            or self.current_training_stimuli.finished
        ):
            if self.current_training_stimuli_index == len(self.training_stimuli):
                self.finished_training = True
                self.start_trial()
                return

            self.current_training_stimuli = self.training_stimuli[
                self.current_training_stimuli_index
            ].build()
            self.current_training_stimuli_index += 1
            self.layout.addWidget(self.current_training_stimuli)
            self.current_training_stimuli.run()

    def start_trial(self) -> NoReturn:
        self.state = "trial"

        if self.trial_prompt is not None:
            prompt = QMessageBox()
            prompt.setText(self.trial_prompt)
            prompt.exec()

    def _next_trial(self) -> NoReturn:
        self.current_trial += 1
        self.current_trial_stimuli = None

    def _next_block(self) -> NoReturn:
        self.current_trial = 0
        self.current_block += 1

    def on_update_inter_trial(self) -> NoReturn:
        if not self.inter_trial_timer.isActive():
            self.inter_trial_timer.start()

    def on_update_inter_block(self) -> NoReturn:
        # Probably has a race condition between self.inter_block_timer and self.timer
        if not self.inter_block_timer.isActive():
            self.inter_block_timer.start()

    def on_update_trial(self) -> NoReturn:
        if self.current_block < len(self.trial_blocks):
            if self.current_trial < len(self.trial_blocks[self.current_block]):
                if self.current_trial_stimuli is None:
                    self.current_trial_stimuli = self.trial_blocks[self.current_block][
                        self.current_trial
                    ].build()
                    self.layout.addWidget(self.current_trial_stimuli)
                    self.current_trial_stimuli.run()
                elif self.current_trial_stimuli.finished:
                    self.on_update_inter_trial()
            else:
                if self.current_block < len(self.trial_blocks):
                    self.on_update_inter_block()
        else:
            self.finished_trial = True
            self.state = "done"

    def write_triggers(self) -> NoReturn:
        for trigger in self.triggers:
            trigger.write()


class MultiStageTaskWindowBuilder:
    def __init__(self) -> NoReturn:
        self.window_size = None
        self.intro_prompt = None
        self.trial_prompt = None
        self.training_stimuli = []
        self.trial_stimuli = []
        self.triggers = []
        self.number_of_trials = 0
        self.number_of_blocks = 1
        self.inter_trial_interval = 1
        self.inter_block_interval = 1

    def build(self) -> MultiStageTaskWindow:
        return MultiStageTaskWindow(
            window_size=self.window_size,
            intro_prompt=self.intro_prompt,
            trial_prompt=self.trial_prompt,
            training_stimuli=self.training_stimuli,
            trial_stimuli=self.trial_stimuli,
            triggers=self.triggers,
            number_of_trials=self.number_of_trials,
            number_of_blocks=self.number_of_blocks,
            inter_trial_interval=self.inter_trial_interval,
            inter_block_interval=self.inter_block_interval,
        )

    def set_window_size(
        self,
        as_absolute_value: Tuple[int, int] = None,
        as_percent_of_current_screen: Tuple[float, float] = None,
    ) -> MultiStageTaskWindowBuilder:
        if as_absolute_value is not None:
            self.window_size = as_absolute_value
        elif as_percent_of_current_screen is not None:
            assert False, "as_percent_of_current_screen is not implemented yet"
        else:
            assert False, "Error: No arguments passed to set_size()"
        return self

    def set_intro_prompt(self, prompt: str) -> MultiStageTaskWindowBuilder:
        self.intro_prompt = prompt
        return self

    def set_trial_prompt(self, prompt: str) -> MultiStageTaskWindowBuilder:
        self.trial_prompt = prompt
        return self

    def set_training_stimulus(self, stimuli: List[Stimulus]) -> MultiStageTaskWindowBuilder:
        self.training_stimuli = stimuli
        return self

    def set_trial_stimulus(self, stimuli: List[Stimulus]) -> MultiStageTaskWindowBuilder:
        self.trial_stimuli = stimuli
        return self

    def set_triggers(self, triggers: List[Trigger]) -> MultiStageTaskWindowBuilder:
        self.triggers = triggers
        return self

    def set_number_of_trials(self, trials: int) -> MultiStageTaskWindowBuilder:
        self.number_of_trials = trials
        return self

    def set_number_of_blocks(self, blocks: int) -> MultiStageTaskWindowBuilder:
        self.number_of_blocks = blocks
        return self

    def set_inter_trial_interval(self, interval: float) -> MultiStageTaskWindowBuilder:
        self.inter_trial_interval = interval
        return self

    def set_inter_block_interval(self, interval: float) -> MultiStageTaskWindowBuilder:
        self.inter_block_interval = interval
        return self

    def set_inter_stage_interval(self, interval: float) -> MultiStageTaskWindowBuilder:
        self.inter_stage_interval = interval
        return self
