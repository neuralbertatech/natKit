<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import Check from "lucide-svelte/icons/check";
    import X from "lucide-svelte/icons/x";

    let {
        backendConnected = false,
        brokerConnected = false,
        onContinue = () => {},
    }: {
        backendConnected: boolean;
        brokerConnected: boolean;
        onContinue: () => void;
    } = $props();
</script>

<div class="broker-connection">
    <h2><b>Connection Status</b></h2>

    <div class="status-list">
        <div class="status-item">
            <span class="status-icon" class:connected={backendConnected}>
                {#if backendConnected}
                    <Check size={20} />
                {:else}
                    <X size={20} />
                {/if}
            </span>
            <span class="status-label">Backend Server</span>
            <span class="status-value" class:connected={backendConnected}>
                {backendConnected ? "Connected" : "Disconnected"}
            </span>
        </div>

        <div class="status-item">
            <span class="status-icon" class:connected={brokerConnected}>
                {#if brokerConnected}
                    <Check size={20} />
                {:else}
                    <X size={20} />
                {/if}
            </span>
            <span class="status-label">Kafka Broker</span>
            <span class="status-value" class:connected={brokerConnected}>
                {brokerConnected ? "Connected" : "Disconnected"}
            </span>
        </div>
    </div>

    {#if backendConnected && brokerConnected}
        <div class="success-message">
            <p>All connections established. You can proceed to stream selection.</p>
        </div>
        <div class="action-button">
            <Button onclick={onContinue}>Continue to Stream Selection</Button>
        </div>
    {:else}
        <div class="warning-message">
            <p>Waiting for all connections to be established...</p>
            <ul>
                {#if !backendConnected}
                    <li>Backend server is not responding. Ensure it is running on the correct port.</li>
                {/if}
                {#if !brokerConnected}
                    <li>Kafka broker is not connected. Check your broker configuration.</li>
                {/if}
            </ul>
        </div>
    {/if}
</div>

<style>
    .broker-connection {
        padding: 1em;
    }

    h2 {
        margin-bottom: 1em;
    }

    .status-list {
        display: flex;
        flex-direction: column;
        gap: 0.75em;
        margin-bottom: 1.5em;
    }

    .status-item {
        display: flex;
        align-items: center;
        gap: 0.75em;
        padding: 0.75em;
        background-color: #f5f5f5;
        border-radius: 6px;
    }

    .status-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background-color: #fee;
        color: #c00;
    }

    .status-icon.connected {
        background-color: #efe;
        color: #0a0;
    }

    .status-label {
        flex: 1;
        font-weight: 500;
    }

    .status-value {
        color: #c00;
        font-weight: 500;
    }

    .status-value.connected {
        color: #0a0;
    }

    .success-message {
        padding: 1em;
        background-color: #efe;
        border: 1px solid #afa;
        border-radius: 6px;
        margin-bottom: 1em;
    }

    .success-message p {
        color: #060;
        margin: 0;
    }

    .warning-message {
        padding: 1em;
        background-color: #fef3cd;
        border: 1px solid #ffc107;
        border-radius: 6px;
    }

    .warning-message p {
        color: #856404;
        margin: 0 0 0.5em 0;
    }

    .warning-message ul {
        margin: 0;
        padding-left: 1.5em;
        color: #856404;
    }

    .action-button {
        margin-top: 1em;
    }
</style>
