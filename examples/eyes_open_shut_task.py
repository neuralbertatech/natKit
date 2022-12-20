import natKit


def main():
    muse_connection = natKit.connect("Muse-2")
    file_node = natKit.FileNode(filename="eyes_open_eyes_shut.csv")

    stimulus1 = (
        natKit.stimulus_builder()
        .set_trigger_number(1)
        .set_durration(Seconds(3))
        .set_appearance_weighting(1)
        .set_prompt(
            "Keep your eyes fixed on the center of the screen for 30 seconds\nPress Space when ready",
            wait=True,
        )
        .add_event_for_duration(
            start=natKit.Stimulus.Start(),
            end=natKit.Stimulus.End(),
            event=natKit.visuals.DrawFixationCross(),
        )
        .build()
    )
    stimulus2 = (
        natKit.stimulus_builder()
        .set_trigger_number(1)
        .set_durration(Seconds(3))
        .set_appearance_weighting(1)
        .set_prompt(
            "Keep your closed for 30 seconds, until you hear a beep\nPress Space when ready",
            wait=True,
        )
        .add_event(at=natKit.Stimulus.End(), event=natKit.audio.PlayBeep())
        .build()
    )

    task_window = (
        natKit.task_window_builder()
        .set_size(as_percent_of_current_window=90)
        .add_intro_prompt(text="Welcome to natKit Eyes Open Eyes Closed Task!")
        .add_stimulus_train(
            stimuli=[stimulus1, stimulus2],
            order=Random(),
            number_of_trials=5,
            number_of_blocks=1,
            inter_trail_interval=Seconds(1),
        )
        .build()
    )

    pipeline = natKit.pipeline_builder([muse_connection, task_window, file_node])
    pipeline.start()


if __name__ == "__main__":
    main()
