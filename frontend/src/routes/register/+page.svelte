<script lang="ts">
  import { register } from '$lib/auth';
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
      await register(email, password);
      goto('/settings');
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Create account · Commute Check</title></svelte:head>
<section class="auth card">
  <p class="eyebrow">Commute Check</p>
  <h1>Set up your account</h1>
  <p class="muted">Save your commute and check the weather before you ride.</p>
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
        autocomplete="new-password"
        minlength="8"
        required
      /></label
    >
    <p class="muted">Use at least 8 characters.</p>
    {#if error}<p class="notice error" role="alert">{error}</p>{/if}
    <button type="submit" disabled={loading}>{loading ? 'Please wait…' : 'Create account'}</button>
  </form>
  <p class="switch">Already have an account? <a href="/login">Sign in</a></p>
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
