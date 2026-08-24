<script lang="ts">
    // The rig's health, as a pill that expands.
    //
    // What this has to get right is the difference between "fine", "I don't know
    // yet" and "something is wrong" -- and never to show the first when it means
    // one of the other two. Concretely:
    //
    //   * a rate of null renders as an em dash with the reason on hover, NEVER as
    //     0.0/s. A device whose rates are not yet computable is not idle.
    //   * a quiet device stays in the list, greyed, with its last-known figures
    //     and how long ago they were. Removing the row would turn a visible
    //     failure into an empty space.
    //   * "no devices" is qualified by how many status topics the backend is
    //     tailing, because zero topics (the rig has never published) and four
    //     topics with nothing on them (every board went silent) are different
    //     problems that look identical in a device list.
    import type {
        DeviceHealthMessage,
        DeviceHealthEntry,
        DeviceCommandResultMessage,
    } from "../StreamViewer/types";
    import type { ConnectionState } from "../StreamViewer/websocket";

    interface Props {
        health: DeviceHealthMessage | null;
        connectionState: ConnectionState;
        /**
         * Send a command to a device over EXECUTION_COMMAND. Used here for the
         * indicator LED (TEC-NATKIT-82) — this panel is the one place that lists
         * every device by MAC, which is exactly the context for "make that one
         * blue".
         */
        sendDeviceCommand?: (
            streamId: string,
            command: string,
            args?: Record<string, unknown>,
        ) => boolean;
        deviceCommandPending?: Record<string, boolean>;
        deviceCommandResults?: Record<string, DeviceCommandResultMessage>;
    }

    let {
        health,
        connectionState,
        sendDeviceCommand,
        deviceCommandPending = {},
        deviceCommandResults = {},
    }: Props = $props();

    /**
     * The colours offered, and why these.
     *
     * ⚠️ Widely separated hues, NOT a gradient. The job is telling boards apart
     * across a bench, so neighbouring swatches have to be unmistakable under warm
     * room light — a palette that steps smoothly through a hue wheel fails exactly
     * when it is needed, with two boards a shade apart.
     *
     * Red is absent on purpose: it is what a person reads as "fault", and an
     * identity colour means nothing of the kind.
     */
    const LED_COLOURS = [
        { name: "green", r: 0, g: 255, b: 0 },
        { name: "blue", r: 0, g: 0, b: 255 },
        { name: "yellow", r: 255, g: 200, b: 0 },
        { name: "magenta", r: 255, g: 0, b: 255 },
        { name: "cyan", r: 0, g: 255, b: 255 },
        { name: "white", r: 255, g: 255, b: 255 },
    ];

    function ledPending(streamId: string): boolean {
        return deviceCommandPending[`${streamId}:set_led`] === true;
    }

    /**
     * The device's own answer to the last command, when it was an LED one.
     *
     * ⚠️ Deliberately shows what the DEVICE said rather than what was clicked. A
     * swatch that highlights on click would claim the board is blue whether or not
     * the command ever arrived — and a board whose LED is not soldered on replies
     * "no indicator on this node", which is worth reading.
     */
    function ledReply(streamId: string): { ok: boolean; text: string } | null {
        const result = deviceCommandResults[streamId];
        if (!result || !result.command.startsWith("set_led")) {
            return null;
        }
        // Same precedence the calibration commands use: what the device said, then
        // why it said nothing, then a bare outcome. ⚠️ `timed_out` is its own case —
        // a board that never answered is not a board that answered "no".
        const text =
            result.records.at(-1)?.message ??
            result.error ??
            (result.timed_out ? "no answer" : result.ok ? "done" : "refused");
        return { ok: result.ok, text };
    }

    let expanded = $state(false);

    // ⚠️ How long we have actually been watching, on the BACKEND's clock.
    //
    // Without this the panel said "every board that used to report has stopped"
    // one second after subscribing, when the truth was "no frame has arrived
    // yet" -- the two look identical in a snapshot (no devices, N topics tailed)
    // and only elapsed time tells them apart. The devices publish at 1 Hz, so a
    // few seconds of silence is news and one second is not.
    let firstWallMs = $state<number | null>(null);
    $effect(() => {
        if (health && firstWallMs === null) {
            firstWallMs = health.wall_ms;
        }
        if (!health) {
            firstWallMs = null;
        }
    });
    const watchedMs = $derived(
        health && firstWallMs !== null ? health.wall_ms - firstWallMs : 0,
    );
    const SETTLING_MS = 4000;
    const settling = $derived(watchedMs < SETTLING_MS);

    const leaves = $derived(health?.devices.filter((d) => d.role === "leaf") ?? []);
    const hub = $derived(health?.devices.find((d) => d.role === "hub") ?? null);
    const quietCount = $derived(health?.devices.filter((d) => d.quiet).length ?? 0);
    const liveCount = $derived((health?.devices.length ?? 0) - quietCount);

    // ⚠️ Deliberately not "ok" when devices is empty. An empty rig is the state
    // this panel exists to make legible, not a pass.
    const summary = $derived.by(() => {
        if (connectionState !== "connected") return "backend offline";
        if (!health) return "waiting";
        if (health.devices.length === 0) {
            if (settling) return "listening";
            return health.topics_tailed === 0
                ? "no devices have ever reported"
                : `${health.topics_tailed} topics, nothing on them`;
        }
        if (quietCount === 0) return `${liveCount} live`;
        if (liveCount === 0) return `all ${quietCount} quiet`;
        return `${liveCount} live, ${quietCount} quiet`;
    });

    const tone = $derived.by(() => {
        if (connectionState !== "connected" || !health) return "unknown";
        if (health.devices.length === 0) return settling ? "unknown" : "warn";
        if (quietCount > 0) return "bad";
        return "good";
    });

    /** A rate, or an em dash. Never a zero standing in for "unknown". */
    function rate(device: DeviceHealthEntry, field: string): string {
        const value = device.rates?.[field];
        if (value === undefined) return "—";
        // Below 0.05 shows as 0.0, which for a counter that IS moving reads as
        // stopped; a sub-0.1 rate is better said in words than in a rounded zero.
        if (value > 0 && value < 0.05) return "<0.1";
        return value.toFixed(1);
    }

    function num(device: DeviceHealthEntry, field: string): string {
        const value = device.fields?.[field];
        return typeof value === "number" ? String(value) : "—";
    }

    function nested(device: DeviceHealthEntry, group: string, field: string): string {
        const outer = device.fields?.[group];
        if (outer && typeof outer === "object") {
            const value = (outer as Record<string, unknown>)[field];
            if (typeof value === "number") return String(value);
            if (typeof value === "boolean") return value ? "yes" : "no";
        }
        return "—";
    }

    /**
     * How long since we last learned anything NEW about this device.
     *
     * ⚠️ Not simply `age_ms`. When the hub has lost a leaf it keeps publishing that
     * leaf's last known entry once a second, so `age_ms` reads ~0 while nothing has
     * actually been heard for minutes — the panel said "now" about a device that
     * had been gone for half an hour. When that is the case, quote the unheard
     * time instead, because that is the number a person needs.
     */
    function age(device: DeviceHealthEntry): string {
        const notHeard = device.quiet_reason === "device_not_heard";
        const ms = notHeard ? (device.unheard_ms ?? device.age_ms) : device.age_ms;
        if (ms < 1500) return "now";
        const seconds = Math.round(ms / 1000);
        if (seconds < 90) return `${seconds}s ago`;
        return `${Math.round(seconds / 60)}m ago`;
    }

    /** Why there are no rates, in words, for the title attribute. */
    function rateReason(device: DeviceHealthEntry): string {
        switch (device.rate_status) {
            case "available":
                return `averaged over ${((device.rate_interval_us ?? 0) / 1e6).toFixed(1)}s of the device's own clock`;
            case "first_sample":
                return "only one frame so far — nothing to difference against";
            case "window_too_short":
                return "not yet enough history to average over; counters relayed on a leaf's heartbeat alias badly over one second";
            case "rebooted":
                return "the device restarted, so its counters restarted too — rates resume once new history builds";
            case "clock_not_advanced":
                return "the last two frames carry the same device clock, so there is no interval to divide by";
            default:
                return "";
        }
    }

    // The leaf identity a person uses at the bench is the MAC on the sticker,
    // not the 14-digit device id.
    function label(device: DeviceHealthEntry): string {
        const mac = device.fields?.mac;
        return typeof mac === "string" && mac.length > 0 ? mac : device.device_id;
    }
