<script lang="ts">
    import Button from "../lib/components/ui/button/button.svelte";
    import { getContext } from "svelte";
    import { SvelteMap } from "svelte/reactivity";
    import {
        SensorPosition,
        CalibrationStatus,
        sensor_position_to_string,
        parse_sensor_position_from_string,
    } from "./util";
    const PUBLIC_BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

    let {
        stream_position_mapping,
    }: { stream_position_mapping: SvelteMap<number, SensorPosition> } =
        $props();

    let calibration_statuses: Map<SensorPosition, CalibrationStatus> = $state(
        new SvelteMap([
            [SensorPosition.LeftForearm, CalibrationStatus.Unknown],
            [SensorPosition.RightForearm, CalibrationStatus.Unknown],
            [SensorPosition.LeftUpperArm, CalibrationStatus.Unknown],
            [SensorPosition.RightUpperArm, CalibrationStatus.Unknown],
            [SensorPosition.LeftShoulder, CalibrationStatus.Unknown],
            [SensorPosition.RightShoulder, CalibrationStatus.Unknown],
            [SensorPosition.Trunk, CalibrationStatus.Unknown],
        ]),
    );

    function calibration_status_to_color(
        status: CalibrationStatus | undefined,
    ) {
        if (status === undefined) {
            return "faded";
        }

        switch (status) {
            case CalibrationStatus.Unknown:
                return "faded";
            case CalibrationStatus.Unreliable:
                return "gray";
            case CalibrationStatus.Low:
                return "red";
            case CalibrationStatus.Medium:
                return "yellow";
            case CalibrationStatus.High:
                return "green";
        }
    }

    function accuracy_int_to_calibration_status(
        val: number,
    ): CalibrationStatus {
        console.log("Foo", val);
        if (val === 0) {
            return CalibrationStatus.Unreliable;
        } else if (val === 1) {
            return CalibrationStatus.Low;
        } else if (val === 2) {
            return CalibrationStatus.Medium;
        } else if (val === 3) {
            return CalibrationStatus.High;
        } else {
            return CalibrationStatus.Unknown;
        }
    }

    //let stream_position_mapping_context: Map<number, SensorPosition> = getContext("stream_position_mapping");
    //console.log("read stream thing ", stream_position_mapping);
    setInterval(async function () {
        fetch(`${PUBLIC_BACKEND_URL}/api/get_accuracies`)
            .then((response) =>
                response
                    .json()
                    .then((json) => {
                        console.log(json);
                        let accuracies = json["accuracies"];
                        for (let id in accuracies) {
                            let accuracy_value = Number(accuracies[id]);
                            let id_num = Number(id);
                            if (stream_position_mapping.has(id_num)) {
                                let position =
                                    stream_position_mapping.get(id_num)!;
                                let accuracy =
                                    accuracy_int_to_calibration_status(
                                        accuracy_value,
                                    );
                                calibration_statuses.set(position, accuracy);
                                console.log(
                                    position,
                                    accuracy,
                                    accuracy_value,
                                    calibration_statuses,
                                );
                            }
                        }
                    })
                    .catch((err) => console.error(err)),
            )
            .catch((err) => console.error(err));
    }, 1000);

    $inspect(stream_position_mapping);
</script>

<div style="margin: 1em;">
    <div>
        <table class="calibration-table">
            <tbody>
                <tr>
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.RightShoulder,
                                ),
                            )}
                        ></span></td
                    >
                    <td
                        ><div
                            class="horizontal-line-container"
                            style="transform: rotate(10deg);"
                        >
                            <div
                                class="horizontal-line"
                                style="width: 2.5em;"
                            ></div>
                        </div></td
                    >
                    <td style="padding-top: 0.75em;"
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(SensorPosition.Trunk),
                            )}
                        ></span></td
                    >
                    <td
                        ><div
                            class="horizontal-line-container"
                            style="transform: rotate(-10deg);"
                        >
                            <div
                                class="horizontal-line"
                                style="width: 2.5em;"
                            ></div>
                        </div></td
                    >
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.LeftShoulder,
                                ),
                            )}
                        ></span></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                </tr>
                <tr>
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.RightUpperArm,
                                ),
                            )}
                        ></span></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.LeftUpperArm,
                                ),
                            )}
                        ></span></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="centered-container">
                            <span class="small-dot"></span>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="centered-container">
                            <span class="small-dot"></span>
                        </div></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height:1.5em;"
                            ></div>
                        </div></td
                    >
                </tr>
                <tr>
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.RightForearm,
                                ),
                            )}
                        ></span></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><span
                            class="dot"
                            color={calibration_status_to_color(
                                calibration_statuses.get(
                                    SensorPosition.LeftForearm,
                                ),
                            )}
                        ></span></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="vertical-line-container">
                            <div
                                class="vertical-line"
                                style="height: 1.5em;"
                            ></div>
                        </div></td
                    >
                </tr>
                <tr>
                    <td
                        ><div class="centered-container">
                            <span class="small-dot"></span>
                        </div></td
                    >
                    <td></td>
                    <td></td>
                    <td></td>
                    <td
                        ><div class="centered-container">
                            <span class="small-dot"></span>
                        </div></td
                    >
                </tr>
            </tbody>
        </table>
    </div>

    <div class="start-button">
        <Button>Start</Button>
    </div>
</div>

<style>
    td {
        /* padding: 0.5em; */
    }

    .small-dot {
        height: 10px;
        width: 10px;
        background-color: black;
        border-radius: 50%;
        display: inline-block;
        outline: 1px solid #bbb;
    }

    .dot {
        height: 25px;
        width: 25px;
        background-color: #bbb;
        border-radius: 50%;
        display: inline-block;
        outline: 1px solid black;
    }

    div.centered-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }

    [color="red"] {
        background-color: red;
    }

    [color="yellow"] {
        background-color: yellow;
    }

    [color="green"] {
        background-color: green;
    }

    [color="gray"] {
        background-color: #bbb;
    }

    [color="faded"] {
        background-color: #a9a9a9;
        opacity: 0.2;
    }

    div.start-button {
        align-content: center;
        margin: 1em;
    }

    div.vertical-line {
        width: 1px; /* Line width */
        background-color: black; /* Line color */
        height: 100%; /* Override in-line if you want specific height. */
        float: left; /* Causes the line to float to left of content.
        You can instead use position:absolute or display:inline-block
        if this fits better with your design */
    }

    div.horizontal-line-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }

    div.horizontal-line {
        width: 100%; /* Line width */
        background-color: black; /* Line color */
        height: 1px; /* Override in-line if you want specific height. */
        float: left; /* Causes the line to float to left of content.
        You can instead use position:absolute or display:inline-block
        if this fits better with your design */
    }

    div.vertical-line-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }
</style>
