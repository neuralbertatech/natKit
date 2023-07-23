#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, ".."))


from natKit.client.gui.pyqt6.event import Trigger
from natKit.client.gui.pyqt6.window.task_window import TaskWindowBuilder
from natKit.client.gui.pyqt6.window.window_launcher import (
    launch_window,
    build_and_launch_window,
    build_and_launch_window_single_process,
)
from natKit.client.gui.pyqt6.widget import StimulusBuilder, StimulusLifecyclePhase
from natKit.client.gui.pyqt6.widget.fixation_cross import DrawFixationCrossEvent
from natKit.client.gui.pyqt6.event.beep import PlayBeep

from time import sleep


def main():
    trigger1 = Trigger(name="Red Fixation Cross")
    trigger2 = Trigger(name="Beep")
    training_stimulus1 = (
        StimulusBuilder()
        .set_prompt(
            "Keep your eyes fixed on the center of the screen for 30 seconds\nPress the space key when ready"
        )
        .set_trigger(trigger1)
        .set_duration(3)
        .add_event_for_duration(
            start=StimulusLifecyclePhase.START,
            end=StimulusLifecyclePhase.END,
            event=DrawFixationCrossEvent(),
        )
    )

    training_stimulus2 = (
        StimulusBuilder()
        .set_prompt(
            "Keep your eyes closed for 30 seconds, until you hear a beep\nPress the space key when ready"
        )
        .set_trigger(trigger2)
        .set_duration(3)
        .add_event(at=StimulusLifecyclePhase.END, event=PlayBeep())
    )

    trial_stimulus1 = (
        StimulusBuilder()
        .set_duration(0.3)
        .set_trigger(trigger1)
        .add_event_for_duration(
            start=StimulusLifecyclePhase.START,
            end=StimulusLifecyclePhase.END,
            event=DrawFixationCrossEvent(),
        )
    )

    trial_stimulus2 = (
        StimulusBuilder()
        .set_duration(0.3)
        .set_trigger(trigger2)
        .add_event_for_duration(
            start=StimulusLifecyclePhase.START,
            end=StimulusLifecyclePhase.END,
            event=DrawFixationCrossEvent(color="green"),
        )
    )

    builder = (
        TaskWindowBuilder()
        .set_window_size(as_absulute_value=(720, 480))
        .set_intro_prompt("Welcome to the natKit Eyes Open Eyes Closed Task!")
        .set_trial_prompt("When you see the red cross press the space bar")
        .set_triggers([trigger1, trigger2])
        .set_training_stimulus([training_stimulus1, training_stimulus2])
        .set_trial_stimulus([trial_stimulus1, trial_stimulus2])
        .set_number_of_trials(10)
        .set_number_of_blocks(3)
        .set_inter_trial_interval(1)
    )

    build_and_launch_window_single_process(builder)


if __name__ == "__main__":
    main()
