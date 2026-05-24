<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
	import { jwt_token, logout } from '$lib/auth';

	let { children } = $props();

    // Placeholder for user email, ideally decoded from JWT
    let userEmail: string = 'User Email'; 
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Commute Check</title>
</svelte:head>

<div class="container">
	<nav>
		<a href="/">Dashboard</a>
		<a href="/history">History</a>
		<a href="/settings">Settings</a>
		{#if $jwt_token}
			<span>Hello, {userEmail}</span>
			<button on:click={logout}>Logout</button>
		{:else}
			<a href="/login">Login</a>
			<a href="/register">Register</a>
		{/if}
	</nav>

	<main>
		{@render children()}
	</main>
</div>
