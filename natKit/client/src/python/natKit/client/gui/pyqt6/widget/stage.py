from __future__ import annotations

from natKit.client.gui.pyqt6.event import DurationEvent
from natKit.client.gui.pyqt6.event import Event
from natKit.client.gui.pyqt6.event import OneShotEvent
from natKit.client.gui.pyqt6.widget import BlockBuilder
from natKit.client.gui.pyqt6.event import Trigger

from PyQt6 import QtCore
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMessageBox

from enum import Enum

from typing import List
from typing import NoReturn


class StageLifecyclePhase(Enum):
    PROMPT = 1
    STAGE_START = 2
    BLOCK_START = 3
    BLOCK_END = 4
    STAGE_END = 5


class Stage(QtWidgets.QWidget):
    def __init__(
        self,
        parent=None,
        name: str = "Stage",
        prompt: str = None,
        trigger: Trigger = None,
        blocks: List[BlockBuilder] = [],
        inter_block_interval: float = 0.0,
        events: List[OneShotEvent] = [],
        duration_events: List[DurationEvent] = [],
    ) -> NoReturn:
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)

        self.name = name
        self.intro_prompt = prompt
        self.trigger = trigger
        self.blocks = [block.build() for block in blocks]
        self.inter_block_interval = inter_block_interval
        self.events = events
        self.duration_events = duration_events
        self.finished = False
        self.stream = None
        self.block_index = 0

    def run(self) -> NoReturn:
        self.prompt()
        self.stage_start()

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(self.inter_block_interval * 1000))
        self.timer.timeout.connect(self.run_block)
        self.timer.start()

    def prompt(self) -> NoReturn:
        self._handle_one_shot_events(StageLifecyclePhase.PROMPT)
        self._handle_duration_events(StageLifecyclePhase.PROMPT)

        if self.intro_prompt is not None:
            prompt_box = QMessageBox()
            prompt_box.setText(self.intro_prompt)
            prompt_box.exec()

    def stage_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(StageLifecyclePhase.STAGE_START)
        self._handle_duration_events(StageLifecyclePhase.STAGE_START)

    def run_block(self) -> NoReturn:
        self.block_start()
        self.blocks(self.blocks_index).run()
        self.trial_end()
        self.block_index += 1
        if self.block_index < len(self.blocks):
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(int(self.inter_block_interval * 1000))
            self.timer.timeout.connect(self.run_block)
            self.timer.start()
        else:
            stage_end()

    def block_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(StageLifecyclePhase.START_BLOCK)
        self._handle_duration_events(StageLifecyclePhase.START_BLOCK)

    def block_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(0)
        self._handle_one_shot_events(StageLifecyclePhase.END_BLOCK)
        self._handle_duration_events(StageLifecyclePhase.END_BLOCK)
        self.finished = True
        self.setParent(None)

    def stage_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(StageLifecyclePhase.STAGE_END)
        self._handle_duration_events(StageLifecyclePhase.STAGE_END)

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


class StageBuilder:
    def __init__(self) -> NoReturn:
        self.name = "Stage"
        self.blocks = []
        self.inter_block_interval = 0.0
        self.prompt = None
        self.trigger = None
        self.events = []
        self.duration_events = []

    def build(self) -> Stage:
        return Stage(
            name=self.name,
            blocks=self.blocks,
            inter_block_interval=self.inter_block_interval,
            prompt=self.prompt,
            trigger=self.trigger,
            events=self.events,
            duration_events=self.duration_events,
        )

    def set_name(self, name: str) -> StageBuilder:
        self.name = name
        return self

    def set_prompt(self, prompt: str) -> StageBuilder:
        self.prompt = prompt
        return self

    def set_trigger(self, trigger: Trigger) -> StageBuilder:
        self.trigger = trigger
        return self

    def add_block(self, block: BlockBuilder, repetitions: int = 1) -> StageBuilder:
        for rep in range(repetitions):
            self.blocks.append(block)
        return self

    def set_inter_block_interval(self, inter_block_interval: float) -> StageBuilder:
        self.inter_block_interval = inter_block_interval
        return self

    def add_event(self, at: StageLifecyclePhase, event: Event) -> StageBuilder:
        self.events.append(OneShotEvent(at=at, event=event))
        return self

    def add_event_for_duration(
        self, start: StageLifecyclePhase, end: StageLifecyclePhase, event: Event
    ) -> StageBuilder:
        self.duration_events.append(DurationEvent(start, end, event))
        return self
