<script lang="ts">
  import { onMount } from 'svelte';
  import { jwt_token } from '$lib/auth';
  import { getCommuteStats, recordDecision } from '$lib/api';
  function localDate(date = new Date()) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }
  let startDate = $state(localDate(new Date(Date.now() - 30 * 86400000)));
  let endDate = $state(localDate());
  let rows = $state<
    { date: string; days_ridden: number; days_driven: number; days_total: number }[]
  >([]);
  let loading = $state(false);
  let recording = $state(false);
  let error = $state('');
  let message = $state('');
  let generation = 0;
  async function load() {
    error = '';
    if (!startDate || !endDate || startDate > endDate) {
      error = 'Choose an end date on or after the start date.';
      return;
    }
    const current = ++generation;
    loading = true;
    try {
      const response = await getCommuteStats(startDate, endDate);
      if (current === generation)
        rows = response.filter((r: { days_total: number }) => r.days_total > 0).reverse();
    } catch (e) {
      if (current === generation) error = (e as Error).message;
    } finally {
      if (current === generation) loading = false;
    }
  }
  async function record(decision: 'riding' | 'driving') {
    recording = true;
    message = '';
    error = '';
    try {
      await recordDecision({ decision, date: localDate() });
      message = `Saved: you ${decision === 'riding' ? 'rode' : 'drove'} today. Choose again to change it.`;
      await load();
    } catch (e) {
      error = (e as Error).message;
    } finally {
      recording = false;
    }
  }
  onMount(() => {
    if ($jwt_token) load();
  });
</script>

<svelte:head><title>Ride history · Commute Check</title></svelte:head>
<div class="page-heading">
  <p class="eyebrow">Your riding days</p>
  <h1>Ride history</h1>
</div>
{#if !$jwt_token}<section class="card">
    <p>Sign in to see your ride history.</p>
    <a class="button" href="/login">Sign in</a>
  </section>
{:else}
  <section class="card">
    <h2>How did you travel today?</h2>
    <p class="muted">Optional. Keep a simple record of your riding days.</p>
    <div class="actions">
      <button disabled={recording} onclick={() => record('riding')}>I rode</button><button
        class="secondary"
        disabled={recording}
        onclick={() => record('driving')}>I drove</button
      >
    </div>
    {#if message}<p class="notice" role="status">{message}</p>{/if}
  </section>
  <form
    class="card"
    onsubmit={(e) => {
      e.preventDefault();
      load();
    }}
  >
    <div class="two-columns">
      <label>From<input type="date" bind:value={startDate} required /></label><label
        >To<input type="date" bind:value={endDate} required /></label
      >
    </div>
    <button class="secondary" disabled={loading}>Show history</button>
  </form>
  {#if error}<p class="notice error" role="alert">{error}</p>{:else if loading}<p role="status">
      Loading history…
    </p>{:else if !rows.length}<section class="card">
      <h2>No rides logged in this period</h2>
      <p>Record today’s trip above, or choose another date range.</p>
    </section>{:else}
    <section class="card">
      <table>
        <caption>Recorded trips</caption><thead
          ><tr><th scope="col">Date</th><th scope="col">Travel</th></tr></thead
        ><tbody
          >{#each rows as row}<tr
              ><th scope="row"
                >{new Date(`${row.date}T12:00:00`).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}</th
              ><td
                >{row.days_ridden ? 'Rode' : ''}{row.days_ridden && row.days_driven
                  ? ' & '
                  : ''}{row.days_driven ? 'Drove' : ''}</td
              ></tr
            >{/each}</tbody
        >
      </table>
    </section>
  {/if}
{/if}

<style>
  table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  caption {
    text-align: left;
    font-weight: 650;
    margin-bottom: 1rem;
  }
  th,
  td {
    border-bottom: 1px solid var(--border);
    padding: 0.8rem 0.2rem;
  }
  tbody th {
    font-weight: 400;
  }
  .notice {
    margin: 1rem 0 0;
  }
</style>
