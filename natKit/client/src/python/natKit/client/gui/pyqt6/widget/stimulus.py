from __future__ import annotations

from natKit.client.gui.pyqt6.event import DurationEvent
from natKit.client.gui.pyqt6.event import Event
from natKit.client.gui.pyqt6.event import OneShotEvent
from natKit.client.gui.pyqt6.event import Trigger
from natKit.common.kafka import TopicManager

from PyQt6 import QtCore
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMessageBox

from enum import Enum

from typing import List
from typing import NoReturn


class StimulusLifecyclePhase(Enum):
    PROMPT = 1
    START = 2
    END = 3


class Stimulus(QtWidgets.QWidget):
    def __init__(
        self,
        parent=None,
        name: str = "Stimulus",
        trigger: Trigger = None,
        duration: float = None,
        prompt: str = None,
        events: List[OneShotEvent] = [],
        duration_events: List[DurationEvent] = [],
    ) -> NoReturn:
        super(Stimulus, self).__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)

        self.name = name
        self.trigger = trigger
        self.intro_prompt = prompt
        self.events = events
        self.duration_events = duration_events
        self.finished = False
        self.topic_manager = TopicManager()
        self.stream = None

        if duration is None:
            duration = 0.0
        self.duration = duration

    def run(self) -> NoReturn:
        self.prompt()
        self.start()

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(self.duration * 1000))
        self.timer.timeout.connect(self.end)
        self.timer.start()

    def prompt(self) -> NoReturn:
        self._handle_one_shot_events(StimulusLifecyclePhase.PROMPT)
        self._handle_duration_events(StimulusLifecyclePhase.PROMPT)

        if self.intro_prompt is not None:
            prompt_box = QMessageBox()
            prompt_box.setText(self.intro_prompt)
            prompt_box.exec()

    def start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(StimulusLifecyclePhase.START)
        self._handle_duration_events(StimulusLifecyclePhase.START)

    def end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(0)
        self._handle_one_shot_events(StimulusLifecyclePhase.END)
        self._handle_duration_events(StimulusLifecyclePhase.END)
        self.finished = True
        self.setParent(None)

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


class StimulusBuilder:
    def __init__(self) -> NoReturn:
        self.name = "Stimulus"
        self.trigger = None
        self.duration = None
        self.prompt = None
        self.events = []
        self.duration_events = []

    def build(self) -> Stimulus:
        return Stimulus(
            name=self.name,
            trigger=self.trigger,
            duration=self.duration,
            prompt=self.prompt,
            events=self.events,
            duration_events=self.duration_events,
        )

    def set_name(self, name: str) -> StimulusBuilder:
        self.name = name
        return self

    def set_trigger(self, trigger: Trigger) -> StimulusBuilder:
        self.trigger = trigger
        return self

    def set_duration(self, seconds: float) -> StimulusBuilder:
        self.duration = seconds
        return self

    def set_prompt(self, prompt: str) -> StimulusBuilder:
        self.prompt = prompt
        return self

    def add_event(self, at: StimulusLifecyclePhase, event: Event) -> StimulusBuilder:
        self.events.append(OneShotEvent(at=at, event=event))
        return self

    def add_event_for_duration(
        self, start: StimulusLifecyclePhase, end: StimulusLifecyclePhase, event: Event
    ) -> StimulusBuilder:
        self.duration_events.append(DurationEvent(start, end, event))
        return self
