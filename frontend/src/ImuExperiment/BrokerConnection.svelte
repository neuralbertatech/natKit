<script lang="ts">
    import { Input } from "$lib/components/ui/input";
    import { Label } from "$lib/components/ui/label/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    const PUBLIC_BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

    let input: string = $state(PUBLIC_BACKEND_URL);
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
        fetch(`${PUBLIC_BACKEND_URL}/api/set_streams`, { 
            mode: "cors", 
            method: "POST",
            body: JSON.stringify({
                stream_ids: get_stream_ids(), 
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8"
            }
        }).then(_response => {
            fetch(`${PUBLIC_BACKEND_URL}/api/start_calibration`, {
                mode: "cors",
                method: "POST"
            }).then(_inner_response => {
                swtichToCalibrationTab()
            })
        });
    }
</script>

<div class="margin: 1em; flex w-full max-w-sm flex-col gap-1.5">
    <Label for="broker-address">Kafka Address</Label>
    <Input type="broker-address" id="broker-address" placeholder={PUBLIC_BACKEND_URL} bind:value={input} />
    <Button type="submit" onclick={() => connect_to_broker(input)} disabled={!is_input_valid()}>Connect</Button>
  </div>