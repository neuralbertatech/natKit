# Spike: embeddable script runtime for natKit script nodes

Settles, with numbers, which interpreter to embed in the C++ transform worker so a
script node's body can be user-authored code. Run it:

```bash
make run      # both harnesses
make sizes    # stripped static binary sizes
```

Self-contained — vendors its own Lua and QuickJS under `vendor/`, touches nothing
in `libnatkit`.

## What it measures

Three safety controls (the things SCI and CPython cannot do), plus throughput
against realistic frame sizes:

| case | shape | frames/sec a real board produces |
|---|---|---|
| `emg-small` | 3ch × 50 @ 500 Hz | 10 |
| `emg-window` | 8ch × 256 @ 1 kHz | ~4 |
| `eeg-wide` | 32ch × 1024 @ 1 kHz | ~1 |

Workload is rectify-then-per-channel-RMS — representative of real feature
extraction. Every result is checked against a C reference implementation; both
engines matched it exactly (max error `0.00e+00` in all cases).

## Results

### Safety — both engines pass all three

| | host escapes denied | infinite loop | runaway allocation |
|---|---|---|---|
| **Lua 5.4.7** | 6/6 | **aborted @ 27.5 ms** (instruction budget) | **denied cleanly** (capping allocator) |
| **QuickJS** | 7/7 | **aborted @ 200 ms** (wall-clock deadline) | **denied cleanly** (`JS_SetMemoryLimit`) |

Neither needed anything exotic. Lua: open only `base`/`table`/`string`/`math`, drop
`load`/`dofile`/`loadfile`, and `io`/`os`/`package`/`debug` simply never exist in
the state. QuickJS: core `quickjs.c` registers *no* I/O at all — `std`/`os` live in
`quickjs-libc`, which you just don't link.

Note the two interrupt mechanisms differ in kind. Lua's is an **instruction
budget** (deterministic, reproducible per frame). QuickJS's is a **wall-clock
deadline** (non-deterministic, but directly expresses "kill it if it takes longer
than X", which is the actual requirement).

### Throughput — ms per frame, lower is better

| case | floats | needed | Lua | QuickJS<br>plain arrays | QuickJS<br>Float32Array | QuickJS F32<br>+ interrupt |
|---|---|---|---|---|---|---|
| `emg-small` | 150 | 10/s | 0.005 | 0.017 | **0.004** | **0.003** |
| `emg-window` | 2048 | ~4/s | 0.050 | 0.178 | **0.009** | **0.010** |
| `eeg-wide` | 32768 | ~1/s | 0.668 | 2.773 | **0.050** | **0.050** |

### Interrupt overhead — the surprise

| | without interrupt | with interrupt | cost |
|---|---|---|---|
| Lua (`emg-window`) | 0.050 ms | 0.088 ms | **+76%** |
| QuickJS F32 (`emg-window`) | 0.009 ms | 0.010 ms | **~0%** (noise) |

Lua's count hook fires every N VM instructions and calls into C; QuickJS's handler
is polled by the interpreter loop far more cheaply. Since the interrupt is **not
optional in production**, Lua's real production figure is 0.088 ms/frame, not
0.050 — which makes QuickJS+Float32Array about **9× faster than
production-configured Lua** on the mid case.

### Binary size (stripped, static, harness + engine)

| Lua | QuickJS |
|---|---|
| 220 K | 820 K |

## Conclusions

**1. Performance is not the deciding factor for feasibility.** Even the slowest
configuration measured (QuickJS plain arrays on `eeg-wide`, 2.77 ms/frame) has
~360× headroom over the ~1 frame/s that case actually produces. natKit's frame
rates are low; nothing here is close to a bottleneck.

**2. But the margin matters where headroom shrinks** — many script nodes on one
worker slot, or per-sample work heavier than RMS (FFT, resampling, convolution).
That is where 5–13× is the difference between comfortable and not.

**3. Float32Array is decisive, and it is the whole QuickJS case.** With plain JS
arrays QuickJS is 3.5–4× *slower* than Lua. With `Float32Array` it is 5.5× faster
at 2 K floats and 13× at 32 K. **Implementation constraint: samples must cross the
boundary as `Float32Array`, never as JS arrays.** Construction is a single
`JS_NewArrayBufferCopy` + `JS_NewTypedArray` — one bulk memcpy instead of *n*
property sets.

**4. Lua's mandatory interrupt tax is real and QuickJS's is not.** This flips the
intuition — Lua has the simpler C API and the more proven sandbox, but you pay 76%
for the one control you cannot ship without.

## Recommendation: QuickJS with Float32Array samples

1. Its interrupt is effectively free; Lua's costs 76%, and the interrupt is not optional.
2. TypedArrays give 5–13× headroom where it matters, and map 1:1 onto the sample
   buffers natKit already has.
3. JS is more widely known, and the same script would run natively in a browser if
   a preview/scratch venue is ever wanted.

Costs: 820 K vs 220 K of binary, and a somewhat more verbose C API.

**Lua stays a defensible choice** if binary size or C-API simplicity dominates.
But note that the "I want a Lisp" argument does *not* favour it: Fennel compiles
to Lua and therefore inherits the 76% hook tax, whereas `squint`/`cherry` compile
Clojure-flavoured source to plain JS at zero runtime cost. A Lisp surface is
available on both sides, and it is cheaper on the QuickJS side.

## Bugs this spike found in its own harness

Worth recording, because both are the kind of thing that would have been a
production crash rather than a test failure:

- **Capping allocator underflow.** Computing `used + nsize - osize` in `size_t`
  wraps when `nsize < osize`, so a *shrinking* realloc got denied — and denying a
  shrink leaves Lua in a state it cannot recover from. It core-dumped. Only a
  growth can breach a cap; compare growth alone.
- `_POSIX_C_SOURCE` hides `M_PI`, which is an X/Open extension.
