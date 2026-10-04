<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import { jwt_token, logout, getUserEmailFromToken } from '$lib/auth';
  let email = $derived(getUserEmailFromToken($jwt_token));
  let { children } = $props();
</script>

<svelte:head
  ><link rel="icon" href="/icons/icon-192.png" /><meta
    name="theme-color"
    content="#285346"
  /></svelte:head
>
<a class="skip-link" href="#main">Skip to content</a>
<header>
  <div class="header-inner">
    <a class="brand" href="/" aria-label="Commute Check home"
      ><span class="brand-mark" aria-hidden="true">↗</span> Commute Check</a
    >
    <nav aria-label="Main navigation">
      {#if $jwt_token}<a href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined}
          >Weather</a
        ><a href="/settings" aria-current={page.url.pathname === '/settings' ? 'page' : undefined}
          >Your commute</a
        ><a href="/history" aria-current={page.url.pathname === '/history' ? 'page' : undefined}
          >History</a
        ><button class="text-button" onclick={logout}>Sign out</button>{:else}<a
          href="/login"
          aria-current={page.url.pathname === '/login' ? 'page' : undefined}>Sign in</a
        >{/if}
    </nav>
  </div>
  {#if email}<p class="account">Signed in as {email}</p>{/if}
</header>
<main id="main" tabindex="-1">{@render children()}</main>
<footer>
  <span>Commute Check</span><span
    >Weather by <a href="https://open-meteo.com/">Open-Meteo</a> · Places by
    <a href="https://www.geonames.org/">GeoNames</a></span
  >
</footer>

<style>
  header {
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
  }
  .header-inner {
    max-width: 960px;
    margin: auto;
    padding: 1rem 1.5rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 2rem;
  }
  .brand {
    font-weight: 750;
    font-size: 1.1rem;
    text-decoration: none;
    white-space: nowrap;
  }
  .account {
    max-width: 960px;
    margin: 0 auto;
    padding: 0 1.5rem 0.7rem;
    text-align: right;
    font-size: 0.8rem;
    color: var(--muted);
    overflow-wrap: anywhere;
  }
  .brand-mark {
    display: inline-grid;
    place-items: center;
    width: 28px;
    height: 28px;
    background: var(--primary);
    color: white;
    border-radius: 4px;
    margin-right: 0.3rem;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem 1.2rem;
  }
  nav a {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    text-decoration: none;
    font-size: 0.9rem;
  }
  nav a[aria-current='page'] {
    text-decoration: underline;
    font-weight: 700;
  }
  nav button {
    font-size: 0.9rem;
    font-weight: 400;
  }
  main {
    max-width: 820px;
    padding: 2rem 1.5rem;
    margin: auto;
    min-height: 75vh;
  }
  main:focus {
    outline: none;
  }
  footer {
    border-top: 1px solid var(--border);
    max-width: 960px;
    margin: 1rem auto 0;
    padding: 1.5rem;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.8rem;
    color: var(--muted);
    font-size: 0.8rem;
  }
  .skip-link {
    position: absolute;
    top: -100px;
    left: 1rem;
    padding: 0.5rem;
    background: white;
    z-index: 9999;
  }
  .skip-link:focus {
    top: 1rem;
  }
  @media (max-width: 560px) {
    .header-inner {
      padding: 0.8rem 1rem;
    }
    main {
      padding: 1.2rem 1rem;
    }
    nav {
      gap: 0.8rem;
    }
  }
</style>
