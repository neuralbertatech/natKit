<script lang="ts">
    import * as Tabs from "$lib/components/ui/tabs";
    import { SvelteMap } from "svelte/reactivity";
    import BrokerConnection from "./BrokerConnection.svelte";
    import StreamSelector from "./StreamSelector.svelte";
    import Calibration from "./Calibration.svelte";
    import TaskRunner from "./TaskRunner.svelte";
    import DataExport from "./DataExport.svelte";
    import {
        SensorPosition,
        REQUIRED_SENSOR_POSITIONS,
        type SessionData,
        type ExperimentPhase,
    } from "./types";

    // Tab/phase constants
    const connectionTab = "connection";
    const streamSelectionTab = "stream-selection";
    const calibrationTab = "calibration";
    const experimentTab = "experiment";
    const exportTab = "export";

    // State
    let currentTab: ExperimentPhase = $state(connectionTab);
    let stream_position_mapping = $state(
        new SvelteMap<number, SensorPosition>(),
    );
    let backendConnected = $state(false);
    let brokerConnected = $state(false);
    let sessionData: SessionData | null = $state(null);
    let calibrationReady = $state(false);

    // Connection status polling
    setInterval(async function () {
        fetch(`/api/heartbeat`)
            .then((response) => {
                backendConnected = true;
            })
            .catch((err) => {
                console.error("Backend connection error:", err);
                backendConnected = false;
            });
    }, 1000);

    setInterval(async function () {
        fetch(`/api/is_connected_to_broker`)
            .then((response) => (brokerConnected = true))
            .catch((err) => (brokerConnected = false));
    }, 1000);

    // Navigation functions
    function switchToStreamSelection() {
        if (currentTab !== streamSelectionTab) {
            currentTab = streamSelectionTab;
        }
    }

    function switchToCalibration() {
        if (currentTab !== calibrationTab) {
            currentTab = calibrationTab;
        }
    }

    function switchToExperiment() {
        if (currentTab !== experimentTab) {
            currentTab = experimentTab;
        }
    }

    function switchToExport(data: SessionData) {
        sessionData = data;
        currentTab = exportTab;
    }

    function startNewSession() {
        sessionData = null;
        stream_position_mapping.clear();
        calibrationReady = false;
        currentTab = streamSelectionTab;
    }

    function onCalibrationReady(ready: boolean) {
        calibrationReady = ready;
    }
</script>

<div class="adl-experiment">
    <h1 class="title"><b>ADL Experiment</b></h1>

    {#if backendConnected === true}
        <div class="tabs-container">
            <Tabs.Root bind:value={currentTab} class="w-full">
                <Tabs.List>
                    <Tabs.Trigger value={connectionTab}>
                        Connection
                    </Tabs.Trigger>
                    {#if brokerConnected === true}
                        <Tabs.Trigger value={streamSelectionTab}>
                            Stream Selection
                        </Tabs.Trigger>
                        {#if stream_position_mapping.size === REQUIRED_SENSOR_POSITIONS.length}
                            <Tabs.Trigger value={calibrationTab}>
                                Calibration
                            </Tabs.Trigger>
                            {#if calibrationReady}
                                <Tabs.Trigger value={experimentTab}>
                                    Experiment
                                </Tabs.Trigger>
                            {/if}
                        {/if}
                        {#if sessionData !== null}
                            <Tabs.Trigger value={exportTab}>
                                Export
                            </Tabs.Trigger>
                        {/if}
                    {/if}
                </Tabs.List>

                <Tabs.Content value={connectionTab}>
                    <BrokerConnection
                        {backendConnected}
                        {brokerConnected}
                        onContinue={switchToStreamSelection}
                    />
                </Tabs.Content>

                {#if brokerConnected === true}
                    <Tabs.Content value={streamSelectionTab}>
                        <StreamSelector
                            {stream_position_mapping}
                            onContinue={switchToCalibration}
                        />
                    </Tabs.Content>

                    {#if stream_position_mapping.size === REQUIRED_SENSOR_POSITIONS.length}
                        <Tabs.Content value={calibrationTab}>
                            <Calibration
                                {stream_position_mapping}
                                onReady={onCalibrationReady}
                                onStartExperiment={switchToExperiment}
                            />
                        </Tabs.Content>

                        {#if calibrationReady}
                            <Tabs.Content value={experimentTab}>
                                <TaskRunner
                                    {stream_position_mapping}
                                    onComplete={switchToExport}
                                />
                            </Tabs.Content>
                        {/if}
                    {/if}

                    {#if sessionData !== null}
                        <Tabs.Content value={exportTab}>
                            <DataExport
                                {sessionData}
                                onNewSession={startNewSession}
                            />
                        </Tabs.Content>
                    {/if}
                {/if}
            </Tabs.Root>
        </div>
    {:else}
        <div class="connection-error">
            <h2><b>Unable to Connect to the Backend</b></h2>
            <p>Please ensure the natKit backend server is running.</p>
        </div>
    {/if}
</div>

<style>
    .adl-experiment {
        padding: 1.5em;
        max-width: 1200px;
        margin: 0 auto;
    }

    .title {
        margin-bottom: 1em;
        font-size: 1.5em;
    }

    .tabs-container {
        margin-top: 1em;
    }

    .connection-error {
        padding: 2em;
        text-align: center;
        background-color: #fee;
        border-radius: 8px;
        border: 1px solid #fcc;
    }

    .connection-error p {
        margin-top: 0.5em;
        color: #666;
    }
</style>
