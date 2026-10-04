<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
	import { jwt_token, logout, decodeJwt } from '$lib/auth';

	let { children } = $props<{ children?: any }>();

	let isDropdownOpen = $state(false);
	let dropdownContainer: HTMLElement | null = $state(null);

	let userEmail = $derived.by(() => {
		if (!$jwt_token) return '';
		const payload = decodeJwt($jwt_token);
		return payload?.email || payload?.sub || payload?.name || 'User';
	});

	function toggleDropdown() {
		isDropdownOpen = !isDropdownOpen;
	}

	function closeDropdown() {
		isDropdownOpen = false;
	}

	function handleLogout() {
		closeDropdown();
		logout();
	}

	function handleWindowClick(event: MouseEvent) {
		if (isDropdownOpen && dropdownContainer && !dropdownContainer.contains(event.target as Node)) {
			closeDropdown();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && isDropdownOpen) {
			closeDropdown();
		}
	}
</script>

<svelte:window onclick={handleWindowClick} onkeydown={handleKeydown} />

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Commute Check</title>
</svelte:head>

<div class="container">
	<nav class="top-nav">
		<div class="nav-links">
			<a href="/">Dashboard</a>
			<a href="/history">History</a>
			<a href="/settings">Settings</a>
		</div>

		<div class="nav-auth">
			{#if $jwt_token}
				<div class="user-dropdown-container" bind:this={dropdownContainer}>
					<button
						type="button"
						class="user-dropdown-trigger"
						onclick={toggleDropdown}
						aria-expanded={isDropdownOpen}
						aria-haspopup="true"
						aria-label="User menu"
						data-testid="user-dropdown-trigger"
					>
						<span class="user-greeting">Hello, <span class="user-email">{userEmail}</span></span>
						<span class="dropdown-arrow" aria-hidden="true">{isDropdownOpen ? '▲' : '▼'}</span>
					</button>

					{#if isDropdownOpen}
						<div
							class="dropdown-menu"
							role="menu"
							data-testid="user-dropdown-menu"
						>
							<div class="dropdown-header">
								<span class="dropdown-label">Signed in as</span>
								<strong class="dropdown-email">{userEmail}</strong>
							</div>
							<a
								href="/settings"
								class="dropdown-item"
								role="menuitem"
								onclick={closeDropdown}
								data-testid="dropdown-profile-link"
							>
								Profile
							</a>
							<button
								type="button"
								class="dropdown-item logout-btn"
								role="menuitem"
								onclick={handleLogout}
								data-testid="dropdown-logout-button"
							>
								Logout
							</button>
						</div>
					{/if}
				</div>
			{:else}
				<a href="/login">Login</a>
				<a href="/register">Register</a>
			{/if}
		</div>
	</nav>

	<main>
		{#if children}
			{@render children()}
		{/if}
	</main>
</div>

<style>
	.top-nav {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 15px;
		margin-bottom: 20px;
	}

	.nav-links {
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.nav-auth {
		display: flex;
		align-items: center;
		gap: 15px;
	}

	.user-dropdown-container {
		position: relative;
		display: inline-block;
	}

	.user-dropdown-trigger {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		background: #ffffff;
		border: 1px solid var(--border, #dee2e6);
		border-radius: 6px;
		padding: 6px 12px;
		font-size: 14px;
		font-weight: 500;
		color: var(--text, #212529);
		cursor: pointer;
		transition: background-color 0.15s ease, border-color 0.15s ease;
	}

	.user-dropdown-trigger:hover,
	.user-dropdown-trigger:focus-visible {
		background-color: #f1f3f5;
		border-color: #ced4da;
		outline: none;
	}

	.dropdown-arrow {
		font-size: 10px;
		color: #6c757d;
		margin-left: 2px;
	}

	.dropdown-menu {
		position: absolute;
		right: 0;
		top: calc(100% + 4px);
		min-width: 200px;
		background: #ffffff;
		border: 1px solid var(--border, #dee2e6);
		border-radius: 6px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		padding: 6px 0;
		z-index: 1000;
		display: flex;
		flex-direction: column;
	}

	.dropdown-header {
		padding: 8px 14px;
		border-bottom: 1px solid var(--border, #dee2e6);
		font-size: 12px;
		color: #6c757d;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.dropdown-label {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #868e96;
	}

	.dropdown-email {
		color: var(--text, #212529);
		word-break: break-all;
	}

	.dropdown-item {
		display: block;
		width: 100%;
		padding: 8px 14px;
		text-align: left;
		text-decoration: none;
		color: var(--text, #212529);
		background: none;
		border: none;
		font-size: 14px;
		font-weight: normal;
		cursor: pointer;
		box-sizing: border-box;
		transition: background-color 0.15s ease;
	}

	.dropdown-item:hover,
	.dropdown-item:focus-visible {
		background-color: #f8f9fa;
		color: var(--primary, #007bff);
		outline: none;
		text-decoration: none;
	}

	.logout-btn {
		color: var(--status-nogo, #dc3545);
		border-top: 1px solid var(--border, #dee2e6);
		margin-top: 4px;
		padding-top: 8px;
	}

	.logout-btn:hover,
	.logout-btn:focus-visible {
		background-color: #fff5f5;
		color: #bd2130;
	}
</style>
