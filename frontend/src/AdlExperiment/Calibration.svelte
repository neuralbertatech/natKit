<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { onMount } from "svelte";
    import { SvelteMap } from "svelte/reactivity";
    import {
        SensorPosition,
        CalibrationStatus,
        sensor_position_to_string,
        REQUIRED_SENSOR_POSITIONS,
    } from "./types";

    let {
        stream_position_mapping,
        onReady = (ready: boolean) => {},
        onStartExperiment = () => {},
    }: {
        stream_position_mapping: SvelteMap<number, SensorPosition>;
        onReady: (ready: boolean) => void;
        onStartExperiment: () => void;
    } = $props();

    // Structure to hold all three accuracy values per sensor
    interface SensorAccuracies {
        accelerometer: CalibrationStatus;
        gyroscope: CalibrationStatus;
        rotation: CalibrationStatus;
    }

    const defaultAccuracies: SensorAccuracies = {
        accelerometer: CalibrationStatus.Unknown,
        gyroscope: CalibrationStatus.Unknown,
        rotation: CalibrationStatus.Unknown,
    };

    // Initialize calibration statuses dynamically based on required positions
    let calibration_statuses: Map<SensorPosition, SensorAccuracies> = $state(
        new SvelteMap(
            REQUIRED_SENSOR_POSITIONS.map((pos) => [
                pos,
                { ...defaultAccuracies },
            ]),
        ),
    );

    let selected_positions = $derived(
        REQUIRED_SENSOR_POSITIONS.filter((requiredPos) =>
            Array.from(stream_position_mapping.values()).includes(requiredPos),
        ),
    );

    function calibration_status_to_color(
        status: CalibrationStatus | undefined,
    ): string {
        if (status === undefined) return "faded";
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
        if (val === 0) return CalibrationStatus.Unreliable;
        else if (val === 1) return CalibrationStatus.Low;
        else if (val === 2) return CalibrationStatus.Medium;
        else if (val === 3) return CalibrationStatus.High;
        else return CalibrationStatus.Unknown;
    }

    function parseSensorAccuracies(raw_accuracy: unknown): SensorAccuracies {
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
            return {
                accelerometer: accuracy_int_to_calibration_status(
                    Number(accuracy_data.accelerometer ?? 0),
                ),
                gyroscope: accuracy_int_to_calibration_status(
                    Number(accuracy_data.gyroscope ?? 0),
                ),
                rotation: accuracy_int_to_calibration_status(
                    Number(accuracy_data.rotation ?? 0),
                ),
            };
        }

        // Backward-compatible parsing for packed bitfield format:
        // bits 5-4 accel, 3-2 gyro, 1-0 rotation (e.g. 63 => 3,3,3)
        const packed = Number(raw_accuracy);
        if (Number.isFinite(packed)) {
            return {
                accelerometer: accuracy_int_to_calibration_status(
                    (packed >> 4) & 0b11,
                ),
                gyroscope: accuracy_int_to_calibration_status(
                    (packed >> 2) & 0b11,
                ),
                rotation: accuracy_int_to_calibration_status(packed & 0b11),
            };
        }

        return { ...defaultAccuracies };
    }

    function calibrationStatusSeverity(status: CalibrationStatus): number {
        switch (status) {
            case CalibrationStatus.Unknown:
                return 0;
            case CalibrationStatus.Unreliable:
                return 1;
            case CalibrationStatus.Low:
                return 2;
            case CalibrationStatus.Medium:
                return 3;
            case CalibrationStatus.High:
                return 4;
        }
    }

    // Get the worst calibration status for overall display.
    // Explicit severity mapping avoids relying on enum numeric ordering.
    function getOverallCalibrationStatus(
        accuracies: SensorAccuracies,
    ): CalibrationStatus {
        const values: CalibrationStatus[] = [
            accuracies.accelerometer,
            accuracies.gyroscope,
            accuracies.rotation,
        ];
        let worst = values[0];
        for (const value of values.slice(1)) {
            if (
                calibrationStatusSeverity(value) <
                calibrationStatusSeverity(worst)
            ) {
                worst = value;
            }
        }
        return worst;
    }

    // Poll for calibration status
    onMount(() => {
        const interval = setInterval(async function () {
            fetch(`/api/get_accuracies`)
                .then((response) =>
                    response
                        .json()
                        .then((json) => {
                            let accuracies = json["accuracies"];
                            for (let id in accuracies) {
                                let accuracy_data = accuracies[id];
                                let id_num = Number(id);
                                if (stream_position_mapping.has(id_num)) {
                                    let position =
                                        stream_position_mapping.get(id_num)!;
                                    let sensorAccuracies: SensorAccuracies =
                                        parseSensorAccuracies(accuracy_data);
                                    calibration_statuses.set(
                                        position,
                                        sensorAccuracies,
                                    );
                                }
                            }
                        })
                        .catch((err) => console.error(err)),
                )
                .catch((err) => console.error(err));
        }, 1000);

        return () => clearInterval(interval);
    });

    // Check if all selected sensors are fully high-calibrated.
    let all_calibrated = $derived(
        selected_positions.length > 0 &&
            selected_positions.every((pos) => {
                return (
                    getOverallStatusForPosition(pos) === CalibrationStatus.High
                );
            }),
    );

    // Notify parent when calibration status changes
    $effect(() => {
        onReady(all_calibrated);
    });

    function getAccuraciesForPosition(pos: SensorPosition): SensorAccuracies {
        return calibration_statuses.get(pos) ?? { ...defaultAccuracies };
    }

    // Get the overall (worst) status for dot display on body diagram
    function getOverallStatusForPosition(
        pos: SensorPosition,
    ): CalibrationStatus {
        const accuracies = calibration_statuses.get(pos);
        if (!accuracies) return CalibrationStatus.Unknown;
        return getOverallCalibrationStatus(accuracies);
    }
