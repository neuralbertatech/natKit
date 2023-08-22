from __future__ import annotations

from natKit.client.gui.pyqt6.event import DurationEvent
from natKit.client.gui.pyqt6.event import Event
from natKit.client.gui.pyqt6.event import OneShotEvent
from natKit.client.gui.pyqt6.widget import StageBuilder
from natKit.client.gui.pyqt6.event import Trigger

from PyQt6 import QtCore
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QMessageBox

from enum import Enum

from typing import List
from typing import NoReturn


class TaskLifecyclePhase(Enum):
    PROMPT = 1
    TASK_START = 2
    STAGE_START = 3
    STAGE_END = 4
    TASK_END = 5


class Task(QWidget):
    # If constructed with a TaskBuilder then only the data set in the builder with be used
    def __init__(
        self,
        parent=None,
        name: str = "Task",
        prompt: str = None,
        trigger: Trigger = None,
        stages: List[StageBuilder] = [],
        inter_stage_interval: float = 0.0,
        events: List[OneShotEvent] = [],
        duration_events: List[DurationEvent] = [],
        builder: TaskBuilder = None,
    ) -> NoReturn:
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()

        # if builder is not None:
        #     print("Constructed a task with a builder")
        #     self.name = builder.name
        #     self.intro_prompt = builder.prompt
        #     self.trigger = builder.trigger
        #     self.stages = builder.stages
        #     self.inter_stage_interval = builder.inter_stage_interval
        #     self.events = builder.events
        #     self.duration_events = builder.duration_events
        # else:
        self.name = name
        self.intro_prompt = prompt
        self.trigger = trigger
        self.stages = [stage.build() for stage in stages]
        self.inter_stage_interval = inter_stage_interval
        self.events = events
        self.duration_events = duration_events

        self.finished = False
        self.stream = None
        self.stage_index = 0

    def run(self) -> NoReturn:
        self.prompt()
        self.task_start()

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(self.inter_stage_interval * 1000))
        self.timer.timeout.connect(self.run_stage)
        self.timer.start()

    def prompt(self) -> NoReturn:
        self._handle_one_shot_events(TaskLifecyclePhase.PROMPT)
        self._handle_duration_events(TaskLifecyclePhase.PROMPT)

        if self.intro_prompt is not None:
            prompt_box = QMessageBox()
            prompt_box.setText(self.intro_prompt)
            prompt_box.exec()

    def task_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(TaskLifecyclePhase.TASK_START)
        self._handle_duration_events(TaskLifecyclePhase.TASK_START)

    def run_stage(self) -> NoReturn:
        self.stage_start()
        self.stages(self.stage_index).run()
        self.stage_end()
        self.stage_index += 1
        if self.stage_index < len(self.stages):
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(int(self.inter_stage_interval * 1000))
            self.timer.timeout.connect(self.run_stage)
            self.timer.start()
        else:
            task_end()

    def stage_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(TaskLifecyclePhase.STAGE_START)
        self._handle_duration_events(TaskLifecyclePhase.STAGE_START)

    def stage_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(0)
        self._handle_one_shot_events(TaskLifecyclePhase.STAGE_END)
        self._handle_duration_events(TaskLifecyclePhase.STAGE_END)
        self.finished = True
        self.setParent(None)

    def task_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(TaskLifecyclePhase.TASK_END)
        self._handle_duration_events(TaskLifecyclePhase.TASK_END)

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


class TaskBuilder:
    def __init__(self) -> NoReturn:
        self.name = "Task"
        self.stages = []
        self.inter_stage_interval = 0.0
        self.prompt = None
        self.trigger = None
        self.events = []
        self.duration_events = []

    def build(self) -> Task:
        return Task(
            name=self.name,
            stages=self.stages,
            inter_stage_interval=self.inter_stage_interval,
            prompt=self.prompt,
            trigger=self.trigger,
            events=self.events,
            duration_events=self.duration_events,
        )

    def set_name(self, name: str) -> TaskBuilder:
        self.name = name
        return self

    def set_prompt(self, prompt: str) -> TaskBuilder:
        self.prompt = prompt
        return self

    def set_trigger(self, trigger: Trigger) -> TaskBuilder:
        self.trigger = trigger
        return self

    def add_stage(self, stage: StageBuilder, repetitions: int = 1) -> TaskBuilder:
        for rep in range(repetitions):
            self.stages.append(stage)
        return self

    def set_inter_stage_interval(self, interval: float) -> TaskBuilder:
        self.inter_stage_interval = interval
        return self

    def add_event(self, at: TaskLifecyclePhase, event: Event) -> TaskBuilder:
        self.events.append(OneShotEvent(at=at, event=event))
        return self

    def add_event_for_duration(
        self, start: TaskLifecyclePhase, end: TaskLifecyclePhase, event: Event
    ) -> TaskBuilder:
        self.duration_events.append(DurationEvent(start, end, event))
        return self
