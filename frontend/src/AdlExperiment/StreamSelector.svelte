<script lang="ts">
    import * as Accordion from "$lib/components/ui/accordion";
    import { Checkbox } from "$lib/components/ui/checkbox";
    import Check from "lucide-svelte/icons/check";
    import ChevronsUpDown from "lucide-svelte/icons/chevrons-up-down";
    import * as Command from "$lib/components/ui/command";
    import * as Popover from "$lib/components/ui/popover";
    import { Button } from "$lib/components/ui/button";
    import { cn } from "$lib/utils.ts";
    import { tick, onMount } from "svelte";
    import { RefreshCw } from "lucide-svelte";
    import { SvelteMap } from "svelte/reactivity";
    import {
        SensorPosition,
        sensor_position_to_string,
        parse_sensor_position_from_string,
        REQUIRED_SENSOR_POSITIONS,
        type Stream,
        type Topic,
    } from "./types";

    let {
        stream_position_mapping,
        onContinue = () => {},
    }: {
        stream_position_mapping: SvelteMap<number, SensorPosition>;
        onContinue: () => void;
    } = $props();

    // Available sensor positions for dropdown
    const sensor_positions = REQUIRED_SENSOR_POSITIONS.map((pos) => ({
        value: pos,
        label: sensor_position_to_string(pos),
    }));

    // State
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
                            var topics: Topic[] = [];
                            for (var topic_index in topics_json) {
                                var topic = topics_json[topic_index];
                                topics.push({
                                    schema_name: topic["schema_name"],
                                    type: topic["type"],
                                    serialization_type:
                                        topic["serialization_type"],
                                });
                            }
                            streams.push({
                                id: Number(id),
                                name: value["name"] || "Raw Stream",
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

    function get_stream_ids(): number[] {
        let ids: number[] = [];
        for (let i = 0; i < streams.length; ++i) {
            if (dropdown_values[i] !== SensorPosition.None) {
                ids.push(streams[i].id);
            }
        }
        return ids;
    }

    async function submitStreams() {
        // Send selected streams to backend
        fetch(`/api/set_streams`, {
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
                onContinue();
            });
        });

        // Update the mapping
        stream_position_mapping.clear();
        for (let i = 0; i < streams.length; ++i) {
            if (dropdown_values[i] !== SensorPosition.None) {
                stream_position_mapping.set(streams[i].id, dropdown_values[i]);
            }
        }
    }

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

    function sensor_checkbox_clicked(state: boolean, index: number) {
        if (state === false) {
            dropdown_enabled[index] = false;
            dropdown_open[index] = false;
            dropdown_values[index] = SensorPosition.None;
        }
    }

    // Count how many sensors are assigned
    let assigned_count = $derived(
        dropdown_values.filter((v) => v !== SensorPosition.None).length,
    );

    // Check if all 7 required positions are assigned
    function areAllPositionsAssigned(): boolean {
        const assignedPositions = new Set(
            dropdown_values.filter((v) => v !== SensorPosition.None),
        );
        return REQUIRED_SENSOR_POSITIONS.every((pos) =>
            assignedPositions.has(pos),
        );
    }

    let all_positions_assigned = $derived(areAllPositionsAssigned());
</script>

<div class="stream-selector">
    <div class="header">
        <div>
            <h2><b>Select Streams for ADL Experiment</b></h2>
            <p class="subtitle">
                Assign all {REQUIRED_SENSOR_POSITIONS.length} sensor positions ({assigned_count}/{REQUIRED_SENSOR_POSITIONS.length}
                assigned)
            </p>
        </div>
        <Button
            variant="outline"
            size="icon"
            onclick={get_streams}
            disabled={searching_for_streams}
        >
            <RefreshCw class={searching_for_streams ? "animate-spin" : ""} />
        </Button>
    </div>

    {#if streams.length === 0}
        <div class="no-streams">
            <p>
                No streams found. Make sure your IMU sensors are connected and
                streaming.
            </p>
            <Button onclick={get_streams} disabled={searching_for_streams}>
                Refresh Streams
            </Button>
        </div>
    {:else}
        <div class="required-positions">
            <h3>Required Positions:</h3>
            <div class="position-grid">
                {#each REQUIRED_SENSOR_POSITIONS as pos}
                    {@const isAssigned = dropdown_values.includes(pos)}
                    <span class="position-badge" class:assigned={isAssigned}>
                        {#if isAssigned}
                            <Check size={14} />
                        {/if}
                        {sensor_position_to_string(pos)}
                    </span>
                {/each}
            </div>
        </div>

        <Accordion.Root>
            {#each streams as stream, index}
                <Accordion.Item value="item-{index}">
                    <div class="stream-row">
                        <Checkbox
                            bind:checked={dropdown_enabled[index]}
                            onCheckedChange={(state: boolean) =>
                                sensor_checkbox_clicked(state, index)}
                        />
                        <Accordion.Trigger class="stream-id"
                            >{stream.id}</Accordion.Trigger
                        >
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
                        <ul class="topic-list">
                            {#each stream.topics as topic}
                                <li>
                                    <b>{topic.type}</b> - {topic.schema_name} encoded
                                    with {topic.serialization_type}
                                </li>
                            {/each}
                        </ul>
                    </Accordion.Content>
                </Accordion.Item>
            {/each}
        </Accordion.Root>

        <div class="submit-section">
            {#if !all_positions_assigned}
                <p class="warning">
                    Please assign all {REQUIRED_SENSOR_POSITIONS.length} sensor positions
                    before continuing.
                </p>
            {/if}
            <Button disabled={!all_positions_assigned} onclick={submitStreams}>
                Continue to Calibration
            </Button>
        </div>
    {/if}
</div>

<style>
    .stream-selector {
        padding: 1em;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1em;
    }

    .header h2 {
        margin: 0;
    }

    .subtitle {
        color: #666;
        margin: 0.25em 0 0 0;
    }

    .no-streams {
        text-align: center;
        padding: 2em;
        background-color: #f5f5f5;
        border-radius: 8px;
    }

    .no-streams p {
        margin-bottom: 1em;
        color: #666;
    }

    .required-positions {
        margin-bottom: 1.5em;
        padding: 1em;
        background-color: #f0f7ff;
        border-radius: 8px;
    }

    .required-positions h3 {
        margin: 0 0 0.5em 0;
        font-size: 0.9em;
        color: #333;
    }

    .position-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em;
    }

    .position-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25em;
        padding: 0.25em 0.5em;
        background-color: #e0e0e0;
        border-radius: 4px;
        font-size: 0.85em;
        color: #666;
    }

    .position-badge.assigned {
        background-color: #d4edda;
        color: #155724;
    }

    .stream-row {
        display: flex;
        align-items: center;
        gap: 1em;
        padding-left: 1em;
    }

    .stream-id {
        flex: 1;
    }

    .topic-list {
        padding-left: 2em;
        margin: 0.5em 0;
    }

    .topic-list li {
        padding: 0.25em 0;
    }

    .submit-section {
        margin-top: 1.5em;
        text-align: center;
    }

    .warning {
        color: #856404;
        margin-bottom: 0.5em;
    }
</style>
