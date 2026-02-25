<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import { SvelteMap } from "svelte/reactivity";
    import { onMount, onDestroy } from "svelte";
    import {
        SensorPosition,
        sensor_position_to_string,
        type SessionData,
        type MarkerType,
    } from "./types";
    import {
        ADL_TASKS,
        REST_PERIOD_SECONDS,
        COUNTDOWN_SECONDS,
        formatDuration,
        calculateTotalDuration,
    } from "./tasks";

    let {
        stream_position_mapping,
        onComplete = (data: SessionData) => {},
    }: {
        stream_position_mapping: SvelteMap<number, SensorPosition>;
        onComplete: (data: SessionData) => void;
    } = $props();

    // Experiment state
    type ExperimentState = "ready" | "countdown" | "task" | "rest" | "complete";

    let experimentState: ExperimentState = $state("ready");
    let currentTaskIndex = $state(0);
    let countdown = $state(COUNTDOWN_SECONDS);
    let taskTimeRemaining = $state(0);
    let restTimeRemaining = $state(REST_PERIOD_SECONDS);
    let sessionId: string | null = $state(null);
    let isPaused = $state(false);
    let intervalId: number | null = null;

    // Current task derived
    let currentTask = $derived(ADL_TASKS[currentTaskIndex]);
    let progress = $derived(
        Math.round((currentTaskIndex / ADL_TASKS.length) * 100),
    );
    let totalDuration = $derived(calculateTotalDuration(ADL_TASKS));

    // Insert marker into the recording
    async function insertMarker(markerType: MarkerType, taskId: string = "") {
        const timestamp = Date.now();
        try {
            await fetch(`/api/insert_marker`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    marker_type: markerType,
                    task_id: taskId,
                    timestamp: timestamp,
                    session_id: sessionId,
                }),
            });
            console.log(`Marker inserted: ${markerType} ${taskId}`);
        } catch (err) {
            console.error("Failed to insert marker:", err);
        }
    }

    // Start the recording session
    async function startRecording() {
        // Build stream position mapping for the backend
        const mappingObj: Record<string, string> = {};
        stream_position_mapping.forEach((position, streamId) => {
            mappingObj[streamId.toString()] =
                sensor_position_to_string(position);
        });

        try {
            const response = await fetch(`/api/start_recording`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    stream_position_mapping: mappingObj,
                }),
            });
            const data = await response.json();
            sessionId = data.session_id;
            console.log("Recording started:", sessionId);
            return true;
        } catch (err) {
            console.error("Failed to start recording:", err);
            return false;
        }
    }

    // Stop the recording session
    async function stopRecording() {
        try {
            await fetch(`/api/stop_recording`, {
                method: "POST",
            });
            console.log("Recording stopped");
        } catch (err) {
            console.error("Failed to stop recording:", err);
        }
    }

    // Get session data for export
    async function getSessionData(): Promise<SessionData | null> {
        try {
            const response = await fetch(`/api/get_session_data`);
            return await response.json();
        } catch (err) {
            console.error("Failed to get session data:", err);
            return null;
        }
    }

    // Start the experiment
    async function startExperiment() {
        const success = await startRecording();
        if (!success) {
            alert("Failed to start recording. Please try again.");
            return;
        }

        await insertMarker("session_start");
        experimentState = "countdown";
        countdown = COUNTDOWN_SECONDS;
        currentTaskIndex = 0;
        startTimer();
    }

    // Timer tick function
    function tick() {
        if (isPaused) return;

        switch (experimentState) {
            case "countdown":
                countdown--;
                if (countdown <= 0) {
                    // Start the task
                    experimentState = "task";
                    taskTimeRemaining = currentTask.duration_seconds;
                    insertMarker("task_start", currentTask.id);
                }
                break;

            case "task":
                taskTimeRemaining--;
                if (taskTimeRemaining <= 0) {
                    insertMarker("task_end", currentTask.id);

                    if (currentTaskIndex < ADL_TASKS.length - 1) {
                        // Move to rest period
                        experimentState = "rest";
                        restTimeRemaining = REST_PERIOD_SECONDS;
                    } else {
                        // Experiment complete
                        finishExperiment();
                    }
                }
                break;

            case "rest":
                restTimeRemaining--;
                if (restTimeRemaining <= 0) {
                    // Move to next task
                    currentTaskIndex++;
                    experimentState = "countdown";
                    countdown = COUNTDOWN_SECONDS;
                }
                break;
        }
    }

    // Start the timer
    function startTimer() {
        if (intervalId !== null) return;
        intervalId = setInterval(tick, 1000);
    }

    // Stop the timer
    function stopTimer() {
        if (intervalId !== null) {
            clearInterval(intervalId);
            intervalId = null;
        }
    }

    // Toggle pause
    function togglePause() {
        isPaused = !isPaused;
    }

    // Finish the experiment
    async function finishExperiment() {
        stopTimer();
        await insertMarker("session_end");
        await stopRecording();
        experimentState = "complete";

        const data = await getSessionData();
        if (data) {
            onComplete(data);
        }
    }

    // Cleanup on component destroy
    onDestroy(() => {
        stopTimer();
    });
