<script lang="ts">
    import { Input } from "$lib/components/ui/input";
    import { Label } from "$lib/components/ui/label/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    let input: string = $state("localhost:7409");
    function is_input_valid(): boolean {
        if ((input.match(/:/g) || []).length != 1) {
            console.log("1");
            return false;
        }

        let split = input.split(":");
        let host = split[0];
        let portString = split[1];
        let port = parseInt(portString);
        if (isNaN(port)) {
            console.log("2");
            return false;
        }

        console.log("3");
        return true;
    }

    function connect_to_broker(address: string) {
        fetch(`/api/start_calibration`, {
            mode: "cors",
            method: "POST",
            headers: {
                "Content-type": "application/json; charset=UTF-8",
            },
            body: JSON.stringify({
                broker_address: address,
            }),
        });
    }
</script>

<div class="margin: 1em; flex w-full max-w-sm flex-col gap-1.5">
    <Label for="broker-address">Kafka Address</Label>
    <Input
        type="broker-address"
        id="broker-address"
        placeholder="localhost:7409"
        bind:value={input}
    />
    <Button
        type="submit"
        onclick={() => connect_to_broker(input)}
        disabled={!is_input_valid()}>Connect</Button
    >
</div>
