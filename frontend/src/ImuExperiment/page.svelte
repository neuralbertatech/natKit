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

    const brokerConnectionTab = "broker-connection";
    const streamSelectionTab = "stream-selection";
    const calibrationTab = "calibration";
    const experimentsTab = "experiments";
    let currentTab = $state(streamSelectionTab);
    let stream_position_mapping = $state(
        new SvelteMap<number, SensorPosition>(),
    );

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
                            >Calibration</Tabs.Trigger
                        >
                    {/if}
                    <Tabs.Trigger value={experimentsTab}>Experiments</Tabs.Trigger>
                </Tabs.List>
                <Tabs.Content value={brokerConnectionTab}>
                    <BrokerConnection />
                </Tabs.Content>
                <Tabs.Content value={experimentsTab}>
                    <ExperimentLibrary />
                </Tabs.Content>
                {#if brokerConnected === true}
                    <Tabs.Content value={streamSelectionTab}>
                        <StreamSelector
                            swtichToCalibrationTab={switchToCalibrationTab}
                            {stream_position_mapping}
                        />
                    </Tabs.Content>
                    <Tabs.Content value={calibrationTab}>
                        <Calibration {stream_position_mapping} />
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
</style>
