import natKit


def main():
    muse_connection = natKit.connect("Arduino-Nano-BLE33", natKit.connection.Serial())
    file_node = natKit.FileNode(filename="imu.csv")

    gifs: [pathlib.Path] = natKit.visuals.reaching_gifs()
    stim_array = []
    for i, gif in enumerate(gifs):
        stim_array.append(
            natKit.stimulus_builder()
            .set_trigger_number(i)
            .set_duration(Seconds(5))
            .add_event_for_duration(
                start=natKit.Stimulus.Start(),
                end=natKit.Stimulus.End(),
                event=natKit.visuals.read_from_file(gif),
            )
            .build()
        )

    task_window = (
        natKit.task_window_builder()
        .set_size(as_percent_of_current_window=90)
        .set_background(natKit.visuals.FixationCross())
        .add_intro_prompt(
            text="Welcome to natKit IMU Task!\nDo the thing\nPress space when ready"
        )
        .add_stimulus_train(
            stimuli=stim_array,
            order=Random(),
            groups_per_block=2,
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
