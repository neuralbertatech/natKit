<script lang="ts">
    import * as Tabs from "$lib/components/ui/tabs";
    import { SvelteMap } from "svelte/reactivity";
    import Calibration from "./Calibration.svelte";
    import StreamSelector from "./StreamSelector.svelte";
    import BrokerConnection from "./BrokerConnection.svelte";
    import ExperimentLibrary from "./ExperimentLibrary.svelte";
    import { onDestroy } from "svelte";
    import {
        SensorPosition,
        sensor_position_to_string,
        parse_sensor_position_from_string,
    } from "./util";

    // This page stays MOUNTED while you are on another one, so that a recording
    // in progress is not destroyed by navigating away (see App.svelte). `active`
    // says whether it is the page actually on screen; polling is skipped while it
    // is not, rather than fetching twice a second for the whole session.
    let { active = true }: { active?: boolean } = $props();

    const brokerConnectionTab = "broker-connection";
    const streamSelectionTab = "stream-selection";
    const calibrationTab = "calibration";
    const experimentsTab = "experiments";
    let currentTab = $state(streamSelectionTab);
    let stream_position_mapping = $state(
        new SvelteMap<number, SensorPosition>(),
    );

    // Calibration is advisory here -- nothing in the backend blocks on it (
    // /api/start_calibration is a stub). Skipping is therefore a data-quality
    // decision, so it is remembered across a reload and shown on the tab rather
    // than silently forgotten mid-session.
    const BYPASS_KEY = "natkit.imu.calibrationBypassed";
    let calibrationBypassed = $state(
        typeof localStorage !== "undefined" &&
            localStorage.getItem(BYPASS_KEY) === "true",
    );

    function setCalibrationBypassed(skipped: boolean) {
        calibrationBypassed = skipped;
        try {
            localStorage.setItem(BYPASS_KEY, skipped ? "true" : "false");
        } catch {
            // Private-mode or blocked storage: the choice just does not persist.
        }
        if (skipped) {
            // Skipping only means anything if it moves you on to recording.
            currentTab = experimentsTab;
        }
    }

    function switchToCalibrationTab() {
        if (currentTab !== calibrationTab) {
            currentTab = calibrationTab;
        }
    }

    let backendConnected = $state(false);
    let brokerConnected = $state(false);
    // A fetch that RESOLVES only means the server answered -- a 500 counted as
    // "connected" before, so check response.ok.
    async function pollConnectivity() {
        if (!active) return;
        try {
            backendConnected = (await fetch("/api/heartbeat")).ok;
        } catch {
            backendConnected = false;
        }
        try {
            brokerConnected = (await fetch("/api/is_connected_to_broker")).ok;
        } catch {
            brokerConnected = false;
        }
    }

    void pollConnectivity();
    // Kept so leaving the page stops the polling; these intervals used to leak one
    // pair per visit.
    const connectivityTimer = setInterval(pollConnectivity, 1000);
    onDestroy(() => clearInterval(connectivityTimer));
</script>

<div>
    {#if backendConnected === true}
        <div class="tabs">
            {#if calibrationBypassed}
                <p class="bypass-banner">
                    Calibration skipped for this session — sensor accuracy is not
                    being waited on.
                    <button
                        type="button"
                        class="bypass-undo"
                        onclick={() => setCalibrationBypassed(false)}>Undo</button
                    >
                </p>
            {/if}
            <Tabs.Root bind:value={currentTab} class="tabs">
                <Tabs.List>
                    <Tabs.Trigger value={brokerConnectionTab}
                        >Broker Connection</Tabs.Trigger
                    >
                    {#if brokerConnected === true}
                        <Tabs.Trigger value={streamSelectionTab}
                            >Stream Selection</Tabs.Trigger
                        >
                        <Tabs.Trigger value={calibrationTab}
                            >Calibration{calibrationBypassed
                                ? " (skipped)"
                                : ""}</Tabs.Trigger
                        >
                    {/if}
                    <Tabs.Trigger value={experimentsTab}>Experiments</Tabs.Trigger>
                </Tabs.List>
                <Tabs.Content value={brokerConnectionTab}>
                    <BrokerConnection />
                </Tabs.Content>
                <Tabs.Content value={experimentsTab}>
                    <ExperimentLibrary
                        streamPositions={new Map(
                            [...stream_position_mapping.entries()].map(
                                ([id, position]) => [
                                    id,
                                    sensor_position_to_string(position),
                                ],
                            ),
                        )}
                    />
                </Tabs.Content>
                {#if brokerConnected === true}
                    <Tabs.Content value={streamSelectionTab}>
                        <StreamSelector
                            swtichToCalibrationTab={switchToCalibrationTab}
                            {stream_position_mapping}
                        />
                    </Tabs.Content>
                    <Tabs.Content value={calibrationTab}>
                        <Calibration
                            {stream_position_mapping}
                            bypassed={calibrationBypassed}
                            onBypass={setCalibrationBypassed}
                        />
                    </Tabs.Content>
                {/if}
            </Tabs.Root>
        </div>
    {:else}
        <div class="tabs">
            <h2><b>Unable to Connect to the Backend</b></h2>
        </div>
    {/if}
</div>

<style>
    .tabs {
        margin: 1.5em;
    }

    .bypass-banner {
        margin: 0 0 0.75em;
        padding: 0.4em 0.7em;
        border: 1px solid #f59e0b;
        border-radius: 6px;
        background: rgba(245, 158, 11, 0.12);
        font-size: 0.85em;
    }

    .bypass-undo {
        margin-left: 0.5em;
        border: none;
        background: none;
        text-decoration: underline;
        cursor: pointer;
        font: inherit;
        color: inherit;
    }
</style>
