/* Lua 5.4 embedded-script spike.
 *
 * Answers, with numbers rather than judgement:
 *   1. marshalling + execution cost for a realistic natKit frame
 *   2. does lua_sethook(LUA_MASKCOUNT) actually abort an infinite loop?
 *   3. does a capping allocator actually stop runaway memory, cleanly?
 */
#define _POSIX_C_SOURCE 199309L
#include <time.h>
#include "frame.h"
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

/* The benchmark workload: rectify, then per-channel RMS. */
static const char *SCRIPT =
    "function process(frame)\n"
    "  local out = { channels = {} }\n"
    "  for i, ch in ipairs(frame.channels) do\n"
    "    local s = ch.samples\n"
    "    local n = #s\n"
    "    local sum = 0.0\n"
    "    for j = 1, n do\n"
    "      local v = s[j]\n"
    "      if v < 0 then v = -v end\n"
    "      sum = sum + v * v\n"
    "    end\n"
    "    out.channels[i] = { label = ch.label, samples = { math.sqrt(sum / n) } }\n"
    "  end\n"
    "  return out\n"
    "end\n";

/* --- Memory cap -------------------------------------------------------------
 * Lua takes its allocator at state creation, so a hard cap is a few lines and
 * Lua turns a NULL return into a catchable memory error. */
typedef struct { size_t used; size_t limit; int denied; } LuaBudget;

static void *capped_alloc(void *ud, void *ptr, size_t osize, size_t nsize)
{
    LuaBudget *b = (LuaBudget *)ud;

    if (nsize == 0) {
        b->used -= (osize <= b->used) ? osize : b->used;
        free(ptr);
        return NULL;
    }

    /* Only a GROWTH can breach the cap. Computing `used + nsize - osize` in
     * size_t underflows when nsize < osize, wrapping to a huge value, which
     * denies a *shrinking* realloc — and denying a shrink leaves Lua in a state
     * it is not built to recover from (it core-dumped). Compare growth only. */
    if (nsize > osize) {
        size_t growth = nsize - osize;
        if (b->used + growth > b->limit) { b->denied = 1; return NULL; }
    }

    void *np = realloc(ptr, nsize);
    if (!np) return NULL;
    if (nsize > osize) b->used += nsize - osize;
    else b->used -= osize - nsize;
    return np;
}

/* --- Instruction budget ----------------------------------------------------- */
typedef struct { long long budget; long long used; } LuaClock;
static LuaClock g_clock;

static void count_hook(lua_State *L, lua_Debug *ar)
{
    (void)ar;
    g_clock.used += 1000;
    if (g_clock.used > g_clock.budget)
        luaL_error(L, "instruction budget exceeded");
}

/* --- Sandbox ---------------------------------------------------------------
 * Open only the libraries a script legitimately needs. io / os / package /
 * debug are simply never opened, so there is no ambient authority to escape
 * from — `require`, `io.open`, `os.execute` are not merely blocked, they do not
 * exist in the state. */
static void open_sandboxed_libs(lua_State *L)
{
    static const luaL_Reg libs[] = {
        {LUA_GNAME,      luaopen_base},
        {LUA_TABLIBNAME, luaopen_table},
        {LUA_STRLIBNAME, luaopen_string},
        {LUA_MATHLIBNAME, luaopen_math},
        {NULL, NULL}
    };
    for (const luaL_Reg *lib = libs; lib->func; lib++) {
        luaL_requiref(L, lib->name, lib->func, 1);
        lua_pop(L, 1);
    }
    /* Even in base, a few names are host-reaching or state-breaking. */
    const char *drop[] = {"dofile", "loadfile", "load", "collectgarbage", NULL};
    for (const char **n = drop; *n; n++) {
        lua_pushnil(L);
        lua_setglobal(L, *n);
    }
}

static lua_State *new_state(LuaBudget *budget)
{
    lua_State *L = lua_newstate(capped_alloc, budget);
    if (!L) return NULL;
    open_sandboxed_libs(L);
    return L;
}

/* --- Marshalling ----------------------------------------------------------- */
static void push_frame(lua_State *L, const SpikeFrame *f)
{
    lua_createtable(L, 0, 5);
    lua_pushstring(L, f->device_id);       lua_setfield(L, -2, "device_id");
    lua_pushinteger(L, f->seq_no);         lua_setfield(L, -2, "seq_no");
    lua_pushinteger(L, f->device_ts_us);   lua_setfield(L, -2, "device_ts_us");
    lua_pushnumber(L, f->sample_rate_hz);  lua_setfield(L, -2, "sample_rate_hz");

    lua_createtable(L, f->n_channels, 0);
    for (int ch = 0; ch < f->n_channels; ch++) {
        lua_createtable(L, 0, 2);
        lua_pushstring(L, f->channels[ch].label);
        lua_setfield(L, -2, "label");
        lua_createtable(L, f->channels[ch].n_samples, 0);
        for (int i = 0; i < f->channels[ch].n_samples; i++) {
            lua_pushnumber(L, f->channels[ch].samples[i]);
            lua_rawseti(L, -2, i + 1);
        }
        lua_setfield(L, -2, "samples");
        lua_rawseti(L, -2, ch + 1);
    }
    lua_setfield(L, -2, "channels");
}

/* Read back the first sample of each channel (the RMS values). */
static int read_result(lua_State *L, double *out, int max)
{
    if (!lua_istable(L, -1)) return -1;
    lua_getfield(L, -1, "channels");
    if (!lua_istable(L, -1)) { lua_pop(L, 1); return -1; }
    int n = (int)lua_rawlen(L, -1);
    if (n > max) n = max;
    for (int i = 0; i < n; i++) {
        lua_rawgeti(L, -1, i + 1);
        lua_getfield(L, -1, "samples");
        lua_rawgeti(L, -1, 1);
        out[i] = lua_tonumber(L, -1);
        lua_pop(L, 3);
    }
    lua_pop(L, 1);
    return n;
}

