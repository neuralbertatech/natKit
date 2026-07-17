<script lang="ts">
	import { Button as ButtonPrimitive } from "bits-ui";
	import { type Events, buttonVariants } from "./index.js";
	import { cn } from "$lib/utils.js";

	type $$Events = Events;

	let className: string | undefined | null = undefined;
	export let variant: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" =
		"default";
	export let size: "default" | "sm" | "lg" | "icon" = "default";
	export let builders: any[] = [];
	export { className as class };
</script>

<ButtonPrimitive.Root
	{builders}
	class={cn(buttonVariants({ variant, size, className }))}
	type="button"
	{...$$restProps}
	on:click
	on:keydown
>
	<slot />
</ButtonPrimitive.Root>