</script>

<div class="calibration">
    <h2><b>Sensor Calibration</b></h2>
    <p class="instructions">
        Rotate each sensor and place it flat on each of its 6 faces for about 1
        second per face.
    </p>

    <div class="body-diagram">
        <table class="calibration-table">
            <tbody>
                <!-- Shoulders and Trunk row -->
                <tr>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.RightShoulder,
                                ),
                            )}
                        ></span>
                    </td>
                    <td>
                        <div
                            class="horizontal-line-container"
                            style="transform: rotate(10deg);"
                        >
                            <div
                                class="horizontal-line"
                                style="width: 2.5em;"
                            ></div>
                        </div>
                    </td>
                    <td style="padding-top: 0.75em;">
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.Trunk,
                                ),
                            )}
                        ></span>
                    </td>
                    <td>
                        <div
                            class="horizontal-line-container"
                            style="transform: rotate(-10deg);"
                        >
                            <div
                                class="horizontal-line"
                                style="width: 2.5em;"
                            ></div>
                        </div>
                    </td>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.LeftShoulder,
                                ),
                            )}
                        ></span>
                    </td>
                </tr>
                <!-- Vertical lines -->
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
                <!-- Upper arms -->
                <tr>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.RightUpperArm,
                                ),
                            )}
                        ></span>
                    </td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.LeftUpperArm,
                                ),
                            )}
                        ></span>
                    </td>
                </tr>
                <!-- Vertical lines -->
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
                <!-- Elbows -->
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
                <!-- Vertical lines -->
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
                <!-- Forearms -->
                <tr>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.RightForearm,
                                ),
                            )}
                        ></span>
                    </td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td>
                        <span
                            class="dot"
                            color={calibration_status_to_color(
                                getOverallStatusForPosition(
                                    SensorPosition.LeftForearm,
                                ),
                            )}
                        ></span>
                    </td>
                </tr>
                <!-- Vertical lines to hands -->
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
                <!-- Hands (wrists) -->
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

    <!-- Legend -->
    <div class="legend">
        <h3>Calibration Status Legend:</h3>
        <div class="legend-items">
            <span class="legend-item"
                ><span class="dot small" color="faded"></span> Unknown</span
            >
            <span class="legend-item"
                ><span class="dot small" color="gray"></span> Unreliable</span
            >
            <span class="legend-item"
                ><span class="dot small" color="red"></span> Low</span
            >
            <span class="legend-item"
                ><span class="dot small" color="yellow"></span> Medium</span
            >
            <span class="legend-item"
                ><span class="dot small" color="green"></span> High</span
            >
        </div>
    </div>

    <!-- Sensor status list -->
    <div class="status-list">
        <h3>Sensor Status:</h3>
        {#each REQUIRED_SENSOR_POSITIONS as pos}
            {@const accuracies = getAccuraciesForPosition(pos)}
            {@const overallStatus = getOverallCalibrationStatus(accuracies)}
            {@const allHigh = overallStatus === CalibrationStatus.High}
            <div class="status-row">
                <span
                    class="dot small"
                    color={calibration_status_to_color(overallStatus)}
                ></span>
                <span class="sensor-name">{sensor_position_to_string(pos)}</span
                >
                <div class="accuracy-details">
                    <span class="accuracy-item">
                        <span class="accuracy-label">Accel:</span>
                        <span
                            class="dot tiny"
                            color={calibration_status_to_color(
                                accuracies.accelerometer,
                            )}
                        ></span>
                    </span>
                    <span class="accuracy-item">
                        <span class="accuracy-label">Gyro:</span>
                        <span
                            class="dot tiny"
                            color={calibration_status_to_color(
                                accuracies.gyroscope,
                            )}
                        ></span>
                    </span>
                    <span class="accuracy-item">
                        <span class="accuracy-label">Rot:</span>
                        <span
                            class="dot tiny"
                            color={calibration_status_to_color(
                                accuracies.rotation,
                            )}
                        ></span>
                    </span>
                </div>
                <span class="sensor-status" class:high={allHigh}>
                    {allHigh ? "Ready" : "Calibrating..."}
                </span>
            </div>
        {/each}
    </div>

    <div class="start-button">
        {#if selected_positions.length === 0}
            <p class="waiting-message">
                Select at least one sensor position to continue.
            </p>
        {:else if all_calibrated}
            <p class="ready-message">
                All selected sensors calibrated! You can start the experiment.
            </p>
        {:else}
            <p class="waiting-message">
                Warning: not all selected sensors are at high calibration. You
                can still continue, but data quality may be reduced.
            </p>
        {/if}
        <Button
            disabled={selected_positions.length === 0}
            onclick={onStartExperiment}
        >
            Start Experiment
        </Button>
    </div>
</div>

<style>
    .calibration {
        padding: 1em;
    }

    h2 {
        margin-bottom: 0.5em;
    }

    .instructions {
        color: #666;
        margin-bottom: 1.5em;
    }

    .body-diagram {
        display: flex;
        justify-content: center;
        margin-bottom: 1.5em;
    }

    .calibration-table {
        border-collapse: collapse;
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

    .dot.small {
        height: 16px;
        width: 16px;
    }

    .dot.tiny {
        height: 10px;
        width: 10px;
    }

    .centered-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }

    [color="red"] {
        background-color: #ff4444;
    }

    [color="yellow"] {
        background-color: #ffcc00;
    }

    [color="green"] {
        background-color: #44bb44;
    }

    [color="gray"] {
        background-color: #999;
    }

    [color="faded"] {
        background-color: #a9a9a9;
        opacity: 0.3;
    }

    .vertical-line-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }

    .vertical-line {
        width: 1px;
        background-color: black;
        height: 100%;
    }

    .horizontal-line-container {
        width: 100%;
        display: flex;
        justify-content: center;
    }

    .horizontal-line {
        width: 100%;
        background-color: black;
        height: 1px;
    }

    .legend {
        margin-bottom: 1.5em;
        padding: 1em;
        background-color: #f5f5f5;
        border-radius: 8px;
    }

    .legend h3 {
        margin: 0 0 0.5em 0;
        font-size: 0.9em;
    }

    .legend-items {
        display: flex;
        flex-wrap: wrap;
        gap: 1em;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 0.5em;
        font-size: 0.85em;
    }

    .status-list {
        margin-bottom: 1.5em;
    }

    .status-list h3 {
        margin: 0 0 0.5em 0;
        font-size: 0.9em;
    }

    .status-row {
        display: flex;
        align-items: center;
        gap: 0.75em;
        padding: 0.5em;
        border-bottom: 1px solid #eee;
    }

    .sensor-name {
        min-width: 100px;
    }

    .accuracy-details {
        display: flex;
        gap: 0.75em;
        flex: 1;
    }

    .accuracy-item {
        display: flex;
        align-items: center;
        gap: 0.25em;
        font-size: 0.8em;
    }

    .accuracy-label {
        color: #666;
    }

    .sensor-status {
        color: #999;
        font-size: 0.85em;
        min-width: 80px;
        text-align: right;
    }

    .sensor-status.high {
        color: #28a745;
        font-weight: 500;
    }

    .start-button {
        text-align: center;
        margin-top: 1em;
    }

    .ready-message {
        color: #28a745;
        margin-bottom: 0.5em;
    }

    .waiting-message {
        color: #856404;
        margin-bottom: 0.5em;
    }
</style>
