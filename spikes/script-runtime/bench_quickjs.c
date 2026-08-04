/* QuickJS embedded-script spike.
 *
 * Same three questions as the Lua harness, plus the one that motivated picking
 * QuickJS in the first place: does Float32Array marshalling actually beat plain
 * arrays by enough to matter at natKit's frame rates?
 */
#define _POSIX_C_SOURCE 199309L
#include <time.h>
#include "frame.h"
#include "quickjs.h"

/* Plain-array workload — the apples-to-apples comparison with Lua. */
static const char *SCRIPT_ARRAY =
    "function process(frame) {\n"
    "  const channels = [];\n"
    "  for (let c = 0; c < frame.channels.length; c++) {\n"
    "    const s = frame.channels[c].samples;\n"
    "    let sum = 0.0;\n"
    "    for (let i = 0; i < s.length; i++) { const v = Math.abs(s[i]); sum += v * v; }\n"
    "    channels.push({ label: frame.channels[c].label,\n"
    "                    samples: [Math.sqrt(sum / s.length)] });\n"
    "  }\n"
    "  return { channels };\n"
    "}\n";

/* Identical logic, but samples arrive as Float32Array. */
static const char *SCRIPT_TYPED =
    "function process(frame) {\n"
    "  const channels = [];\n"
    "  for (let c = 0; c < frame.channels.length; c++) {\n"
    "    const s = frame.channels[c].samples;\n"
    "    let sum = 0.0;\n"
    "    for (let i = 0; i < s.length; i++) { const v = Math.abs(s[i]); sum += v * v; }\n"
    "    channels.push({ label: frame.channels[c].label,\n"
    "                    samples: [Math.sqrt(sum / s.length)] });\n"
    "  }\n"
    "  return { channels };\n"
    "}\n";

/* --- Interrupt ------------------------------------------------------------- */
typedef struct { double deadline_ms; int fired; } Deadline;

static int interrupt_handler(JSRuntime *rt, void *opaque)
{
    (void)rt;
    Deadline *d = (Deadline *)opaque;
    if (spike_now_ms() > d->deadline_ms) { d->fired = 1; return 1; }
    return 0;
}

/* --- Sandbox ---------------------------------------------------------------
 * Nothing to strip. Core QuickJS has NO I/O: std/os live in quickjs-libc, which
 * this harness never links or registers. There is no fs, no network, no process
 * in the context to begin with. */
static JSRuntime *new_runtime(size_t memory_limit)
{
    JSRuntime *rt = JS_NewRuntime();
    if (memory_limit) JS_SetMemoryLimit(rt, memory_limit);
    JS_SetMaxStackSize(rt, 1024u * 1024);
    return rt;
}

/* --- Marshalling ----------------------------------------------------------- */
static JSValue frame_to_js(JSContext *ctx, const SpikeFrame *f, int typed)
{
    JSValue frame = JS_NewObject(ctx);
    JS_SetPropertyStr(ctx, frame, "device_id", JS_NewString(ctx, f->device_id));
    JS_SetPropertyStr(ctx, frame, "seq_no", JS_NewInt64(ctx, f->seq_no));
    JS_SetPropertyStr(ctx, frame, "device_ts_us", JS_NewInt64(ctx, f->device_ts_us));
    JS_SetPropertyStr(ctx, frame, "sample_rate_hz", JS_NewFloat64(ctx, f->sample_rate_hz));

    JSValue channels = JS_NewArray(ctx);
    for (int ch = 0; ch < f->n_channels; ch++) {
        JSValue channel = JS_NewObject(ctx);
        JS_SetPropertyStr(ctx, channel, "label",
                          JS_NewString(ctx, f->channels[ch].label));
        int n = f->channels[ch].n_samples;

        if (typed) {
            /* Copy into a Float32Array via an ArrayBuffer. One bulk memcpy
             * instead of n property sets. */
            float *tmp = (float *)malloc(sizeof(float) * (size_t)n);
            for (int i = 0; i < n; i++) tmp[i] = (float)f->channels[ch].samples[i];
            JSValue buf = JS_NewArrayBufferCopy(ctx, (const uint8_t *)tmp,
                                                sizeof(float) * (size_t)n);
            free(tmp);
            JSValue argv[1] = { buf };
            JSValue arr = JS_NewTypedArray(ctx, 1, argv, JS_TYPED_ARRAY_FLOAT32);
            JS_FreeValue(ctx, buf);
            JS_SetPropertyStr(ctx, channel, "samples", arr);
        } else {
            JSValue samples = JS_NewArray(ctx);
            for (int i = 0; i < n; i++)
                JS_SetPropertyUint32(ctx, samples, (uint32_t)i,
                                     JS_NewFloat64(ctx, f->channels[ch].samples[i]));
            JS_SetPropertyStr(ctx, channel, "samples", samples);
        }
        JS_SetPropertyUint32(ctx, channels, (uint32_t)ch, channel);
    }
    JS_SetPropertyStr(ctx, frame, "channels", channels);
    return frame;
}

