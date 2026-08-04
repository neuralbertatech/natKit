<script lang="ts">
    import { onMount } from "svelte";
    import type { ImuQuaternion } from "./types";

    interface Props {
        quat: ImuQuaternion;
        formatNumber: (num: number, decimals?: number) => string;
    }

    let { quat, formatNumber }: Props = $props();

    type Vec3 = [number, number, number];
    type Quat = { w: number; x: number; y: number; z: number };
    type UpAxis = "x" | "y" | "z";

    // --- config (persisted so the user configures it once) --------------------
    const UP_KEY = "natkit.imu.orientation.up";
    const REF_KEY = "natkit.imu.orientation.ref";

    function loadUpAxis(): UpAxis {
        try {
            const v = localStorage.getItem(UP_KEY);
            if (v === "x" || v === "y" || v === "z") return v;
        } catch {
            /* ignore */
        }
        return "z"; // BNO08x reference frame is Z-up (gravity along Z)
    }
    function loadRef(): Quat | null {
        try {
            const v = localStorage.getItem(REF_KEY);
            if (v) return JSON.parse(v) as Quat;
        } catch {
            /* ignore */
        }
        return null;
    }

    let upAxis = $state<UpAxis>(loadUpAxis());
    let refQuat = $state<Quat | null>(loadRef());

    $effect(() => {
        try {
            localStorage.setItem(UP_KEY, upAxis);
        } catch {
            /* ignore */
        }
    });
    $effect(() => {
        try {
            if (refQuat) localStorage.setItem(REF_KEY, JSON.stringify(refQuat));
            else localStorage.removeItem(REF_KEY);
        } catch {
            /* ignore */
        }
    });

    // --- vector / quaternion math --------------------------------------------
    function cross(a: Vec3, b: Vec3): Vec3 {
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ];
    }
    function dot(a: Vec3, b: Vec3): number {
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }
    function normalize(a: Vec3): Vec3 {
        const len = Math.hypot(a[0], a[1], a[2]) || 1;
        return [a[0] / len, a[1] / len, a[2] / len];
    }
    function qConj(q: Quat): Quat {
        return { w: q.w, x: -q.x, y: -q.y, z: -q.z };
    }
    function qMul(a: Quat, b: Quat): Quat {
        return {
            w: a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
            x: a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
            y: a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
            z: a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        };
    }
    // Rotate a body vector into the (sensor) world frame by a unit quaternion.
    function rotate(q: Quat, v: Vec3): Vec3 {
        const tx = 2 * (q.y * v[2] - q.z * v[1]);
        const ty = 2 * (q.z * v[0] - q.x * v[2]);
        const tz = 2 * (q.x * v[1] - q.y * v[0]);
        return [
            v[0] + q.w * tx + (q.y * tz - q.z * ty),
            v[1] + q.w * ty + (q.z * tx - q.x * tz),
            v[2] + q.w * tz + (q.x * ty - q.y * tx),
        ];
    }
    // Remap a sensor-world vector into the DISPLAY frame so the chosen "up" axis
    // becomes the view's vertical (+Y). This is what makes a flat-on-desk spin
    // read as a spin in the horizontal plane instead of 90° off.
    function remap(v: Vec3): Vec3 {
        if (upAxis === "z") return [v[0], v[2], -v[1]]; // +Z → +Y
        if (upAxis === "x") return [-v[1], v[0], v[2]]; // +X → +Y
        return v; // "y" → identity
    }

    // --- camera (fixed 3/4 orthographic; display-frame Y is up) --------------
    const AZ = -0.62;
    const EL = 0.42;
    const eye = normalize([
        Math.cos(EL) * Math.cos(AZ),
        Math.sin(EL),
        Math.cos(EL) * Math.sin(AZ),
    ]);
    const camRight = normalize(cross([0, 1, 0], eye));
    const camUp = cross(eye, camRight);
    function project(p: Vec3): { x: number; y: number; d: number } {
        return { x: dot(p, camRight), y: dot(p, camUp), d: dot(p, eye) };
    }

    // Displayed orientation = incoming quat made relative to the reference pose
    // (if "set level" was used), normalized.
    const qDisplay = $derived.by<Quat>(() => {
        const len = Math.hypot(quat.real, quat.i, quat.j, quat.k) || 1;
        const nq: Quat = {
            w: quat.real / len,
            x: quat.i / len,
            y: quat.j / len,
            z: quat.k / len,
        };
        return refQuat ? qMul(qConj(refQuat), nq) : nq;
    });

    // Aerospace ZYX Euler angles (deg) of the displayed orientation.
    const euler = $derived.by(() => {
        const { w, x, y, z } = qDisplay;
        const clamp = (v: number) => Math.max(-1, Math.min(1, v));
        const roll = Math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y));
        const pitch = Math.asin(clamp(2 * (w * y - z * x)));
        const yaw = Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z));
        const deg = 180 / Math.PI;
        return { roll: roll * deg, pitch: pitch * deg, yaw: yaw * deg };
    });

    let canvas = $state<HTMLCanvasElement | null>(null);
    let ctx: CanvasRenderingContext2D | null = null;

    function draw(): void {
        if (!canvas || !ctx) return;
        const dpr = window.devicePixelRatio || 1;
        const cw = canvas.clientWidth || 280;
        const ch = canvas.clientHeight || 240;
        if (
            canvas.width !== Math.round(cw * dpr) ||
            canvas.height !== Math.round(ch * dpr)
        ) {
            canvas.width = Math.round(cw * dpr);
            canvas.height = Math.round(ch * dpr);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cw, ch);

        const cx = cw / 2;
        const cy = ch / 2;
        const R = Math.min(cw, ch) * 0.4;
        const toPx = (p: Vec3) => {
            const s = project(p);
            return { px: cx + s.x * R, py: cy - s.y * R, d: s.d };
        };

        // Sphere body.
        const grad = ctx.createRadialGradient(
            cx - R * 0.35,
            cy - R * 0.35,
            R * 0.2,
            cx,
            cy,
            R,
        );
        grad.addColorStop(0, "#f8fafc");
        grad.addColorStop(1, "#dbe3ee");
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, 2 * Math.PI);
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.strokeStyle = "#cbd5e1";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Grid great circles (equator = display horizontal plane, one meridian).
        const greatCircle = (a: Vec3, b: Vec3) => {
            for (const front of [false, true]) {
                ctx!.beginPath();
                let started = false;
                for (let i = 0; i <= 72; i += 1) {
                    const t = (i / 72) * 2 * Math.PI;
                    const cosT = Math.cos(t);
                    const sinT = Math.sin(t);
                    const p: Vec3 = [
                        a[0] * cosT + b[0] * sinT,
                        a[1] * cosT + b[1] * sinT,
                        a[2] * cosT + b[2] * sinT,
                    ];
                    const pt = toPx(p);
                    if (pt.d >= 0 !== front) {
                        started = false;
                        continue;
                    }
                    if (!started) {
                        ctx!.moveTo(pt.px, pt.py);
                        started = true;
                    } else {
                        ctx!.lineTo(pt.px, pt.py);
                    }
                }
                ctx!.strokeStyle = "#94a3b8";
                ctx!.lineWidth = 1;
                ctx!.globalAlpha = front ? 0.7 : 0.22;
                ctx!.setLineDash(front ? [] : [3, 3]);
                ctx!.stroke();
            }
            ctx!.globalAlpha = 1;
            ctx!.setLineDash([]);
        };
        greatCircle([1, 0, 0], [0, 0, 1]); // horizontal plane in display frame
        greatCircle([1, 0, 0], [0, 1, 0]); // vertical meridian

        // Body axes, rotated by the orientation then remapped into display frame.
        // +X is the bold "pointing" arrow; +Y/+Z are faint reference axes.
        const axes: { v: Vec3; color: string; bold: boolean }[] = [
            { v: [1, 0, 0], color: "#dc2626", bold: true },
            { v: [0, 1, 0], color: "#16a34a", bold: false },
            { v: [0, 0, 1], color: "#2563eb", bold: false },
        ];
        const drawn = axes
            .map((axis) => {
                const dir = normalize(remap(rotate(qDisplay, axis.v)));
                return { ...axis, pt: toPx(dir) };
            })
            .sort((l, r) => l.pt.d - r.pt.d);

        for (const axis of drawn) {
            ctx.globalAlpha = axis.pt.d >= 0 ? 1 : 0.3;
            ctx.strokeStyle = axis.color;
            ctx.fillStyle = axis.color;
            ctx.lineWidth = axis.bold ? 3 : 1.5;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(axis.pt.px, axis.pt.py);
            ctx.stroke();
            const ang = Math.atan2(axis.pt.py - cy, axis.pt.px - cx);
            const hl = axis.bold ? 13 : 8;
            const spread = 0.42;
            ctx.beginPath();
            ctx.moveTo(axis.pt.px, axis.pt.py);
            ctx.lineTo(
                axis.pt.px - hl * Math.cos(ang - spread),
                axis.pt.py - hl * Math.sin(ang - spread),
            );
            ctx.lineTo(
                axis.pt.px - hl * Math.cos(ang + spread),
                axis.pt.py - hl * Math.sin(ang + spread),
            );
            ctx.closePath();
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    }

    // Throttle redraws to ~30 fps; also re-runs when the config changes.
    let lastDrawMs = 0;
    $effect(() => {
        qDisplay;
        upAxis;
        const now = Date.now();
        if (now - lastDrawMs < 33) return;
        lastDrawMs = now;
        draw();
    });

    onMount(() => {
        ctx = canvas?.getContext("2d") ?? null;
        draw();
        let ro: ResizeObserver | null = null;
        if (canvas && typeof ResizeObserver !== "undefined") {
            ro = new ResizeObserver(() => draw());
            ro.observe(canvas);
        }
        return () => ro?.disconnect();
    });

    function setLevel() {
        const len = Math.hypot(quat.real, quat.i, quat.j, quat.k) || 1;
        refQuat = {
            w: quat.real / len,
            x: quat.i / len,
            y: quat.j / len,
            z: quat.k / len,
        };
    }
