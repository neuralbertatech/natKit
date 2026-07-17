<script lang="ts">
	import type { HTMLAttributes } from "svelte/elements";
	import { cn } from "$lib/utils.js";

	type $$Props = Omit<HTMLAttributes<HTMLSpanElement>, "class"> & {
		class?: string | null | undefined;
	};

	let className: string | undefined | null = undefined;
	export { className as class };
</script>

<span
	class={cn("text-muted-foreground ml-auto text-xs tracking-widest", className)}
	{...$$restProps}
>
	<slot />
</span>
