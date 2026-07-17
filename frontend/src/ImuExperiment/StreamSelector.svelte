<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion";
    import { Checkbox } from "$lib/components/ui/checkbox";
    import Check from "lucide-svelte/icons/check";
    import ChevronsUpDown from "lucide-svelte/icons/chevrons-up-down";
    import * as Command from "$lib/components/ui/command";
    import * as Popover from "$lib/components/ui/popover";
    import { Button } from "$lib/components/ui/button";
    import { cn } from "$lib/utils.js";
    import { tick } from "svelte";
    import {
        SensorPosition,
        sensor_position_to_string,
        parse_sensor_position_from_string,
    } from "./util";
    import { onMount } from "svelte";
    import { RefreshCw } from "lucide-svelte";
    import { setContext } from "svelte";
    import { SvelteMap } from "svelte/reactivity";

    let {
        swtichToCalibrationTab = () => {},
        stream_position_mapping,
    }: {
        swtichToCalibrationTab: () => void;
        stream_position_mapping: SvelteMap<number, SensorPosition>;
    } = $props();

    //let stream_position_mapping_context = $state(new Map<number, SensorPosition>());
    //setContext("stream_position_mapping", stream_position_mapping_context);
    //console.log("Set stream thing ", stream_position_mapping_context);

    const sensor_positions = [
        {
            value: SensorPosition.LeftForearm,
            label: sensor_position_to_string(SensorPosition.LeftForearm),
        },
        {
            value: SensorPosition.LeftUpperArm,
            label: sensor_position_to_string(SensorPosition.LeftUpperArm),
        },
        {
            value: SensorPosition.LeftShoulder,
            label: sensor_position_to_string(SensorPosition.LeftShoulder),
        },
        {
            value: SensorPosition.Trunk,
            label: sensor_position_to_string(SensorPosition.Trunk),
        },
        {
            value: SensorPosition.RightForearm,
            label: sensor_position_to_string(SensorPosition.RightForearm),
        },
        {
            value: SensorPosition.RightUpperArm,
            label: sensor_position_to_string(SensorPosition.RightUpperArm),
        },
        {
            value: SensorPosition.RightShoulder,
            label: sensor_position_to_string(SensorPosition.RightShoulder),
        },
    ];

    type Topic = {
        schema_name: string;
        type: string;
        id: number;
        serialization_type: string;
    };

    type Stream = {
        id: number;
        name: string;
        topics: Topic[];
    };

    // let streams: Stream[] = $state([
    //     { id: 13793649553528, name: "Raw Stream", topics: [ { schema_name: "BasicMetaInfoSchema", type: "Meta", id: 13793649553528, serialization_type: "Json" }, { schema_name: "NatImuBulkDataSchema", type: "Data", id: 13793649553528, serialization_type: "Binary" } ] },
    //     { id: 189167462739012, name: "Raw Stream", topics: [ { schema_name: "BasicMetaInfoSchema", type: "Meta", id: 189167462739012, serialization_type: "Json" } ] },
    //     { id: 13793649553360, name: "Raw Stream", topics: [ { schema_name: "BasicMetaInfoSchema", type: "Meta", id: 13793649553360, serialization_type: "Json" }, { schema_name: "NatImuBulkDataSchema", type: "Data", id: 13793649553360, serialization_type: "Binary" } ] },
    // ]);
    let streams: Stream[] = $state([]);
    let dropdown_enabled: boolean[] = $state([]);
    let dropdown_open: boolean[] = $state([]);
    let dropdown_values: SensorPosition[] = $state([]);

    let searching_for_streams: boolean = $state(false);
    async function get_streams() {
        searching_for_streams = true;
        console.log("Querying Streams");
        fetch(`/api/get_all_streams`, {
            mode: "cors",
            method: "GET",
        })
            .then((response) => {
                response
                    .json()
                    .then((json) => {
                        streams = [];
                        for (var id in json) {
                            var value = json[id];
                            var topics_json = value["topics"];
                            var topics = [];
                            for (var topic_index in topics_json) {
                                var topic = topics_json[topic_index];
                                topics.push({
                                    schema_name: topic["schema_name"],
                                    type: topic["type"],
                                    id: Number(id),
                                    serialization_type:
                                        topic["serialization_type"],
                                });
                            }
                            streams.push({
                                id: Number(id),
                                name: value["name"],
                                topics: topics,
                            });
                        }
                        dropdown_enabled = [
                            ...Array(streams.length).keys(),
                        ].map((_) => false);
                        dropdown_open = [...Array(streams.length).keys()].map(
                            (_) => false,
                        );
                        dropdown_values = [...Array(streams.length).keys()].map(
                            (_) => SensorPosition.None,
                        );
                        searching_for_streams = false;
                    })
                    .catch((err) => {
                        console.error(err);
                        searching_for_streams = false;
                    });
            })
            .catch((err) => {
                console.error(err);
                searching_for_streams = false;
            });
    }
    onMount(get_streams);

    function get_stream_ids() {
        let ids = [];
        for (let i = 0; i < streams.length; ++i) {
            if (dropdown_values[i] !== SensorPosition.None) {
                ids.push(streams[i].id);
            }
        }

        return ids;
    }

    async function set_streams() {
        fetch(`/api/set_streams`, {
            //mode: "cors",
            method: "POST",
            body: JSON.stringify({
                stream_ids: get_stream_ids(),
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
        }).then((_response) => {
            fetch(`/api/start_calibration`, {
                mode: "cors",
                method: "POST",
            }).then((_inner_response) => {
                swtichToCalibrationTab();
            });
        });
        stream_position_mapping.clear();
        for (let i = 0; i < streams.length; ++i) {
            if (dropdown_values[i] !== SensorPosition.None) {
                stream_position_mapping.set(streams[i].id, dropdown_values[i]);
            }
        }
    }

    // We want to refocus the trigger button when the user selects
    // an item from the list so users can continue navigating the
    // rest of the form with the keyboard.
    function closeAndFocusTrigger(triggerId: string, index: number) {
        dropdown_open[index] = false;
        tick().then(() => {
            document.getElementById(triggerId)?.focus();
        });
    }

    let selected_values = $derived(
        [...Array(streams.length).keys()].map(
            (index) =>
                sensor_positions.find((f) => f.value === dropdown_values[index])
                    ?.label ?? "Select a Position...",
        ),
    );

    function sensor_checkbox_clicked(
        state: boolean | "indeterminate",
        index: number,
    ) {
        if (state !== true) {
            dropdown_enabled[index] = false;
            dropdown_open[index] = false;
            dropdown_values[index] = SensorPosition.None;
        }
    }

    function are_streams_ready_for_submission(): boolean {
        let any_dropdown_enabled: boolean = false;
        for (let i: number = 0; i < dropdown_enabled.length; ++i) {
            if (dropdown_enabled[i] === true) {
                any_dropdown_enabled = true;
                if (dropdown_values[i] === SensorPosition.None) {
                    return false;
                }
            }
        }
        return any_dropdown_enabled;
    }
</script>

<div>
    <div style="display: flex">
        <div>
            <h1 style="margin: 1em"><b>Select Streams to be Used</b></h1>
        </div>
        <div>
            <Button
                variant="outline"
                size="icon"
                onclick={get_streams}
                disabled={searching_for_streams}
            >
                <RefreshCw />
            </Button>
        </div>
    </div>
    <div>
        <Accordion.Root>
            {#each streams as stream, index}
                <Accordion.Item value="item-{index}">
                    <div
                        class="flex items-center space-x-6"
                        style="padding-left: 1em"
                    >
                        <Checkbox
                            bind:checked={dropdown_enabled[index]}
                            onCheckedChange={(state) =>
                                sensor_checkbox_clicked(state, index)}
                        />
                        <Accordion.Trigger>{stream.id}</Accordion.Trigger>
                        {#if dropdown_enabled[index] === true}
                            <Popover.Root
                                bind:open={dropdown_open[index]}
                                let:ids
                            >
                                <Popover.Trigger asChild let:builder>
                                    <Button
                                        builders={[builder]}
                                        variant="outline"
                                        role="combobox"
                                        aria-expanded={dropdown_open[index]}
                                        class="w-[200px] justify-between"
                                    >
                                        {selected_values[index]}
                                        <ChevronsUpDown
                                            class="ml-2 h-4 w-4 shrink-0 opacity-50"
                                        />
                                    </Button>
                                </Popover.Trigger>
                                <Popover.Content class="w-[200px] p-0">
                                    <Command.Root>
                                        <Command.Group>
                                            {#each sensor_positions.filter((position) => !dropdown_values.some((val) => val === position.value)) as position}
                                                <Command.Item
                                                    value={position.label}
                                                    onSelect={(
                                                        currentValue: string,
                                                    ) => {
                                                        dropdown_values[index] =
                                                            parse_sensor_position_from_string(
                                                                currentValue,
                                                            );
                                                        closeAndFocusTrigger(
                                                            ids.trigger,
                                                            index,
                                                        );
                                                    }}
                                                >
                                                    <Check
                                                        class={cn(
                                                            "mr-2 h-4 w-4",
                                                            dropdown_values[
                                                                index
                                                            ] !==
                                                                position.value &&
                                                                "text-transparent",
                                                        )}
                                                    />
                                                    {position.label}
                                                </Command.Item>
                                            {/each}
                                        </Command.Group>
                                    </Command.Root>
                                </Popover.Content>
                            </Popover.Root>
                        {/if}
                    </div>
                    <Accordion.Content>
                        <ul>
                            {#each stream.topics as topic}
                                <li style="padding-left: 1em">
                                    <b>{topic.type}</b> - {topic.schema_name} encoded
                                    with {topic.serialization_type}
                                </li>
                            {/each}
                        </ul>
                    </Accordion.Content>
                </Accordion.Item>
            {/each}
        </Accordion.Root>
    </div>
    <div class="stream-submission">
        <Button
            disabled={!are_streams_ready_for_submission()}
            onclick={set_streams}>Submit Changes</Button
        >
    </div>
</div>

<style>
    div.stream-submission {
        align-content: center;
        margin: 1em;
    }
</style>
