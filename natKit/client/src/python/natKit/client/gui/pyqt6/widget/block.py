from __future__ import annotations

from natKit.client.gui.pyqt6.event import DurationEvent
from natKit.client.gui.pyqt6.event import Event
from natKit.client.gui.pyqt6.event import OneShotEvent
from natKit.client.gui.pyqt6.widget import Stimulus

from PyQt6 import QtCore
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMessageBox

from enum import Enum

from typing import List
from typing import NoReturn


class BlockLifecyclePhase(Enum):
    PROMPT = 1
    BLOCK_START = 2
    TRIAL_START = 3
    TRIAL_END = 4
    BLOCK_END = 5


class Block(QtWidgets.QWidget):
    def __init__(
        self,
        parent=None,
        name: str = "Block",
        prompt: str = None,
        stimuli: List[Stimulus] = [],
        inter_trial_interval: float = 0.0,
        events: List[OneShotEvent] = [],
        duration_events: List[DurationEvent] = [],
    ) -> NoReturn:
        super(Block, self).__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)

        self.name = name
        self.intro_prompt = prompt
        self.stimuli = stimuli
        self.inter_trial_interval = inter_trial_interval
        self.events = events
        self.duration_events = duration_events
        self.finished = False
        self.stream = None
        self.stimuli_index = 0

    def run(self) -> NoReturn:
        self.prompt()
        self.block_start()
        
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(self.inter_trial_interval * 1000))
        self.timer.timeout.connect(self.run_stimulus)
        self.timer.start()
        

    def prompt(self) -> NoReturn:
        self._handle_one_shot_events(BlockLifecyclePhase.PROMPT)
        self._handle_duration_events(BlockLifecyclePhase.PROMPT)

        if self.intro_prompt is not None:
            prompt_box = QMessageBox()
            prompt_box.setText(self.intro_prompt)
            prompt_box.exec()
     
    def block_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(BlockLifecyclePhase.BLOCK_START)
        self._handle_duration_events(BlockLifecyclePhase.BLOCK_START)
            
    def run_stimulus(self) -> NoReturn:
        self.trial_start()
        self.stimuli(self.stimuli_index).run()
        self.trial_end()
        self.stimuli_index += 1
        if self.stimuli_index < len(self.stimuli):
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(int(self.inter_trial_interval * 1000))
            self.timer.timeout.connect(self.run_stimulus)
            self.timer.start()
        else: 
            block_end()
        
    def trial_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(BlockLifecyclePhase.START_TRIAL)
        self._handle_duration_events(BlockLifecyclePhase.START_TRIAL)

    def trial_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(0)
        self._handle_one_shot_events(BlockLifecyclePhase.TRIAL_END)
        self._handle_duration_events(BlockLifecyclePhase.TRIAL_END)
        self.finished = True
        self.setParent(None)
        
    def block_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(BlockLifecyclePhase.BLOCK_END)
        self._handle_duration_events(BlockLifecyclePhase.BLOCK_END)

    def _handle_one_shot_events(self, lifecycle_phase) -> NoReturn:
        for event in self.events:
            if event.at == lifecycle_phase:
                event.event.start(self.layout)

    def _handle_duration_events(self, lifecycle_phase) -> NoReturn:
        for event in self.duration_events:
            if event.start == lifecycle_phase:
                event.event.start(self.layout)
            if event.end == lifecycle_phase:
                event.event.end()
                

class BlockBuilder:
    def __init__(self) -> NoReturn:
        self.name = "Block"
        self.stimuli = []
        inter_trial_interval = 0.0
        self.prompt = None
        self.events = []
        self.duration_events = []

    def build(self) -> Block:
        return Block(
            name=self.name,
            stimuli=self.stimuli,
            inter_trial_interval=self.inter_trial_interval,
            prompt=self.prompt,
            events=self.events,
            duration_events=self.duration_events,
        )

    def set_name(self, name: str) -> BlockBuilder:
        self.name = name
        return self

    def set_prompt(self, prompt: str) -> BlockBuilder:
        self.prompt = prompt
        return self
    
    def add_stimulus(self, stimulus: Stimulus, repetitions: int = 1) -> BlockBuilder:
        for rep in range(repetitions):
            self.stimuli.append(stimulus)
        return self
    
    def set_inter_trial_interval(self, inter_trial_interval: float) -> BlockBuilder:
        self.inter_trial_interval = inter_trial_interval
        return self
    
    def add_event(self, at: BlockLifecyclePhase, event: Event) -> BlockBuilder:
        self.events.append(OneShotEvent(at=at, event=event))
        return self

    def add_event_for_duration(
        self, start: BlockLifecyclePhase, end: BlockLifecyclePhase, event: Event
    ) -> BlockBuilder:
        self.duration_events.append(DurationEvent(start, end, event))
        return self
