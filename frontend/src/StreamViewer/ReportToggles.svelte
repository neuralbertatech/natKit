<script lang="ts">
    /**
     * Which sensor reports a node is collecting, and switches to change them.
     *
     * ⚠️ THE TRUTH COMES FROM THE DEVICE, NOT FROM THE DATA. A disabled sensor
     * and one that simply has not reported yet are identical in a frame -- both
     * are zeroed with a clear has_data bit -- so a control driven off the samples
     * would show "waiting" forever for something deliberately switched off. The
     * state here is whatever the device last answered and nothing else.
     *
     * ⚠️ AND IT IS NOT A RATE CONTROL. Turning a report off does not make the
     * others faster: the hub delivers its reports in bursts at ~88 Hz regardless
     * of how many are enabled or what rate they are asked for (TEC-NATKIT-41).
     * The reasons to turn one off are airtime, power, and not wanting the
     * channel. The wording below says so, because the obvious assumption is
     * wrong and would otherwise be made silently.
     */
    interface Props {
        streamId: string;
        // Sends a device command; returns false if it could not be sent.
        sendCommand: (
            streamId: string,
            command: string,
            args?: Record<string, unknown>,
        ) => boolean;
        // The most recent answer for this stream, or null.
        lastAnswer: { command: string; ok: boolean; message: string } | null;
        // A recording is running, so changes are refused server-side. Shown
        // rather than hidden: a disabled control with a reason beats a control
        // that silently fails.
        recording?: boolean;
    }

    let {
        streamId,
        sendCommand,
        lastAnswer,
        recording = false,
    }: Props = $props();

    const REPORTS = [
        { key: "accel", label: "Accelerometer" },
        { key: "gyro", label: "Gyroscope" },
        { key: "mag", label: "Magnetometer" },
        { key: "rotation", label: "Rotation" },
    ] as const;

    type ReportKey = (typeof REPORTS)[number]["key"];

    let known = $state<Record<ReportKey, boolean> | null>(null);
    let pending = $state(false);
    let error = $state<string | null>(null);

    /**
     * The device answers with "accel=1 gyro=1 mag=0 rotation=1".
     *
     * Parsed rather than sent as JSON because the answer travels on the device
     * log channel, whose records are a human-readable message by design -- the
     * same channel a person reads when asking why a node is quiet. Keeping one
     * format means the log stays readable instead of turning into a wire
     * protocol nobody can skim.
     */
    function parseReports(message: string): Record<ReportKey, boolean> | null {
        const found: Partial<Record<ReportKey, boolean>> = {};
        for (const report of REPORTS) {
            const match = message.match(new RegExp(`${report.key}=([01])`));
            if (!match) return null;
            found[report.key] = match[1] === "1";
        }
        return found as Record<ReportKey, boolean>;
    }

    $effect(() => {
        if (!lastAnswer) return;
        if (
            lastAnswer.command !== "get_reports" &&
            lastAnswer.command !== "set_reports"
        ) {
            return;
        }
        pending = false;
        const parsed = parseReports(lastAnswer.message);
        if (parsed) {
            known = parsed;
            // A refusal still reports the CURRENT state, which is why the error
            // and the state are both taken from the same answer.
            error = lastAnswer.ok ? null : lastAnswer.message;
        } else {
            error = lastAnswer.message;
        }
    });

    function refresh() {
        error = null;
        pending = sendCommand(streamId, "get_reports");
        if (!pending) error = "Not connected";
    }

    function toggle(key: ReportKey) {
        if (!known || recording) return;
        error = null;
        // Only the changed field is sent. The device starts from its current
        // mask, so this cannot accidentally reset the others -- and it means two
        // toggles in flight do not clobber each other.
        pending = sendCommand(streamId, "set_reports", { [key]: !known[key] });
        if (!pending) error = "Not connected";
    }
</script>

<div class="reports">
    <div class="head">
        <span class="title">Collected reports</span>
        <button onclick={refresh} disabled={pending}>
            {known ? "Refresh" : "Read from device"}
        </button>
    </div>

    {#if recording}
        <p class="note">
            A recording is in progress. Changing what a sensor collects would
            change the recording's schema partway through, so it is refused until
            the recording stops.
        </p>
    {/if}

    {#if known}
        <div class="toggles">
            {#each REPORTS as report}
                <label class:off={!known[report.key]}>
                    <input
                        type="checkbox"
                        checked={known[report.key]}
                        disabled={pending || recording}
                        onchange={() => toggle(report.key)}
                    />
                    {report.label}
                </label>
            {/each}
        </div>
        <p class="note">
            Turning a report off does not speed the others up — the sensor
            delivers all of them together in bursts. Use it to save airtime and
            power, not to gain rate.
        </p>
    {:else if !pending}
        <p class="note">
            The device has not been asked yet. This cannot be read from the data:
            a disabled sensor looks exactly like one that has not reported.
        </p>
    {/if}

    {#if pending}
        <p class="note">Waiting for the device…</p>
    {/if}
    {#if error}
        <p class="error">{error}</p>
    {/if}
</div>

<style>
    .reports {
        border-top: 1px solid var(--border, #d9e1dc);
        margin-top: 12px;
        padding-top: 10px;
    }
    .head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .title {
        font-weight: 600;
        font-size: 0.9rem;
    }
    .toggles {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 8px;
    }
    label {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 0.85rem;
    }
    label.off {
        opacity: 0.55;
    }
    .note {
        font-size: 0.75rem;
        opacity: 0.75;
        margin-top: 6px;
    }
    .error {
        font-size: 0.78rem;
        color: #9a3324;
        margin-top: 6px;
    }
    button {
        font-size: 0.8rem;
        padding: 3px 8px;
    }
</style>
