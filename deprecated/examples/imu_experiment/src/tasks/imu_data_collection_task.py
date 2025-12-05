#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "../../.."))


from natKit.client.gui.pyqt6.event import Trigger
from natKit.client.gui.pyqt6.window.multi_stage_task_window import MultiStageTaskWindowBuilder
from natKit.client.gui.pyqt6.window.window_launcher import (
    launch_window,
    build_and_launch_window,
    build_and_launch_window_single_process,
)
from natKit.client.gui.pyqt6.widget import StimulusBuilder, StimulusLifecyclePhase, BlockBuilder, StageBuilder
from natKit.client.gui.pyqt6.widget.fixation_cross import DrawFixationCrossEvent
from natKit.client.gui.pyqt6.event.beep import PlayBeep
from natKit.client.gui.pyqt6.event.PlayTone import PlayTone

from time import sleep




def main():
    pos_stim_num = 6
    pos_stim_trigs = [Trigger(name="1",id=1001),Trigger(name="2",id=1002),Trigger(name="3",id=1003),Trigger(name="4",id=1004),Trigger(name="5",id=1005),Trigger(name="6",id=1006)]
    neg_stim_num = 3
    neg_stim_trigs = [Trigger(name="11",id=1011),Trigger(name="12",id=1012),Trigger(name="13",id=1013)]
    cal_stim_num = 5
    cal_stim_trigs = [Trigger(name="95",id=95),Trigger(name="96",id=96),Trigger(name="97",id=97),Trigger(name="98",id=98),Trigger(name="99",id=99)]
    
    all_trigs = pos_stim_trigs + neg_stim_trigs + cal_stim_trigs
    
    neg_tones = [PlayTone("Walk"),PlayTone("Sitting"),PlayTone("Standing")]
    cal_tones = [PlayTone("N-Pose"),PlayTone("T-Pose"),PlayTone("1"),PlayTone("2"),PlayTone("3")]
    
    stim_template = (
        StimulusBuilder()
        .set_prompt("Press space to continue")
        .set_cue_duration(2)
        .set_duration(5)
        .add_event(at=StimulusLifecyclePhase.TRIAL_START, event=PlayTone("start"))
        .add_event(at=StimulusLifecyclePhase.TRIAL_END, event=PlayTone("stop"))
    )
        
    ### Tutorial ###
    
    tutorial_pos_stim = [stim_template.add_event(at=StimulusLifecyclePhase.CUE_START, event=PlayTone(x)).build() for x in range(6)]
    tutorial_neg_stim = [stim_template.add_event(at=StimulusLifecyclePhase.CUE_START, event=tone).build() for tone in neg_tones]
    tutorial_stim = tutorial_pos_stim + tutorial_neg_stim

    tutorial_block = (
        BlockBuilder()
            # .set_stimulus(tutorial_stim)
            # .set_number_of_trials(1)
            .set_prompt("Tutorial Block starting")
            # .start_delay(1)
            .add_stimulus(tutorial_stim[0], 5)
            .add_stimulus(tutorial_stim[1], 5)
            .add_stimulus(tutorial_stim[2], 5)
            .set_inter_trial_interval(1)
    )

    tutorial_stage = (
        StageBuilder()
        .set_prompt("Tutorial!")
        .add_block(tutorial_block, 1)
        .set_inter_block_interval(1)
    )

    ### Calibration ###
    
    cal_stim = [stim_template.add_event(at=StimulusLifecyclePhase.CUE_START, event=tone).set_trigger(stim).build() for tone,stim in zip(cal_tones,cal_stim_trigs)]

    cal_block = (
        BlockBuilder()
            # .set_stimulus(cal_stim)
            # .set_number_of_trials(1)
            .set_prompt("Calibration Block starting")
            .add_stimulus(cal_stim[0], 5)
            .add_stimulus(cal_stim[1], 5)
            .add_stimulus(cal_stim[2], 5)
            .add_stimulus(cal_stim[3], 5)
            .add_stimulus(cal_stim[4], 5)
            .set_inter_trial_interval(1)
    )
    
    calibration_stage = (
        StageBuilder()
            .set_prompt("Calibration!")
            .add_block(cal_block, 1)
            .set_inter_block_interval(1)
    )

    ### Task ###
    
    task_pos_stim = [stim_template.add_event(at=StimulusLifecyclePhase.CUE_START, event=PlayTone(x)).set_trigger(pos_stim_trigs[x]).build() for x in range(6)]
    task_neg_stim = [stim_template.add_event(at=StimulusLifecyclePhase.CUE_START, event=tone).set_trigger(stim).build() for tone,stim in zip(neg_tones,neg_stim_trigs)]

    task_positive_block = (
        BlockBuilder()
            # .set_stimulus(task_pos_stim)
            # .set_number_of_trials(5)
            .set_prompt("Task Block starting")

            .add_stimulus(task_pos_stim[0], 5)
            .add_stimulus(task_pos_stim[1], 5)
            .add_stimulus(task_pos_stim[2], 5)
            .add_stimulus(task_pos_stim[3], 5)
            .add_stimulus(task_pos_stim[4], 5)
            .add_stimulus(task_pos_stim[5], 5)
            .set_trial_ordering("random")
            .set_inter_trial_interval(1)
    )
    
    task_negative_block = (
        BlockBuilder()
            # .set_stimulus(task_neg_stim)
            # .set_number_of_trials(5)
            .add_stimulus(task_neg_stim[0], 5)
            .add_stimulus(task_neg_stim[1], 5)
            .add_stimulus(task_neg_stim[2], 5)
            .set_trial_ordering("random")
            .set_inter_trial_interval(1)
    )

    task_stage = (
        StageBuilder()
            .set_prompt("Task!")
            .add_block(task_positive_block, 5)
            .add_block(task_negative_block, 2)            
            .set_block_ordering(random=True) 
            .set_inter_block_interval(1)
            .add_event(at.StageLifecyclePhase.STAGE_END)

    
    ### Build Window ###

    builder = MultiStageTaskWindowBuilder().set_window_size(as_absolute_value=(720, 480)).set_prompt("Welcome!").set_stages(tutorial_stage, calibration_stage, task_stage).set_inter_stage_interval(1).set_triggers(all_trigs)
    ### Add in ending - save everything + close it down without hanging


    build_and_launch_window_single_process(builder)


if __name__ == "__main__":
    main()
