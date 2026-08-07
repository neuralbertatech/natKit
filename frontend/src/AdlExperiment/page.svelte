<script lang="ts">
    import * as Tabs from "$lib/components/ui/tabs";
    import { onDestroy } from "svelte";
    import { SvelteMap } from "svelte/reactivity";
    import BrokerConnection from "./BrokerConnection.svelte";
    import StreamSelector from "./StreamSelector.svelte";
    import Calibration from "./Calibration.svelte";
    import TaskRunner from "./TaskRunner.svelte";
    import DataExport from "./DataExport.svelte";
    import {
        SensorPosition,
        type SessionData,
        type ExperimentPhase,
    } from "./types";

    // This page stays MOUNTED while you are on another one, so that a run in
    // progress is not destroyed by navigating away (see App.svelte). `active`
    // says whether it is the page actually on screen.
    let { active = true }: { active?: boolean } = $props();

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

    // Connection status polling.
    //
    // Skipped while this page is off screen: nobody is reading these two
    // indicators, and the page stays mounted for the whole session now. State is
    // left as-is and refreshes within a second of coming back.
    // A fetch that RESOLVES only means the server answered -- a 500 counted as
    // "connected" before, so check response.ok.
    async function pollConnectivity() {
        if (!active) return;
        try {
            backendConnected = (await fetch(`/api/heartbeat`)).ok;
        } catch {
            backendConnected = false;
        }
        try {
            brokerConnected = (await fetch(`/api/is_connected_to_broker`)).ok;
        } catch {
            brokerConnected = false;
        }
    }

    void pollConnectivity();
    // These intervals had no cleanup and were never cleared, so every visit to
    // this page left another pair polling forever.
    const connectivityTimer = setInterval(pollConnectivity, 1000);
    onDestroy(() => clearInterval(connectivityTimer));

    // Navigation functions
    function switchToStreamSelection() {
        if (currentTab !== streamSelectionTab) {
            currentTab = streamSelectionTab;
        }
    }

    function switchToCalibration() {
        if (stream_position_mapping.size === 0) {
            currentTab = streamSelectionTab;
            return;
        }
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
                        {#if stream_position_mapping.size > 0}
                            <Tabs.Trigger value={calibrationTab}>
                                Calibration
                            </Tabs.Trigger>
                            <Tabs.Trigger value={experimentTab}>
                                Experiment
                            </Tabs.Trigger>
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

                    {#if stream_position_mapping.size > 0}
                        <Tabs.Content value={calibrationTab}>
                            <Calibration
                                {stream_position_mapping}
                                onReady={onCalibrationReady}
                                onStartExperiment={switchToExperiment}
                            />
                        </Tabs.Content>

                        <Tabs.Content value={experimentTab}>
                            <TaskRunner
                                {stream_position_mapping}
                                onComplete={switchToExport}
                            />
                        </Tabs.Content>
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
