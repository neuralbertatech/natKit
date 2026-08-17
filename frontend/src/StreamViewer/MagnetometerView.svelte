<script lang="ts">
    /**
     * What the magnetometer is actually telling you.
     *
     * It measures the local magnetic field as a vector in microtesla. At rest
     * that is three nearly-constant numbers, which is why a rolling trace of
     * x/y/z shows three flat wiggly lines and conveys almost nothing. Everything
     * useful is DERIVED from the vector:
     *
     *   heading      where the horizontal part of the field points -- a compass
     *   strength     |B|, which should be ~25-65 uT anywhere on Earth
     *   dip          how steeply the field dives into the ground, a latitude fact
     *
     * ⚠️ STRENGTH IS THE HEALTH CHECK, not a measurement anyone wants. Earth's
     * field magnitude is essentially constant wherever you are standing, so if it
     * moves when you rotate the sensor, the reading is distorted -- by magnetised
     * metal fixed to the board (hard iron) or by the sensor being uncalibrated.
     * A heading computed from a distorted field is confidently wrong, so the
     * strength is shown next to the heading rather than buried.
     */
    import type { ImuVector3, ImuAccuracies } from "./types";

    interface Props {
        mag: ImuVector3;
        // Needed to know which way is down. A compass must be tilt-compensated:
        // the field points into the ground almost everywhere, so an un-levelled
        // sensor mixes that vertical component into the heading and the needle
        // swings wildly as you tip it.
        accel: ImuVector3;
        accuracies: ImuAccuracies;
        formatNumber: (num: number, decimals?: number) => string;
    }

    let { mag, accel, accuracies, formatNumber }: Props = $props();

    // Earth's field is 25-65 uT depending where you are. Outside that, something
    // local is dominating and nothing derived from the vector can be trusted.
    const EARTH_MIN_UT = 25;
    const EARTH_MAX_UT = 65;

    const strength = $derived(
        Math.sqrt(mag.x * mag.x + mag.y * mag.y + mag.z * mag.z),
    );

    const plausible = $derived(
        strength >= EARTH_MIN_UT && strength <= EARTH_MAX_UT,
    );

    /**
     * Tilt-compensated heading, the standard formulation: level the field using
     * roll and pitch from gravity, then take the angle of what is left in the
     * horizontal plane.
     */
    const derivedAngles = $derived.by(() => {
        const g = Math.sqrt(
            accel.x * accel.x + accel.y * accel.y + accel.z * accel.z,
        );
        if (g < 1e-6 || strength < 1e-6) {
            return { heading: null as number | null, dip: null as number | null };
        }
        const roll = Math.atan2(accel.y, accel.z);
        const pitch = Math.atan2(
            -accel.x,
            accel.y * Math.sin(roll) + accel.z * Math.cos(roll),
        );
        const xh =
            mag.x * Math.cos(pitch) +
            mag.y * Math.sin(roll) * Math.sin(pitch) +
            mag.z * Math.cos(roll) * Math.sin(pitch);
        const yh = mag.y * Math.cos(roll) - mag.z * Math.sin(roll);

        let heading = (Math.atan2(-yh, xh) * 180) / Math.PI;
        if (heading < 0) heading += 360;

        // Dip: how far the field tilts out of horizontal. Positive means it dives
        // downward, which is the northern hemisphere.
        const horizontal = Math.sqrt(xh * xh + yh * yh);
        const vertical = -(
            mag.x * -Math.sin(pitch) +
            mag.y * Math.sin(roll) * Math.cos(pitch) +
            mag.z * Math.cos(roll) * Math.cos(pitch)
        );
        const dip = (Math.atan2(vertical, horizontal) * 180) / Math.PI;
        return { heading, dip };
    });

    const heading = $derived(derivedAngles.heading);
    const dip = $derived(derivedAngles.dip);

    // ⚠️ The BNO08x reports magnetometer accuracy 0-3 and it starts at 0. It rises
    // only after the sensor has been moved through enough orientations for the
    // hub to solve for the hard-iron offset -- the "figure of eight" every phone
    // compass asks for. Until then the heading is a number, not a direction.
    const ACCURACY_LABEL = ["unreliable", "low", "medium", "high"];
    const calibrated = $derived(accuracies.magnetometer >= 2);

    // Where |B| sits within the plausible band, for the bar.
    const strengthPct = $derived(
        Math.max(
            0,
            Math.min(
                100,
                ((strength - EARTH_MIN_UT) / (EARTH_MAX_UT - EARTH_MIN_UT)) * 100,
            ),
        ),
    );

    const CARDINALS = [
        { label: "N", deg: 0 },
        { label: "E", deg: 90 },
        { label: "S", deg: 180 },
        { label: "W", deg: 270 },
    ];
</script>

