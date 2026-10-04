<script lang="ts">
  import { onMount } from 'svelte';
  import { jwt_token } from '$lib/auth';
  import { getCommuteConfig, checkRoute, type RouteAssessmentResult } from '$lib/api';
  import { verdict, statusClass, type Commute } from '$lib/commute';
  import LegRiskCard from '$lib/components/LegRiskCard.svelte';
  import OfflineBanner from '$lib/components/OfflineBanner.svelte';
  let commutes = $state<Commute[]>([]);
  let selectedId = $state<number | undefined>();
  let result = $state<RouteAssessmentResult | null>(null);
  let loading = $state(true);
  let checking = $state(false);
  let error = $state('');
  let request = 0;
  const concern = $derived(
    result
      ? [result.outbound_leg, result.return_leg].find(
          (leg) => leg?.status === result?.overall_status
        )
      : undefined
  );
  const selected = $derived(commutes.find((c) => c.id === selectedId));
  async function check() {
    if (!selectedId) return;
    const current = ++request;
    checking = true;
    error = '';
    result = null;
    try {
      const response = await checkRoute({ commute_id: selectedId });
      if (current === request) result = response;
    } catch (e) {
      if (current === request) error = (e as Error).message;
    } finally {
      if (current === request) checking = false;
    }
  }
  async function load() {
    loading = true;
    error = '';
    try {
      commutes = await getCommuteConfig();
      const requested = Number(new URLSearchParams(window.location.search).get('commute'));
      selectedId = commutes.find((c) => c.id === requested)?.id || commutes[0]?.id;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
    if (selectedId) await check();
  }
  onMount(() => {
    if ($jwt_token) load();
    else loading = false;
  });
  function dateLabel(date: string) {
    return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'short',
      day: 'numeric'
    });
  }
</script>

<svelte:head
  ><title>Ride today? · Commute Check</title><meta
    name="description"
    content="Check the weather for your ride to work and back, in one place."
  /></svelte:head