static int js_to_result(JSContext *ctx, JSValueConst result, double *out, int max)
{
    JSValue channels = JS_GetPropertyStr(ctx, result, "channels");
    if (JS_IsException(channels) || !JS_IsArray(ctx, channels)) {
        JS_FreeValue(ctx, channels); return -1;
    }
    JSValue len_v = JS_GetPropertyStr(ctx, channels, "length");
    uint32_t len = 0; JS_ToUint32(ctx, &len, len_v); JS_FreeValue(ctx, len_v);
    int n = (int)len; if (n > max) n = max;
    for (int i = 0; i < n; i++) {
        JSValue ch = JS_GetPropertyUint32(ctx, channels, (uint32_t)i);
        JSValue samples = JS_GetPropertyStr(ctx, ch, "samples");
        JSValue first = JS_GetPropertyUint32(ctx, samples, 0);
        JS_ToFloat64(ctx, &out[i], first);
        JS_FreeValue(ctx, first); JS_FreeValue(ctx, samples); JS_FreeValue(ctx, ch);
    }
    JS_FreeValue(ctx, channels);
    return n;
}

/* --- Tests ----------------------------------------------------------------- */

static int test_interrupt(void)
{
    Deadline d = {spike_now_ms() + 200.0, 0};
    JSRuntime *rt = new_runtime(64u * 1024 * 1024);
    JS_SetInterruptHandler(rt, interrupt_handler, &d);
    JSContext *ctx = JS_NewContext(rt);

    double t0 = spike_now_ms();
    const char *src = "let x = 0; while (true) { x++; }";
    JSValue r = JS_Eval(ctx, src, strlen(src), "<loop>", JS_EVAL_TYPE_GLOBAL);
    double elapsed = spike_now_ms() - t0;
    int aborted = JS_IsException(r);
    JS_FreeValue(ctx, r);

    printf("  infinite loop      : %s after %.1f ms  (wall-clock deadline, handler fired=%d)\n",
           aborted ? "ABORTED" : "STILL RUNNING - FAIL", elapsed, d.fired);
    JS_FreeContext(ctx); JS_FreeRuntime(rt);
    return aborted;
}

static int test_memory_cap(void)
{
    JSRuntime *rt = new_runtime(8u * 1024 * 1024);
    JSContext *ctx = JS_NewContext(rt);
    const char *src = "const a = []; while (true) { a.push(new Array(1024).fill(1)); }";
    JSValue r = JS_Eval(ctx, src, strlen(src), "<alloc>", JS_EVAL_TYPE_GLOBAL);
    int denied = JS_IsException(r);
    if (denied) {
        JSValue e = JS_GetException(ctx);
        const char *msg = JS_ToCString(ctx, e);
        printf("  runaway alloc      : DENIED cleanly (cap 8 MB) — %s\n",
               msg ? msg : "?");
        JS_FreeCString(ctx, msg); JS_FreeValue(ctx, e);
    } else {
        printf("  runaway alloc      : UNBOUNDED - FAIL\n");
    }
    JS_FreeValue(ctx, r);
    JS_FreeContext(ctx); JS_FreeRuntime(rt);
    return denied;
}

static int test_sandbox(void)
{
    JSRuntime *rt = new_runtime(32u * 1024 * 1024);
    JSContext *ctx = JS_NewContext(rt);
    const char *escapes[] = {
        "std.open('/etc/passwd', 'r')",
        "os.exec(['id'])",
        "require('fs')",
        "fetch('http://example.com')",
        "process.env.HOME",
        "globalThis.process.exit(0)",
        "new (globalThis.Function)('return this')().require",
        NULL
    };
    int denied = 0, total = 0;
    for (const char **e = escapes; *e; e++) {
        total++;
        JSValue r = JS_Eval(ctx, *e, strlen(*e), "<escape>", JS_EVAL_TYPE_GLOBAL);
        if (JS_IsException(r)) { denied++; JSValue ex = JS_GetException(ctx); JS_FreeValue(ctx, ex); }
        else {
            /* Undefined is also a denial — the capability simply is not there. */
            if (JS_IsUndefined(r)) denied++;
            else printf("    !! ALLOWED: %s\n", *e);
        }
        JS_FreeValue(ctx, r);
    }
    printf("  host escapes       : %d/%d denied (core QuickJS registers no I/O at all)\n",
           denied, total);
    JS_FreeContext(ctx); JS_FreeRuntime(rt);
    return denied == total;
}