</script>

<div class="orientation">
    <div class="controls">
        <div class="control-group" aria-label="Up axis">
            <span class="control-label">Up</span>
            {#each ["x", "y", "z"] as ax}
                <button
                    type="button"
                    class:selected={upAxis === ax}
                    onclick={() => (upAxis = ax as UpAxis)}
                    title="Which sensor axis points up in the view"
                >
                    {ax.toUpperCase()}
                </button>
            {/each}
        </div>
        <div class="control-group">
            <button
                type="button"
                onclick={setLevel}
                title="Use the board's current pose as the neutral 'level' reference"
            >
                Set level
            </button>
            <button
                type="button"
                disabled={!refQuat}
                onclick={() => (refQuat = null)}
                title="Clear the reference pose"
            >
                Reset
            </button>
        </div>
    </div>

    <canvas bind:this={canvas}></canvas>

    <div class="euler">
        <div class="axis-key">
            <span class="dot x"></span>X (arrow)
            <span class="dot y"></span>Y
            <span class="dot z"></span>Z
            {#if refQuat}<span class="leveled">· leveled</span>{/if}
        </div>
        <div class="angles">
            <div><span class="label">Roll</span>{formatNumber(euler.roll, 1)}°</div>
            <div>
                <span class="label">Pitch</span>{formatNumber(euler.pitch, 1)}°
            </div>
            <div><span class="label">Yaw</span>{formatNumber(euler.yaw, 1)}°</div>
        </div>
    </div>
</div>

<style>
    .orientation {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        height: 100%;
        min-height: 0;
    }

    .controls {
        display: flex;
        justify-content: space-between;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .control-group {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
    }

    .control-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        color: #64748b;
        margin-right: 0.15rem;
    }

    .control-group button {
        border: 1px solid #dbe3ee;
        background: #f8fafc;
        color: #475569;
        border-radius: 6px;
        padding: 0.25rem 0.55rem;
        font-size: 0.78rem;
        cursor: pointer;
    }

    .control-group button.selected {
        background: #e2e8f0;
        color: #0f172a;
        font-weight: 600;
        border-color: #cbd5e1;
    }

    .control-group button:disabled {
        opacity: 0.5;
        cursor: default;
    }

    canvas {
        flex: 1 1 auto;
        width: 100%;
        min-height: 0;
    }

    .euler {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
    }

    .axis-key {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.75rem;
        color: #64748b;
    }

    .leveled {
        color: #047857;
        font-weight: 600;
    }

    .dot {
        display: inline-block;
        width: 0.6rem;
        height: 0.6rem;
        border-radius: 50%;
        margin-left: 0.5rem;
    }
    .dot.x {
        background: #dc2626;
    }
    .dot.y {
        background: #16a34a;
    }
    .dot.z {
        background: #2563eb;
    }

    .angles {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.5rem;
        font-family: ui-monospace, monospace;
        font-size: 0.9rem;
        color: #0f172a;
    }

    .label {
        display: block;
        color: #64748b;
        font-size: 0.72rem;
        text-transform: uppercase;
        font-family: system-ui, sans-serif;
    }
</style>