>
<OfflineBanner />
{#if !$jwt_token}
  <section class="welcome">
    <p class="eyebrow">A weather check for your everyday ride</p>
    <h1>Before you grab<br />your helmet.</h1>
    <p class="intro">
      See the weather on your way there and back. Know what needs a little care, and when to
      consider another way.
    </p>
    <a class="button" href="/register">Set up my commute</a>
    <p class="muted">Already set up? <a href="/login">Sign in</a></p>
  </section>
  <div class="welcome-steps">
    <div>
      <span>01</span>
      <h2>Your places</h2>
      <p>Choose where you leave from and where you’re headed.</p>
    </div>
    <div>
      <span>02</span>
      <h2>Your times</h2>
      <p>Set your departure times and the days you commute.</p>
    </div>
    <div>
      <span>03</span>
      <h2>Your weather</h2>
      <p>One clear check for both trips, with reasons you can act on.</p>
    </div>
  </div>
{:else}
  <div class="page-heading">
    <p class="eyebrow">Before you leave</p>
    <h1>Your ride, there and back.</h1>
  </div>
  {#if loading}<p role="status">Loading your commute…</p>
  {:else if !commutes.length && !error}<section class="card empty">
      <h2>Let’s set up your first commute</h2>
      <p>Choose your places and times. We’ll check the weather for both trips.</p>
      <a class="button" href="/settings">Set up my commute</a>
    </section>
  {:else}
    {#if selected}<div class="route-heading" id="route-visualizer">
        <div>
          {#if commutes.length > 1}<label for="commute-select">Your commute</label><select
              id="commute-select"
              bind:value={selectedId}
              onchange={check}
              >{#each commutes as commute}<option value={commute.id}>{commute.name}</option
                >{/each}</select
            >{:else}<h2>{selected.name}</h2>{/if}
          <p class="muted">
            {selected.origin_name || 'Home'} → {selected.dest_name || 'Destination'}
          </p>
        </div>
        <a href={`/settings?commute=${selected.id}`}>Edit commute</a>
      </div>{/if}
    {#if checking}<section class="card" role="status">
        <h2>Checking both trips…</h2>
        <p class="muted">Getting the forecast for your places and departure times.</p>
      </section>
    {:else if error}<section class="card">
        <h2>Forecast unavailable</h2>
        <p class="notice error" role="alert">{error}</p>
        <button onclick={selectedId ? check : load}>Try again</button>
      </section>
    {:else if result && selected}
      <section class="verdict {statusClass(result.overall_status)}" aria-labelledby="verdict-title">
        <p class="eyebrow">
          {result.assessment_date ? dateLabel(result.assessment_date) : 'Your next commute'}
        </p>
        <h2 id="verdict-title">{verdict(result.overall_status)}</h2>
        <p>{result.recommendation}</p>
        {#if concern && result.overall_status !== 'Go'}<p class="main-reason">
            <strong>{concern.leg_type === 'return' ? 'Heading back' : 'Heading out'}:</strong>
            {concern.reasons[0]}
          </p>{/if}
      </section>
      <LegRiskCard
        outboundLeg={result.outbound_leg}
        returnLeg={result.return_leg || undefined}
        unitSystem={selected.unit_system}
        timezone={result.timezone}
      />
      <div class="forecast-footer">
        <p class="muted">
          {#if result.checked_at}Checked {new Date(result.checked_at).toLocaleTimeString([], {
              hour: 'numeric',
              minute: '2-digit'
            })}.
          {/if}Times shown in {(result.timezone || selected.timezone).replaceAll('_', ' ')}.
        </p>
        <button class="secondary" onclick={check}>Refresh weather</button>
      </div>
      <details class="card">
        <summary>What this check covers</summary>
        <p>
          Weather at your starting point, destination and saved stops, at estimated arrival times.
          The overall result uses the worse of your two trips.
        </p>
        <p>
          {result.routing_estimated
            ? 'Travel times are rough distance estimates because road routing is unavailable.'
            : 'Travel times use road routing estimates; traffic and time spent at stops are not included.'}
          Weather between checked locations can differ.
        </p>
        <p>
          A forecast is a guide, not a guarantee of road conditions. Check local warnings before
          riding.
        </p>
      </details>
    {/if}
  {/if}
{/if}

<style>
  .welcome {
    padding: 3rem 0;
    max-width: 38rem;
  }
  .welcome h1 {
    font-size: clamp(2.5rem, 7vw, 4rem);
    line-height: 1.12;
    letter-spacing: -0.045em;
  }
  .intro {
    font-size: 1.15rem;
    max-width: 33rem;
    margin: 1.5rem 0 2rem;
  }
  .welcome-steps {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
    border-top: 1px solid var(--border);
    padding-top: 2rem;
  }
  .welcome-steps span {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .welcome-steps h2 {
    font-size: 1.1rem;
    margin: 0.6rem 0;
  }
  .welcome-steps p {
    color: var(--muted);
  }
  .route-heading,
  .forecast-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .route-heading h2,
  .route-heading p {
    margin: 0.25rem 0;
  }
  .verdict {
    border: 1px solid var(--border);
    border-left: 5px solid var(--status-go);
    padding: 1.5rem;
    margin: 1.5rem 0;
    background: #edf3ed;
  }
  .verdict h2 {
    font-size: 1.8rem;
    margin-bottom: 0.7rem;
  }
  .verdict p:last-child {
    margin-bottom: 0;
  }
  .verdict.caution {
    background: #fbf3e1;
    border-left-color: var(--status-caution);
  }
  .verdict.nogo {
    background: #f9eded;
    border-left-color: var(--status-nogo);
  }
  @media (max-width: 560px) {
    .welcome {
      padding: 1.5rem 0;
    }
    .welcome-steps {
      grid-template-columns: 1fr;
      gap: 1rem;
    }
    .forecast-footer {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