static void bench_case_opts(const SpikeCase *c, int iterations, int typed, int with_interrupt)
{
    JSRuntime *rt = new_runtime(256u * 1024 * 1024);
    Deadline guard = {0, 0};
    if (with_interrupt) {
        /* A per-frame wall-clock budget — what you would actually run in
         * production. Note this differs from Lua's instruction budget: it is
         * non-deterministic but directly expresses "kill it if it takes too
         * long", which is the real requirement. */
        guard.deadline_ms = spike_now_ms() + 1.0e9;
        JS_SetInterruptHandler(rt, interrupt_handler, &guard);
    }
    JSContext *ctx = JS_NewContext(rt);
    const char *src = typed ? SCRIPT_TYPED : SCRIPT_ARRAY;
    JSValue load = JS_Eval(ctx, src, strlen(src), "<script>", JS_EVAL_TYPE_GLOBAL);
    if (JS_IsException(load)) { printf("  script load failed\n"); goto done; }
    JS_FreeValue(ctx, load);

    JSValue global = JS_GetGlobalObject(ctx);
    JSValue fn = JS_GetPropertyStr(ctx, global, "process");

    SpikeFrame *f = spike_frame_new(c);
    double *expected = (double *)malloc(sizeof(double) * (size_t)c->n_channels);
    double *got = (double *)malloc(sizeof(double) * (size_t)c->n_channels);
    spike_reference_rms(f, expected);

    for (int i = 0; i < 50; i++) {
        JSValue arg = frame_to_js(ctx, f, typed);
        JSValue r = JS_Call(ctx, fn, global, 1, (JSValueConst *)&arg);
        JS_FreeValue(ctx, r); JS_FreeValue(ctx, arg);
    }

    double marshal_ms = 0.0, total_ms = 0.0;
    for (int i = 0; i < iterations; i++) {
        double t0 = spike_now_ms();
        JSValue arg = frame_to_js(ctx, f, typed);
        double t1 = spike_now_ms();
        JSValue r = JS_Call(ctx, fn, global, 1, (JSValueConst *)&arg);
        if (JS_IsException(r)) { printf("  call threw\n"); JS_FreeValue(ctx, r); JS_FreeValue(ctx, arg); break; }
        js_to_result(ctx, r, got, c->n_channels);
        JS_FreeValue(ctx, r); JS_FreeValue(ctx, arg);
        double t2 = spike_now_ms();
        marshal_ms += t1 - t0;
        total_ms += t2 - t0;
    }

    double max_err = 0.0;
    for (int ch = 0; ch < c->n_channels; ch++) {
        double e = fabs(got[ch] - expected[ch]);
        if (e > max_err) max_err = e;
    }
    double per_frame = total_ms / iterations;
    printf("  %-11s %6d floats | %7.3f ms/frame (marshal %5.3f) | %8.0f frames/s | err %.2e\n",
           c->name, spike_total_samples(c), per_frame,
           marshal_ms / iterations, 1000.0 / per_frame, max_err);

    free(expected); free(got); spike_frame_free(f);
    JS_FreeValue(ctx, fn); JS_FreeValue(ctx, global);
done:
    JS_FreeContext(ctx); JS_FreeRuntime(rt);
}

static void bench_case(const SpikeCase *c, int iterations, int typed)
{
    bench_case_opts(c, iterations, typed, 0);
}

int main(void)
{
    printf("=== QuickJS (bellard 2025-04-26) ===\n\n");
    printf("Safety:\n");
    int ok = 1;
    ok &= test_sandbox();
    ok &= test_interrupt();
    ok &= test_memory_cap();

    printf("\nThroughput, plain arrays (rectify + per-channel RMS):\n");
    for (int i = 0; i < SPIKE_CASE_COUNT; i++)
        bench_case(&SPIKE_CASES[i], 2000, 0);

    printf("\nThroughput, Float32Array samples:\n");
    for (int i = 0; i < SPIKE_CASE_COUNT; i++)
        bench_case(&SPIKE_CASES[i], 2000, 1);

    printf("\nFloat32Array WITH the interrupt handler installed (production config):\n");
    for (int i = 0; i < SPIKE_CASE_COUNT; i++)
        bench_case_opts(&SPIKE_CASES[i], 2000, 1, 1);

    printf("\nSafety verdict: %s\n", ok ? "all three controls work" : "A CONTROL FAILED");
    return ok ? 0 : 1;
}
