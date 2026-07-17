<script lang="ts">
	import { Command as CommandPrimitive } from "cmdk-sv";
	import { cn } from "$lib/utils.js";

	type $$Props = Omit<CommandPrimitive.CommandProps, "class"> & {
		class?: string | null | undefined;
	};

	export let value: $$Props["value"] = undefined;

	let className: string | undefined | null = undefined;
	export { className as class };
</script>

<CommandPrimitive.Root
	class={cn(
		"bg-popover text-popover-foreground flex h-full w-full flex-col overflow-hidden rounded-md",
		className
	)}
	bind:value
	{...$$restProps}
>
	<slot />
</CommandPrimitive.Root>