<div class="mag">
    <div class="compass-wrap">
        <svg viewBox="-60 -60 120 120" class="compass" role="img"
             aria-label="Magnetic heading">
            <circle cx="0" cy="0" r="52" class="dial" />
            {#each Array(72) as _, i}
                <line
                    x1="0" y1="-52" x2="0" y2={i % 18 === 0 ? -44 : i % 6 === 0 ? -47 : -50}
                    class="tick"
                    transform="rotate({i * 5})"
                />
            {/each}
            {#each CARDINALS as c}
                <text
                    x={38 * Math.sin((c.deg * Math.PI) / 180)}
                    y={-38 * Math.cos((c.deg * Math.PI) / 180) + 4}
                    class="cardinal"
                    class:north={c.label === "N"}>{c.label}</text
                >
            {/each}
            {#if heading !== null}
                <!-- The needle points along the horizontal field, i.e. toward
                     magnetic north, so it rotates OPPOSITE to the heading. -->
                <g transform="rotate({-heading})" class:stale={!calibrated}>
                    <polygon points="0,-40 6,0 0,8 -6,0" class="needle-n" />
                    <polygon points="0,40 6,0 0,-8 -6,0" class="needle-s" />
                </g>
            {/if}
            <circle cx="0" cy="0" r="3" class="hub" />
        </svg>
        <div class="heading-readout">
            {#if heading === null}
                <span class="big muted">--</span>
            {:else}
                <span class="big">{formatNumber(heading, 0)}°</span>
            {/if}
            <span class="sub">magnetic heading</span>
        </div>
    </div>

    <div class="facts">
        <div class="fact">
            <span class="k">Field strength</span>
            <span class="v" class:bad={!plausible}>
                {formatNumber(strength, 1)} µT
            </span>
            <div class="bar" aria-hidden="true">
                <div class="band"></div>
                <div class="marker" style="left: {strengthPct}%"></div>
            </div>
            <span class="hint">
                {#if plausible}
                    Within Earth's {EARTH_MIN_UT}–{EARTH_MAX_UT} µT range. It
                    should stay put as you rotate the sensor — if it moves, the
                    reading is distorted.
                {:else}
                    ⚠️ Outside Earth's {EARTH_MIN_UT}–{EARTH_MAX_UT} µT range, so
                    something local dominates the field — magnetised metal on or
                    near the board. The heading is not trustworthy.
                {/if}
            </span>
        </div>

        <div class="fact">
            <span class="k">Dip angle</span>
            <span class="v"
                >{dip === null ? "--" : `${formatNumber(dip, 0)}°`}</span
            >
            <span class="hint">
                How steeply the field dives into the ground. Near 0° at the
                equator, ±90° at the poles — it is a property of where you are,
                not of the sensor, so it should barely move.
            </span>
        </div>

        <div class="fact">
            <span class="k">Calibration</span>
            <span class="v" class:bad={!calibrated}>
                {ACCURACY_LABEL[accuracies.magnetometer] ?? "?"}
            </span>
            <span class="hint">
                {#if calibrated}
                    The hub has solved for the fixed magnetic offset of the board
                    itself, so the heading is meaningful.
                {:else}
                    ⚠️ Not yet calibrated — the needle is dimmed. Move the sensor
                    through a figure of eight, turning it over as you go, until
                    this reads medium or high.
                {/if}
            </span>
        </div>
    </div>
</div>

<style>
    .mag {
        display: flex;
        gap: 22px;
        flex-wrap: wrap;
        align-items: flex-start;
        padding: 6px 2px;
    }
    .compass-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
    }
    .compass {
        width: 190px;
        height: 190px;
    }
    .dial {
        fill: var(--panel, #fff);
        stroke: #cfd8d3;
        stroke-width: 1.5;
    }
    .tick {
        stroke: #b9c5bf;
        stroke-width: 0.8;
    }
    .cardinal {
        font: 9px ui-monospace, monospace;
        text-anchor: middle;
        fill: #57655f;
    }
    .cardinal.north {
        fill: #b3261e;
        font-weight: 700;
    }
    .needle-n {
        fill: #b3261e;
    }
    .needle-s {
        fill: #8a9691;
    }
    .stale {
        opacity: 0.35;
    }
    .hub {
        fill: #57655f;
    }
    .heading-readout {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .big {
        font: 600 22px ui-monospace, monospace;
    }
    .big.muted {
        opacity: 0.4;
    }
    .sub {
        font-size: 0.72rem;
        opacity: 0.7;
    }
    .facts {
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-width: 260px;
        flex: 1;
    }
    .fact {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .k {
        font-size: 0.72rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        opacity: 0.7;
    }
    .v {
        font: 600 15px ui-monospace, monospace;
    }
    .v.bad {
        color: #9a3324;
    }
    .bar {
        position: relative;
        height: 6px;
        margin: 3px 0 1px;
        background: #e7ece9;
        border-radius: 3px;
    }
    .band {
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, #cfe6da, #9fd3ba, #cfe6da);
        border-radius: 3px;
    }
    .marker {
        position: absolute;
        top: -3px;
        width: 2px;
        height: 12px;
        background: #16211c;
        transform: translateX(-1px);
    }
    .hint {
        font-size: 0.72rem;
        opacity: 0.75;
        line-height: 1.35;
    }
</style>
