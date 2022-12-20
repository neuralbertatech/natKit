import natKit


def main():
    muse_connection = natKit.connect("Muse-2")
    file_node = natKit.FileNode(filename="oddball.csv")

    stimulus1 = (
        natKit.stimulus_builder()
        .set_trigger_number(1)
        .set_duration(Seconds(2))
        .set_appearance_weighting(4)
        .add_event_for_duration(
            start=natKit.Stimulus.Start(),
            end=natKit.Stimulus.End(),
            event=natKit.visuals.Circle(color="blue"),
        )
        .add_event(natKit.listeners.TimedResponseInput("<space>"), write_to_trigger=3)
        .build()
    )
    stimulus2 = (
        natKit.stimulus_builder()
        .set_trigger_number(2)
        .set_duration(Seconds(2))
        .set_appearance_weighting(1)
        .add_event_for_duration(
            start=natKit.Stimulus.Start(),
            end=natKit.Stimulus.End(),
            event=natKit.visuals.Circle(color="red"),
        )
        .add_event(natKit.listeners.TimedResponseInput("<space>"), write_to_trigger=4)
        .build()
    )

    task_window = (
        natKit.task_window_builder()
        .set_size(as_percent_of_current_window=90)
        .set_background(natKit.visuals.FixationCross())
        .add_intro_prompt(
            text="Welcome to natKit Oddball Task!\nKeep your eyes fixed on the cross in the center of the screen.\nWhen the red circle appears press the spacebar as quickly as possible"
        )
        .add_stimulus_train(
            stimuli=[stimulus1, stimulus2],
            order=Random(),
            number_of_trials=10,
            number_of_blocks=1,
            block_prompt="Press the spacebar to continue",
            inter_trail_interval=Seconds(1),
        )
        .build()
    )

    pipeline = natKit.pipeline_builder([muse_connection, task_window, file_node])
    pipeline.start()


if __name__ == "__main__":
    main()