</script>

<div class="task-runner">
    {#if experimentState === "ready"}
        <div class="ready-screen">
            <h2><b>Ready to Start ADL Experiment</b></h2>
            <div class="experiment-info">
                <p><strong>Tasks:</strong> {ADL_TASKS.length}</p>
                <p>
                    <strong>Estimated Duration:</strong>
                    {formatDuration(totalDuration)}
                </p>
            </div>
            <div class="task-preview">
                <h3>Tasks to Perform:</h3>
                <ol>
                    {#each ADL_TASKS as task}
                        <li>{task.name} ({task.duration_seconds}s)</li>
                    {/each}
                </ol>
            </div>
            <div class="start-section">
                <p>
                    When you click Start, the experiment will begin. Follow the
                    on-screen instructions for each task.
                </p>
                <Button size="lg" onclick={startExperiment}
                    >Start Experiment</Button
                >
            </div>
        </div>
    {:else if experimentState === "countdown"}
        <div class="countdown-screen">
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress}%"></div>
            </div>
            <p class="progress-text">
                Task {currentTaskIndex + 1} of {ADL_TASKS.length}
            </p>

            <div class="countdown-display">
                <p class="get-ready">Get Ready!</p>
                <p class="next-task">
                    Next: <strong>{currentTask.name}</strong>
                </p>
                <div class="countdown-number">{countdown}</div>
            </div>

            <div class="controls">
                <Button variant="outline" onclick={togglePause}>
                    {isPaused ? "Resume" : "Pause"}
                </Button>
            </div>
        </div>
    {:else if experimentState === "task"}
        <div class="task-screen">
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress}%"></div>
            </div>
            <p class="progress-text">
                Task {currentTaskIndex + 1} of {ADL_TASKS.length}
            </p>

            <div class="task-display">
                <h2 class="task-name">{currentTask.name}</h2>
                <p class="task-instruction">{currentTask.instruction}</p>
                <div class="task-timer">{taskTimeRemaining}</div>
                <p class="timer-label">seconds remaining</p>
            </div>

            <div class="controls">
                <Button variant="outline" onclick={togglePause}>
                    {isPaused ? "Resume" : "Pause"}
                </Button>
            </div>
        </div>
    {:else if experimentState === "rest"}
        <div class="rest-screen">
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress}%"></div>
            </div>
            <p class="progress-text">
                Task {currentTaskIndex + 1} of {ADL_TASKS.length} completed
            </p>

            <div class="rest-display">
                <p class="rest-message">Rest</p>
                <div class="rest-timer">{restTimeRemaining}</div>
                <p class="next-up">
                    Next up: <strong
                        >{ADL_TASKS[currentTaskIndex + 1]?.name}</strong
                    >
                </p>
            </div>

            <div class="controls">
                <Button variant="outline" onclick={togglePause}>
                    {isPaused ? "Resume" : "Pause"}
                </Button>
            </div>
        </div>
    {:else if experimentState === "complete"}
        <div class="complete-screen">
            <h2><b>Experiment Complete!</b></h2>
            <p>All {ADL_TASKS.length} tasks have been completed.</p>
            <p>Preparing data for export...</p>
        </div>
    {/if}

    {#if isPaused && experimentState !== "ready" && experimentState !== "complete"}
        <div class="pause-overlay">
            <div class="pause-message">
                <h2>PAUSED</h2>
                <p>Click Resume to continue</p>
                <Button onclick={togglePause}>Resume</Button>
            </div>
        </div>
    {/if}
</div>

<style>
    .task-runner {
        padding: 1em;
        position: relative;
        min-height: 500px;
    }

    /* Ready Screen */
    .ready-screen {
        text-align: center;
    }

    .ready-screen h2 {
        margin-bottom: 1em;
    }

    .experiment-info {
        margin-bottom: 1.5em;
        padding: 1em;
        background-color: #f0f7ff;
        border-radius: 8px;
        display: inline-block;
    }

    .experiment-info p {
        margin: 0.25em 0;
    }

    .task-preview {
        text-align: left;
        max-width: 400px;
        margin: 0 auto 1.5em;
        padding: 1em;
        background-color: #f5f5f5;
        border-radius: 8px;
    }

    .task-preview h3 {
        margin: 0 0 0.5em 0;
    }

    .task-preview ol {
        margin: 0;
        padding-left: 1.5em;
    }

    .task-preview li {
        padding: 0.25em 0;
    }

    .start-section {
        margin-top: 1.5em;
    }

    .start-section p {
        color: #666;
        margin-bottom: 1em;
    }

    /* Progress Bar */
    .progress-bar {
        width: 100%;
        height: 8px;
        background-color: #e0e0e0;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 0.5em;
    }

    .progress-fill {
        height: 100%;
        background-color: #4caf50;
        transition: width 0.3s ease;
    }

    .progress-text {
        text-align: center;
        color: #666;
        font-size: 0.9em;
        margin-bottom: 2em;
    }

    /* Countdown Screen */
    .countdown-screen {
        text-align: center;
    }

    .countdown-display {
        margin: 2em 0;
    }

    .get-ready {
        font-size: 1.5em;
        color: #666;
        margin-bottom: 0.5em;
    }

    .next-task {
        font-size: 1.2em;
        margin-bottom: 1em;
    }

    .countdown-number {
        font-size: 8em;
        font-weight: bold;
        color: #2196f3;
        line-height: 1;
    }

    /* Task Screen */
    .task-screen {
        text-align: center;
    }

    .task-display {
        margin: 2em 0;
        padding: 2em;
        background-color: #e8f5e9;
        border-radius: 16px;
    }

    .task-name {
        font-size: 2em;
        color: #2e7d32;
        margin: 0 0 0.5em 0;
    }

    .task-instruction {
        font-size: 1.5em;
        color: #333;
        margin-bottom: 1.5em;
    }

    .task-timer {
        font-size: 6em;
        font-weight: bold;
        color: #4caf50;
        line-height: 1;
    }

    .timer-label {
        color: #666;
        margin-top: 0.5em;
    }

    /* Rest Screen */
    .rest-screen {
        text-align: center;
    }

    .rest-display {
        margin: 2em 0;
        padding: 2em;
        background-color: #fff3e0;
        border-radius: 16px;
    }

    .rest-message {
        font-size: 2em;
        color: #e65100;
        margin: 0 0 0.5em 0;
    }

    .rest-timer {
        font-size: 6em;
        font-weight: bold;
        color: #ff9800;
        line-height: 1;
    }

    .next-up {
        margin-top: 1em;
        font-size: 1.2em;
        color: #666;
    }

    /* Complete Screen */
    .complete-screen {
        text-align: center;
        padding: 3em;
    }

    .complete-screen h2 {
        color: #4caf50;
        margin-bottom: 1em;
    }

    /* Controls */
    .controls {
        margin-top: 2em;
    }

    /* Pause Overlay */
    .pause-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
    }

    .pause-message {
        text-align: center;
        color: white;
    }

    .pause-message h2 {
        font-size: 3em;
        margin-bottom: 0.5em;
    }

    .pause-message p {
        margin-bottom: 1em;
    }
</style>
