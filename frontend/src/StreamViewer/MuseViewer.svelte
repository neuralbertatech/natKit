<script lang="ts">
    import type { MuseSample } from "./types";

    interface Props {
        sample: MuseSample;
        formatNumber: (num: number, decimals?: number) => string;
    }

    let { sample, formatNumber }: Props = $props();

    // Calculate average EEG values for display
    function getChannelAverage(channelData: number[]): number {
        if (!channelData || channelData.length === 0) return 0;
        return channelData.reduce((a, b) => a + b, 0) / channelData.length;
    }

    // Simple bar visualization for EEG values
    function getBarWidth(
        value: number,
        min: number = -100,
        max: number = 100,
    ): number {
        const normalized = ((value - min) / (max - min)) * 100;
        return Math.max(0, Math.min(100, normalized));
    }

    // Get color based on signal strength
    function getSignalClass(hasData: boolean): string {
        return hasData ? "signal-good" : "signal-none";
    }
</script>

<div class="muse-viewer">
    <!-- Signal Status -->
    <div class="signal-status">
        <span class="status-item {getSignalClass(sample.has_data.eeg)}"
            >EEG</span
        >
        <span class="status-item {getSignalClass(sample.has_data.accel)}"
            >Accel</span
        >
        <span class="status-item {getSignalClass(sample.has_data.gyro)}"
            >Gyro</span
        >
        <span class="status-item {getSignalClass(sample.has_data.ppg)}"
            >PPG</span
        >
    </div>

    <!-- EEG Section -->
    {#if sample.has_data.eeg}
        <div class="sensor-section eeg-section">
            <h4>EEG (microvolts)</h4>
            <div class="eeg-channels">
                <div class="eeg-channel">
                    <span class="channel-label">TP9 (L Ear)</span>
                    <div class="channel-bar-container">
                        <div
                            class="channel-bar"
                            style="width: {getBarWidth(
                                getChannelAverage(sample.eeg.tp9),
                            )}%"
                        ></div>
                    </div>
                    <span class="channel-value"
                        >{formatNumber(
                            getChannelAverage(sample.eeg.tp9),
                            2,
                        )}</span
                    >
                </div>
                <div class="eeg-channel">
                    <span class="channel-label">AF7 (L Fore)</span>
                    <div class="channel-bar-container">
                        <div
                            class="channel-bar"
                            style="width: {getBarWidth(
                                getChannelAverage(sample.eeg.af7),
                            )}%"
                        ></div>
                    </div>
                    <span class="channel-value"
                        >{formatNumber(
                            getChannelAverage(sample.eeg.af7),
                            2,
                        )}</span
                    >
                </div>
                <div class="eeg-channel">
                    <span class="channel-label">AF8 (R Fore)</span>
                    <div class="channel-bar-container">
                        <div
                            class="channel-bar"
                            style="width: {getBarWidth(
                                getChannelAverage(sample.eeg.af8),
                            )}%"
                        ></div>
                    </div>
                    <span class="channel-value"
                        >{formatNumber(
                            getChannelAverage(sample.eeg.af8),
                            2,
                        )}</span
                    >
                </div>
                <div class="eeg-channel">
                    <span class="channel-label">TP10 (R Ear)</span>
                    <div class="channel-bar-container">
                        <div
                            class="channel-bar"
                            style="width: {getBarWidth(
                                getChannelAverage(sample.eeg.tp10),
                            )}%"
                        ></div>
                    </div>
                    <span class="channel-value"
                        >{formatNumber(
                            getChannelAverage(sample.eeg.tp10),
                            2,
                        )}</span
                    >
                </div>
            </div>
        </div>
    {/if}

    <!-- Motion Section -->
    {#if sample.has_data.accel || sample.has_data.gyro}
        <div class="sensor-section">
            <h4>Motion</h4>
            <div class="motion-data">
                {#if sample.has_data.accel && sample.accel.length > 0}
                    <div class="motion-row">
                        <span class="motion-label">Accel (g):</span>
                        <span class="motion-values">
                            X: {formatNumber(sample.accel[0].x, 3)}
                            Y: {formatNumber(sample.accel[0].y, 3)}
                            Z: {formatNumber(sample.accel[0].z, 3)}
                        </span>
                    </div>
                {/if}
                {#if sample.has_data.gyro && sample.gyro.length > 0}
                    <div class="motion-row">
                        <span class="motion-label">Gyro (deg/s):</span>
                        <span class="motion-values">
                            X: {formatNumber(sample.gyro[0].x, 2)}
                            Y: {formatNumber(sample.gyro[0].y, 2)}
                            Z: {formatNumber(sample.gyro[0].z, 2)}
                        </span>
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    <!-- PPG Section (if available) -->
    {#if sample.has_data.ppg && sample.ppg}
        <div class="sensor-section">
            <h4>PPG (Heart Rate Sensor)</h4>
            <div class="ppg-data">
                <div class="ppg-channel">
                    <span>PPG0:</span>
                    <span class="ppg-value"
                        >{formatNumber(sample.ppg.ppg0[0] || 0, 2)}</span
                    >
                </div>
                <div class="ppg-channel">
                    <span>PPG1:</span>
                    <span class="ppg-value"
                        >{formatNumber(sample.ppg.ppg1[0] || 0, 2)}</span
                    >
                </div>
                <div class="ppg-channel">
                    <span>PPG2:</span>
                    <span class="ppg-value"
                        >{formatNumber(sample.ppg.ppg2[0] || 0, 2)}</span
                    >
                </div>
            </div>
        </div>
    {/if}

    <!-- Timestamp -->
    <div class="timestamp-section">
        <span class="timestamp-label">Timestamp:</span>
        <span class="timestamp-value">{sample.timestamp}</span>
        <span class="sequence-info">
            EEG Seq: {sample.eeg_sequence} | Motion Seq: {sample.motion_sequence}
        </span>
    </div>
</div>

<style>
    .muse-viewer {
        /* No wrapper styling needed - parent handles the card */
    }

    .signal-status {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
        flex-wrap: wrap;
    }

    .status-item {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }

    .signal-good {
        background: #c8e6c9;
        color: #2e7d32;
    }

    .signal-none {
        background: #e0e0e0;
        color: #757575;
    }

    .sensor-section {
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }

    .sensor-section:last-of-type {
        border-bottom: none;
        margin-bottom: 0.5rem;
        padding-bottom: 0.5rem;
    }

    .sensor-section h4 {
        margin: 0 0 0.5rem 0;
        font-size: 0.9rem;
        color: #333;
    }

    .eeg-section h4 {
        color: #7b1fa2;
    }

    .eeg-channels {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .eeg-channel {
        display: grid;
        grid-template-columns: 100px 1fr 70px;
        align-items: center;
        gap: 0.5rem;
    }

    .channel-label {
        font-size: 0.8rem;
        color: #666;
    }

    .channel-bar-container {
        height: 12px;
        background: #f0f0f0;
        border-radius: 6px;
        overflow: hidden;
    }

    .channel-bar {
        height: 100%;
        background: linear-gradient(90deg, #7b1fa2, #9c27b0);
        border-radius: 6px;
        transition: width 0.1s ease;
    }

    .channel-value {
        font-family: monospace;
        font-size: 0.8rem;
        text-align: right;
    }

    .motion-data {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .motion-row {
        display: flex;
        gap: 0.5rem;
        font-size: 0.85rem;
    }

    .motion-label {
        font-weight: 500;
        min-width: 80px;
    }

    .motion-values {
        font-family: monospace;
        color: #555;
    }

    .ppg-data {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .ppg-channel {
        display: flex;
        gap: 0.25rem;
        font-size: 0.85rem;
    }

    .ppg-value {
        font-family: monospace;
        color: #e91e63;
    }

    .timestamp-section {
        font-size: 0.8rem;
        color: #666;
        padding-top: 0.5rem;
        border-top: 1px solid #eee;
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        align-items: center;
    }

    .timestamp-label {
        font-weight: 500;
    }

    .timestamp-value {
        font-family: monospace;
    }

    .sequence-info {
        font-size: 0.75rem;
        color: #999;
        margin-left: auto;
    }
</style>