/* --- Tests ----------------------------------------------------------------- */

static int test_interrupt(void)
{
    LuaBudget budget = {0, 64u * 1024 * 1024, 0};
    lua_State *L = new_state(&budget);
    g_clock.budget = 5000000; g_clock.used = 0;
    lua_sethook(L, count_hook, LUA_MASKCOUNT, 1000);

    double t0 = spike_now_ms();
    int rc = luaL_dostring(L, "local x = 0 while true do x = x + 1 end");
    double elapsed = spike_now_ms() - t0;

    int aborted = (rc != LUA_OK);
    printf("  infinite loop      : %s after %.1f ms  (%s)\n",
           aborted ? "ABORTED" : "STILL RUNNING - FAIL",
           elapsed,
           aborted ? lua_tostring(L, -1) : "no error");
    lua_close(L);
    return aborted;
}

static int test_memory_cap(void)
{
    LuaBudget budget = {0, 8u * 1024 * 1024, 0};
    lua_State *L = new_state(&budget);
    lua_sethook(L, NULL, 0, 0);

    int rc = luaL_dostring(L,
        "local t = {} local i = 1 while true do t[i] = string.rep('x', 1024) i = i + 1 end");
    int denied = (rc != LUA_OK);
    printf("  runaway alloc      : %s (cap 8 MB, peak %.1f MB, allocator denied=%d)\n",
           denied ? "DENIED cleanly" : "UNBOUNDED - FAIL",
           (double)budget.used / (1024.0 * 1024.0), budget.denied);
    lua_close(L);
    return denied;
}

static int test_sandbox(void)
{
    LuaBudget budget = {0, 32u * 1024 * 1024, 0};
    lua_State *L = new_state(&budget);
    const char *escapes[] = {
        "return io.open('/etc/passwd')",
        "return os.execute('id')",
        "return require('os')",
        "return dofile('/etc/passwd')",
        "return load('return 1')()",
        "return os.getenv('HOME')",
        NULL
    };
    int denied = 0, total = 0;
    for (const char **e = escapes; *e; e++) {
        total++;
        if (luaL_dostring(L, *e) != LUA_OK) { denied++; lua_pop(L, 1); }
        else printf("    !! ALLOWED: %s\n", *e);
    }
    printf("  host escapes       : %d/%d denied\n", denied, total);
    lua_close(L);
    return denied == total;
}

static void bench_case(const SpikeCase *c, int iterations)
{
    LuaBudget budget = {0, 256u * 1024 * 1024, 0};
    lua_State *L = new_state(&budget);
    /* No hook during the benchmark: we are measuring the engine, and the hook's
     * cost is reported separately below. */
    if (luaL_dostring(L, SCRIPT) != LUA_OK) {
        printf("  script load failed: %s\n", lua_tostring(L, -1));
        lua_close(L); return;
    }

    SpikeFrame *f = spike_frame_new(c);
    double *expected = (double *)malloc(sizeof(double) * (size_t)c->n_channels);
    double *got = (double *)malloc(sizeof(double) * (size_t)c->n_channels);
    spike_reference_rms(f, expected);

    /* Warm up. */
    for (int i = 0; i < 50; i++) {
        lua_getglobal(L, "process");
        push_frame(L, f);
        lua_pcall(L, 1, 1, 0);
        lua_pop(L, 1);
    }

    double marshal_ms = 0.0, total_ms = 0.0;
    for (int i = 0; i < iterations; i++) {
        double t0 = spike_now_ms();
        lua_getglobal(L, "process");
        push_frame(L, f);
        double t1 = spike_now_ms();
        int rc = lua_pcall(L, 1, 1, 0);
        if (rc != LUA_OK) { printf("  call failed: %s\n", lua_tostring(L, -1)); break; }
        read_result(L, got, c->n_channels);
        lua_pop(L, 1);
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

    free(expected); free(got);
    spike_frame_free(f);
    lua_close(L);
}

static void bench_hook_overhead(const SpikeCase *c, int iterations)
{
    LuaBudget budget = {0, 256u * 1024 * 1024, 0};
    lua_State *L = new_state(&budget);
    (void)luaL_dostring(L, SCRIPT);
    g_clock.budget = 1000000000LL; g_clock.used = 0;
    lua_sethook(L, count_hook, LUA_MASKCOUNT, 1000);

    SpikeFrame *f = spike_frame_new(c);
    double t0 = spike_now_ms();
    for (int i = 0; i < iterations; i++) {
        lua_getglobal(L, "process");
        push_frame(L, f);
        lua_pcall(L, 1, 1, 0);
        lua_pop(L, 1);
    }
    double per_frame = (spike_now_ms() - t0) / iterations;
    printf("  with 1k-instruction hook installed: %.3f ms/frame (%s)\n",
           per_frame, c->name);
    spike_frame_free(f);
    lua_close(L);
}

int main(void)
{
    printf("=== Lua 5.4.7 ===\n\n");
    printf("Safety:\n");
    int ok = 1;
    ok &= test_sandbox();
    ok &= test_interrupt();
    ok &= test_memory_cap();

    printf("\nThroughput (rectify + per-channel RMS):\n");
    for (int i = 0; i < SPIKE_CASE_COUNT; i++)
        bench_case(&SPIKE_CASES[i], 2000);

    printf("\nInstruction-hook cost:\n");
    bench_hook_overhead(&SPIKE_CASES[1], 2000);

    printf("\nSafety verdict: %s\n", ok ? "all three controls work" : "A CONTROL FAILED");
    return ok ? 0 : 1;
}