</script>

<div class="rig-health" class:expanded>
    <button
        class="rig-pill tone-{tone}"
        onclick={() => (expanded = !expanded)}
        title="Device health from the hub's 1 Hz status frames"
    >
        <span class="dot"></span>
        <span class="label">Rig</span>
        <span class="summary">{summary}</span>
        <span class="chevron">{expanded ? "▾" : "▸"}</span>
    </button>

    {#if expanded}
        <div class="rig-body">
            {#if connectionState !== "connected"}
                <p class="note">The backend is not connected, so nothing is being read.</p>
            {:else if !health}
                <p class="note">Waiting for the first status frame.</p>
            {:else}
                {#if health.devices.length === 0}
                    <p class="note">
                        {#if settling}
                            Listening. Nothing has arrived yet — the boards publish
                            about once a second, so give it a moment.
                        {:else if health.topics_tailed === 0}
                            No device has ever published a status frame. Either the hub
                            is off, or its firmware predates the status channel.
                        {:else}
                            The backend is tailing {health.topics_tailed} status
                            {health.topics_tailed === 1 ? "topic" : "topics"} but nothing
                            has arrived — every board that used to report has stopped.
                        {/if}
                    </p>
                {/if}

                {#if hub}
                    <div class="device hub" class:quiet={hub.quiet}>
                        <div class="device-head">
                            <span class="role">hub</span>
                            <span class="id">{hub.device_id}</span>
                            <span class="age" class:stale={hub.quiet}>{age(hub)}</span>
                        </div>
                        <div class="metrics">
                            <span title="Frames the hub handed to its uplink, per second. {rateReason(hub)}">
                                uplink <b>{rate(hub, "frames_sent")}/s</b>
                            </span>
                            <span title="Frames the hub discarded because its queue was full. Anything above zero is loss.">
                                dropped <b>{rate(hub, "frames_dropped")}/s</b>
                            </span>
                            <span title="Leaves in the hub's registry right now (a count, not a rate)">
                                nodes <b>{num(hub, "nodes_known")}</b>
                            </span>
                            <span title="The bound on rig-wide clock agreement — the figure to quote as the rig's synchronisation">
                                coherence <b>{num(hub, "coherence_bound_us")}µs</b>
                            </span>
                            <span title="The hub's die temperature; meaningless if the sensor failed to read">
                                temp <b>{num(hub, "chip_temp_c")}°C</b>
                            </span>
                            <span title="The hub's own noise floor — the CONTROL for each leaf's figure">
                                floor <b>{num(hub, "noise_floor_dbm")}dBm</b>
                            </span>
                        </div>
                    </div>
                {/if}

                {#each leaves as leaf (leaf.device_id)}
                    <div class="device" class:quiet={leaf.quiet}>
                        <div class="device-head">
                            <span class="role">leaf</span>
                            <span class="id">{label(leaf)}</span>
                            <span class="age" class:stale={leaf.quiet}>{age(leaf)}</span>
                        </div>
                        {#if sendDeviceCommand}
                            <!-- The indicator LED (TEC-NATKIT-82). Offered on every
                                 device row because this panel is the only place
                                 that lists them all by MAC. -->
                            <div class="led-row">
                                <span class="led-label">LED</span>
                                {#each LED_COLOURS as colour}
                                    <button
                                        type="button"
                                        class="led-swatch"
                                        style={`background: rgb(${colour.r}, ${colour.g}, ${colour.b})`}
                                        title={`Set this board's LED to ${colour.name}`}
                                        disabled={ledPending(leaf.device_id)}
                                        onclick={() =>
                                            sendDeviceCommand?.(
                                                leaf.device_id,
                                                "set_led",
                                                { r: colour.r, g: colour.g, b: colour.b },
                                            )}
                                        aria-label={`Set LED to ${colour.name}`}
                                    ></button>
                                {/each}
                                <button
                                    type="button"
                                    class="led-off"
                                    title="Turn this board's LED off"
                                    disabled={ledPending(leaf.device_id)}
                                    onclick={() =>
                                        sendDeviceCommand?.(leaf.device_id, "set_led", {
                                            off: true,
                                        })}
                                >
                                    off
                                </button>
                                {#if ledPending(leaf.device_id)}
                                    <span class="led-reply">sending…</span>
                                {:else if ledReply(leaf.device_id)}
                                    {@const reply = ledReply(leaf.device_id)}
                                    <span class="led-reply" class:bad={!reply?.ok}>
                                        {reply?.text}
                                    </span>
                                {/if}
                            </div>
                        {/if}
                        {#if leaf.quiet_reason === "device_not_heard"}
                            <!-- ⚠️ Said out loud, because the frames ARE arriving:
                                 without this the row looks like a reporting device
                                 whose numbers happen not to move. -->
                            <p class="quiet-note">
                                The hub is still publishing this leaf's last known
                                state, but has not heard from it — every figure below
                                is frozen at whatever it was then.
                            </p>
                        {/if}
                        <div class="metrics">
                            <span title="Data frames the hub received from this leaf, per second. {rateReason(leaf)}">
                                data <b>{rate(leaf, "data_frames")}/s</b>
                            </span>
                            <span title="Frames the leaf BUILT, per second. Reaches the hub on the leaf's own heartbeat rather than with the data, so it is approximate — read the GAP against the received rate, not the digits. A large gap is loss in the air.">
                                built <b>{rate(leaf, "leaf_frames_built")}/s</b>
                            </span>
                            <span
                                class:alarm={(leaf.rates?.leaf_send_failures ?? 0) > 1}
                                title="Radio sends that failed, per second. A leaf can build frames and deliver almost none — that is what a bad connector looks like."
                            >
                                send fails <b>{rate(leaf, "leaf_send_failures")}/s</b>
                            </span>
                            <span title="Signal strength of this leaf at the hub. Compare against the hub's own noise floor, not against a fixed number.">
                                rssi <b>{num(leaf, "rssi_last")}dBm</b>
                            </span>
                            <span title="Whether the hub holds a usable clock fit for this leaf">
                                sync <b>{nested(leaf, "sync", "valid")}</b>
                            </span>
                            <span title="Beacons this leaf missed, per second — the clock fit's input rate going wrong">
                                missed <b>{rate(leaf, "sync.beacons_missed")}/s</b>
                            </span>
                        </div>
                    </div>
                {/each}

                {#if health.devices.some((d) => d.rate_status !== "available")}
                    <p class="note subtle">
                        A dash means there is no rate to report — not a rate of zero.
                        Hover a figure for why.
                    </p>
                {/if}
            {/if}
        </div>
    {/if}
</div>

<style>
    .rig-health {
        font-size: 0.78rem;
        /* The body is an overlay, not a block: it lives in the graph toolbar, and
           letting it grow inline would push every control below it down by 300px
           each time somebody glanced at the rig. */
        position: relative;
    }

    .rig-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.25rem 0.6rem;
        border: 1px solid #2f3b4a;
        border-radius: 999px;
        background: #161c24;
        color: #cbd5e1;
        cursor: pointer;
        font: inherit;
    }

    .rig-pill:hover {
        border-color: #46586e;
    }

    .dot {
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 50%;
        background: #64748b;
        flex: none;
    }

    .tone-good .dot { background: #4ade80; }
    .tone-bad .dot { background: #f87171; }
    .tone-warn .dot { background: #fbbf24; }
    .tone-unknown .dot { background: #64748b; }

    .label {
        color: #94a3b8;
    }

    .summary {
        color: #e2e8f0;
    }

    .chevron {
        color: #64748b;
    }

    .rig-body {
        position: absolute;
        top: calc(100% + 0.35rem);
        /* Anchored RIGHT, not left: the pill sits near the toolbar's right edge,
           and a left-anchored 34rem panel ran straight off the viewport -- the
           rightmost metric on every row was clipped. */
        right: 0;
        z-index: 40;
        min-width: 34rem;
        box-shadow: 0 0.6rem 1.6rem rgba(0, 0, 0, 0.55);
        padding: 0.5rem 0.6rem;
        border: 1px solid #2f3b4a;
        border-radius: 0.5rem;
        background: #12171f;
        max-width: 44rem;
    }

    .device {
        padding: 0.35rem 0;
        border-bottom: 1px solid #1e2632;
    }

    .device:last-of-type {
        border-bottom: none;
    }

    /* Greyed, but still legible: a quiet device's last figures are the evidence
       for what went wrong, so they must not be dimmed into unreadability. */
    .device.quiet {
        opacity: 0.62;
    }

    .device-head {
        display: flex;
        align-items: baseline;
        gap: 0.5rem;
    }

    .role {
        text-transform: uppercase;
        font-size: 0.65rem;
        letter-spacing: 0.06em;
        color: #64748b;
        min-width: 2.4rem;
    }

    .hub .role {
        color: #93c5fd;
    }

    .id {
        color: #e2e8f0;
        font-family: ui-monospace, monospace;
    }

    .age {
        color: #64748b;
        margin-left: auto;
    }

    .age.stale {
        color: #f87171;
    }

    .metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 0.15rem 0.9rem;
        margin-top: 0.15rem;
        padding-left: 2.9rem;
        color: #7f8ea3;
    }

    .metrics b {
        color: #cbd5e1;
        font-weight: 600;
        font-family: ui-monospace, monospace;
    }

    .metrics .alarm b {
        color: #f87171;
    }

    .led-row {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        margin-top: 0.2rem;
        padding-left: 2.9rem;
    }

    .led-label {
        color: #64748b;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .led-swatch {
        width: 0.85rem;
        height: 0.85rem;
        border-radius: 50%;
        border: 1px solid #2f3b4a;
        padding: 0;
        cursor: pointer;
    }

    .led-swatch:hover:not(:disabled) {
        border-color: #e2e8f0;
    }

    .led-swatch:disabled,
    .led-off:disabled {
        opacity: 0.5;
        cursor: default;
    }

    .led-off {
        border: 1px solid #2f3b4a;
        border-radius: 0.3rem;
        background: #161c24;
        color: #94a3b8;
        font: inherit;
        font-size: 0.66rem;
        padding: 0 0.3rem;
        cursor: pointer;
    }

    .led-reply {
        color: #7f8ea3;
        font-size: 0.68rem;
        font-family: ui-monospace, monospace;
    }

    .led-reply.bad {
        color: #fca5a5;
    }

    .quiet-note {
        margin: 0.1rem 0 0;
        padding-left: 2.9rem;
        color: #fcd34d;
        font-size: 0.72rem;
        line-height: 1.35;
    }

    .note {
        margin: 0.3rem 0 0;
        color: #94a3b8;
        line-height: 1.4;
    }

    .note.subtle {
        color: #64748b;
        font-size: 0.72rem;
        border-top: 1px solid #1e2632;
        padding-top: 0.35rem;
    }
</style>
