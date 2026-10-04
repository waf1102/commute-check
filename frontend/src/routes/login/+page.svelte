<script lang="ts">
  import { login } from '$lib/auth';
  import { goto } from '$app/navigation';

  let email = $state('');
  let password = $state('');
  let error = $state<string | null>(null);
  let loading = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    loading = true;
    error = null;
    try {
      await login(email, password);
      await goto('/');
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Sign in · Commute Check</title></svelte:head>
<section class="auth card">
  <p class="eyebrow">Commute Check</p>
  <h1>Welcome back</h1>
  <p class="muted">Sign in to check your commute.</p>
  <form onsubmit={handleSubmit}>
    <label for="email"
      >Email address<input
        type="email"
        id="email"
        bind:value={email}
        autocomplete="email"
        autocapitalize="none"
        required
      /></label
    >
    <label for="password"
      >Password<input
        type="password"
        id="password"
        bind:value={password}
        autocomplete="current-password"
        required
      /></label
    >

    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    <button type="submit" disabled={loading}>{loading ? 'Please wait…' : 'Sign in'}</button>
  </form>
  <p class="switch">New here? <a href="/register">Create an account</a></p>
</section>

<style>
  .auth {
    max-width: 430px;
    margin: 2rem auto;
  }
  h1 {
    font-size: 1.8rem;
  }
  button {
    width: 100%;
    margin-top: 0.5rem;
  }
  .switch {
    margin: 1.5rem 0 0;
  }
</style>
