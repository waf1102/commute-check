<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Commute Check</title>
</svelte:head>

<div class="container">
	<nav>
		<a href="/">Dashboard</a>
		<a href="/settings">Settings</a>
	</nav>

	<main>
		{@render children()}
	</main>
</div>
