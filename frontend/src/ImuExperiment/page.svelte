<script lang="ts">
    import * as Tabs from "$lib/components/ui/tabs";
    import { SvelteMap } from "svelte/reactivity";
    import Calibration from "./Calibration.svelte";
    import StreamSelector from "./StreamSelector.svelte";
    import BrokerConnection from "./BrokerConnection.svelte";
    import {
        SensorPosition,
        sensor_position_to_string,
        parse_sensor_position_from_string,
    } from "./util";
    const PUBLIC_BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

    const brokerConnectionTab = "broker-connection";
    const streamSelectionTab = "stream-selection";
    const calibrationTab = "calibration";
    let currentTab = $state(streamSelectionTab);
    let stream_position_mapping = $state(
        new SvelteMap<number, SensorPosition>(),
    );
    console.log("parent", stream_position_mapping);

    function switchToCalibrationTab() {
        if (currentTab !== calibrationTab) {
            currentTab = calibrationTab;
        }
    }

    let backendConnected = $state(false);
    let brokerConnected = $state(false);
    setInterval(async function () {
        fetch(`${PUBLIC_BACKEND_URL}/api/heartbeat`)
            .then((response) => {
                console.log("Backend connected")
                backendConnected = true;
            })
            .catch((err) => {
                console.error(`FOOOOOOOOOOOOOOOOO ${err}`);
                backendConnected = false;
            });
    }, 1000);

    setInterval(async function () {
        fetch(`${PUBLIC_BACKEND_URL}/api/is_connected_to_broker`)
            .then((response) => (brokerConnected = true))
            .catch((err) => (brokerConnected = false));
    }, 1000);
</script>

<div>
    {#if backendConnected === true}
        <div class="tabs">
            <Tabs.Root bind:value={currentTab} class="w-[400px] tabs">
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
                </Tabs.List>
                <Tabs.Content value={brokerConnectionTab}>
                    <BrokerConnection />
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
