<script lang="ts">
    import Button from "../lib/components/ui/button/button.svelte";
    import { onMount } from "svelte";
    import { SvelteMap } from "svelte/reactivity";
    import { SensorPosition, CalibrationStatus } from "./util";
    const PUBLIC_BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

    let {
        stream_position_mapping,
        onStart = () => {},
    }: {
        stream_position_mapping: SvelteMap<number, SensorPosition>;
        onStart: () => void;
    } = $props();

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
    let start_in_progress = $state(false);
    let start_error = $state("");
    let start_success_message = $state("");

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

    function min_calibration_status(
        statuses: CalibrationStatus[],
    ): CalibrationStatus {
        const known = statuses.filter((s) => s !== CalibrationStatus.Unknown);
        if (known.length === 0) {
            return CalibrationStatus.Unknown;
        }
        return Math.min(...known) as CalibrationStatus;
    }

    function extract_display_status_for_stream(raw_accuracy: unknown) {
        if (
            typeof raw_accuracy === "object" &&
            raw_accuracy !== null &&
            "accelerometer" in raw_accuracy &&
            "gyroscope" in raw_accuracy &&
            "rotation" in raw_accuracy
        ) {
            const accuracy_data = raw_accuracy as {
                accelerometer: number;
                gyroscope: number;
                rotation: number;
            };
            return min_calibration_status([
                accuracy_int_to_calibration_status(
                    Number(accuracy_data.accelerometer ?? 0),
                ),
                accuracy_int_to_calibration_status(
                    Number(accuracy_data.gyroscope ?? 0),
                ),
                accuracy_int_to_calibration_status(
                    Number(accuracy_data.rotation ?? 0),
                ),
            ]);
        }

        return accuracy_int_to_calibration_status(Number(raw_accuracy));
    }

    onMount(() => {
        const interval = setInterval(async function () {
            fetch(`${PUBLIC_BACKEND_URL}/api/get_accuracies`)
                .then((response) =>
                    response
                        .json()
                        .then((json) => {
                            let accuracies = json["accuracies"];
                            for (let id in accuracies) {
                                let id_num = Number(id);
                                if (stream_position_mapping.has(id_num)) {
                                    let position =
                                        stream_position_mapping.get(id_num)!;
                                    let status =
                                        extract_display_status_for_stream(
                                            accuracies[id],
                                        );
                                    calibration_statuses.set(position, status);
                                }
                            }
                        })
                        .catch((err) => console.error(err)),
                )
                .catch((err) => console.error(err));
        }, 1000);

        return () => clearInterval(interval);
    });

    async function start_calibration() {
        if (start_in_progress) {
            return;
        }

        start_in_progress = true;
        start_error = "";
        start_success_message = "";
        try {
            const response = await fetch(
                `${PUBLIC_BACKEND_URL}/api/start_calibration`,
                {
                    method: "POST",
                    headers: {
                        "Content-type": "application/json; charset=UTF-8",
                    },
                },
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const response_json = await response.json();
            start_success_message =
                response_json?.message ?? "Calibration started";
            onStart();
        } catch (err) {
            console.error(err);
            start_error = "Failed to start calibration";
        } finally {
            start_in_progress = false;
        }
    }

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
        <Button
            onclick={start_calibration}
            disabled={start_in_progress || stream_position_mapping.size === 0}
            >{start_in_progress ? "Starting..." : "Start"}</Button
        >
    </div>
    {#if start_error}
        <p class="start-status error">{start_error}</p>
    {/if}
    {#if start_success_message}
        <p class="start-status success">{start_success_message}</p>
    {/if}
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

    .start-status {
        margin: 0.5em 1em 0;
        font-size: 0.9em;
    }

    .start-status.error {
        color: #c62828;
    }

    .start-status.success {
        color: #2e7d32;
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
