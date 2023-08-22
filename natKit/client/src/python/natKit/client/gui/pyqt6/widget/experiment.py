from __future__ import annotations

from natKit.client.gui.pyqt6.event import DurationEvent
from natKit.client.gui.pyqt6.event import Event
from natKit.client.gui.pyqt6.event import OneShotEvent
from natKit.client.gui.pyqt6.widget import TaskBuilder
from natKit.client.gui.pyqt6.event import Trigger

from PyQt6 import QtCore
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QMessageBox

from enum import Enum

from typing import List
from typing import NoReturn


class ExperimentLifecyclePhase(Enum):
    PROMPT = 1
    EXPERIMENT_START = 2
    TASK_START = 3
    TASK_END = 4
    EXPERIMENT_END = 5


class Experiment(QWidget):
    def __init__(
        self,
        parent=None,
        name: str = "Task",
        prompt: str = None,
        trigger: Trigger = None,
        tasks: List[TaskBuilder] = [],
        inter_task_interval: float = 0.0,
        events: List[OneShotEvent] = [],
        duration_events: List[DurationEvent] = [],
    ) -> NoReturn:
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)

        self.name = name
        self.intro_prompt = prompt
        self.trigger = trigger
        self.tasks = [task.build() for task in tasks]
        self.inter_task_interval = inter_task_interval
        self.events = events
        self.duration_events = duration_events
        self.finished = False
        self.stream = None
        self.task_index = 0

    def run(self) -> NoReturn:
        self.prompt()
        self.experiment_start()

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(int(self.inter_task_interval * 1000))
        self.timer.timeout.connect(self.run_task)
        self.timer.start()

    def prompt(self) -> NoReturn:
        self._handle_one_shot_events(ExperimentLifecyclePhase.PROMPT)
        self._handle_duration_events(ExperimentLifecyclePhase.PROMPT)

        if self.intro_prompt is not None:
            prompt_box = QMessageBox()
            prompt_box.setText(self.intro_prompt)
            prompt_box.exec()

    def experiment_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(ExperimentLifecyclePhase.EXPERIMENT_START)
        self._handle_duration_events(ExperimentLifecyclePhase.EXPERIMENT_START)

    def run_task(self) -> NoReturn:
        self.task_start()
        self.tasks(self.task_index).run()
        self.task_end()
        self.task_index += 1
        if self.stage_index < len(self.stages):
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(int(self.inter_stage_interval * 1000))
            self.timer.timeout.connect(self.run_task)
            self.timer.start()
        else:
            experiment_end()

    def task_start(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(ExperimentLifecyclePhase.TASK_START)
        self._handle_duration_events(ExperimentLifecyclePhase.TASK_START)

    def task_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(0)
        self._handle_one_shot_events(ExperimentLifecyclePhase.TASK_END)
        self._handle_duration_events(ExperimentLifecyclePhase.TASK_END)
        self.finished = True
        self.setParent(None)

    def experiment_end(self) -> NoReturn:
        if self.trigger is not None:
            self.trigger.set_value(1)
        self._handle_one_shot_events(ExperimentLifecyclePhase.EXPERIMENT_END)
        self._handle_duration_events(ExperimentLifecyclePhase.EXPERIMENT_END)

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


class ExperimentBuilder:
    def __init__(self) -> NoReturn:
        self.name = "Experiment"
        self.tasks = []
        self.inter_task_interval = 0.0
        self.prompt = None
        self.trigger = None
        self.events = []
        self.duration_events = []

    def build(self) -> Task:
        return Experiment(
            name=self.name,
            tasks=self.tasks,
            inter_stage_interval=self.inter_task_interval,
            prompt=self.prompt,
            trigger=self.trigger,
            events=self.events,
            duration_events=self.duration_events,
        )

    def set_name(self, name: str) -> ExperimentBuilder:
        self.name = name
        return self

    def set_prompt(self, prompt: str) -> ExperimentBuilder:
        self.prompt = prompt
        return self

    def set_trigger(self, trigger: Trigger) -> ExperimentBuilder:
        self.trigger = trigger
        return self

    def add_task(self, tasks: TaskBuilder, repetitions: int = 1) -> ExperimentBuilder:
        for rep in range(repetitions):
            self.tasks.append(tasks)
        return self

    def set_inter_task_interval(self, interval: float) -> ExperimentBuilder:
        self.inter_task_interval = interval
        return self

    def add_event(
        self, at: ExperimentLifecyclePhase, event: Event
    ) -> ExperimentBuilder:
        self.events.append(OneShotEvent(at=at, event=event))
        return self

    def add_event_for_duration(
        self,
        start: ExperimentLifecyclePhase,
        end: ExperimentLifecyclePhase,
        event: Event,
    ) -> ExperimentBuilder:
        self.duration_events.append(DurationEvent(start, end, event))
        return self
