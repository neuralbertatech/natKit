/* Synthetic natKit channel frames, sized across the realistic envelope.
 *
 * Frame rates in natKit are LOW: an EMG stream at 500 Hz with 50 samples per
 * frame is 10 frames/sec; a sliding_window transform at 200ms/50ms hop emits
 * 20/sec. So per-frame interpreter *call* overhead is close to irrelevant — what
 * this spike needs to measure is marshalling cost and per-sample throughput
 * inside the script. The cases below bracket what a real board produces.
 */
#ifndef NATKIT_SPIKE_FRAME_H
#define NATKIT_SPIKE_FRAME_H

#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <time.h>

/* _POSIX_C_SOURCE hides M_PI (an X/Open extension), so define it ourselves. */
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    char label[16];
    double *samples;
    int n_samples;
} SpikeChannel;

typedef struct {
    const char *device_id;
    long long seq_no;
    long long device_ts_us;
    double sample_rate_hz;
    SpikeChannel *channels;
    int n_channels;
} SpikeFrame;

typedef struct {
    const char *name;
    int n_channels;
    int samples_per_channel;
    double sample_rate_hz;
    const char *note;
} SpikeCase;

/* The envelope. frames/sec = sample_rate_hz / samples_per_channel. */
static const SpikeCase SPIKE_CASES[] = {
    {"emg-small",   3,   50,  500.0, "live EXG Pill: 3ch x 50 @500Hz = 10 frames/s"},
    {"emg-window",  8,  256, 1000.0, "8ch windowed: ~4 frames/s"},
    {"eeg-wide",   32, 1024, 1000.0, "high channel count stress: ~1 frame/s"},
};
#define SPIKE_CASE_COUNT ((int)(sizeof(SPIKE_CASES) / sizeof(SPIKE_CASES[0])))

static SpikeFrame *spike_frame_new(const SpikeCase *c)
{
    SpikeFrame *f = (SpikeFrame *)calloc(1, sizeof(SpikeFrame));
    f->device_id = "exg-01";
    f->seq_no = 1234;
    f->device_ts_us = 1784308749619698LL;
    f->sample_rate_hz = c->sample_rate_hz;
    f->n_channels = c->n_channels;
    f->channels = (SpikeChannel *)calloc(c->n_channels, sizeof(SpikeChannel));
    for (int ch = 0; ch < c->n_channels; ch++) {
        snprintf(f->channels[ch].label, sizeof(f->channels[ch].label), "ch%d", ch);
        f->channels[ch].n_samples = c->samples_per_channel;
        f->channels[ch].samples =
            (double *)malloc(sizeof(double) * (size_t)c->samples_per_channel);
        for (int i = 0; i < c->samples_per_channel; i++) {
            /* Something EMG-ish: a sinusoid plus noise, signed so rectify matters. */
            double t = (double)i / c->sample_rate_hz;
            f->channels[ch].samples[i] =
                sin(2.0 * M_PI * 60.0 * t + ch) * 100.0 +
                ((double)((i * 7919 + ch * 104729) % 200) - 100.0) * 0.3;
        }
    }
    return f;
}

static void spike_frame_free(SpikeFrame *f)
{
    for (int ch = 0; ch < f->n_channels; ch++) free(f->channels[ch].samples);
    free(f->channels);
    free(f);
}

static int spike_total_samples(const SpikeCase *c)
{
    return c->n_channels * c->samples_per_channel;
}

/* Reference implementation of the benchmark workload, in C, so each engine's
 * result can be checked rather than assumed: rectify every sample, then reduce
 * each channel to its RMS. Representative of real feature extraction. */
static void spike_reference_rms(const SpikeFrame *f, double *out)
{
    for (int ch = 0; ch < f->n_channels; ch++) {
        double sum = 0.0;
        for (int i = 0; i < f->channels[ch].n_samples; i++) {
            double v = fabs(f->channels[ch].samples[i]);
            sum += v * v;
        }
        out[ch] = sqrt(sum / (double)f->channels[ch].n_samples);
    }
}

static double spike_now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1.0e6;
}

#endif
