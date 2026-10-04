<script lang="ts">
  import { onMount } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { getCommuteConfig, saveCommuteConfig, deleteCommuteConfig, testWebhook } from '$lib/api';
  import { jwt_token } from '$lib/auth';
  import { newCommute, convertUnits, type Commute } from '$lib/commute';
  import PlacePicker from '$lib/components/PlacePicker.svelte';
  import DayOfWeekSelector from '$lib/components/DayOfWeekSelector.svelte';
  import PushNotificationToggle from '$lib/components/PushNotificationToggle.svelte';

  let commutes = $state<Commute[]>([]);
  let settings = $state<Commute>(newCommute());
  let baseline = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let error = $state('');
  let message = $state('');
  let confirmDelete = $state(false);
  let loaded = $state(false);
  const dirty = $derived(loaded && JSON.stringify(settings) !== baseline);
  beforeNavigate((navigation) => {
    if (dirty && !confirm('Leave without saving your changes?')) navigation.cancel();
  });
  function setDraft(commute: Commute) {
    settings = JSON.parse(JSON.stringify(commute));
    baseline = JSON.stringify(settings);
    error = '';
    message = '';
    confirmDelete = false;
  }
  function select(commute: Commute) {
    if (dirty && !confirm('Discard your unsaved changes?')) return;
    setDraft(commute);
  }
  async function load() {
    loading = true;
    error = '';
    try {
      commutes = await getCommuteConfig();
      const requested = Number(new URLSearchParams(window.location.search).get('commute'));
      setDraft(commutes.find((c) => c.id === requested) || commutes[0] || newCommute());
      loaded = true;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }
  onMount(() => {
    if ($jwt_token) load();
    else loading = false;
  });
  async function save(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    message = '';
    if (settings.lat == null || settings.lon == null) {
      error = 'Choose where you leave from.';
      return;
    }
    if (settings.dest_lat == null || settings.dest_lon == null) {
      error = 'Choose where you are going.';
      return;
    }
    if (settings.waypoints.some((wp) => wp.lat == null || wp.lon == null)) {
      error = 'Choose a location for each stop, or remove unused stops.';
      return;
    }
    if (!settings.days_of_week) {
      error = 'Choose at least one commute day.';
      return;
    }
    busy = true;
    try {
      const saved = await saveCommuteConfig({
        ...settings,
        name: settings.name.trim(),
        waypoints: settings.waypoints.map((wp, order) => ({ ...wp, order }))
      });
      baseline = JSON.stringify(settings);
      setDraft(saved);
      await goto(`/?commute=${saved.id}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  async function remove() {
    if (!settings.id) return;
    busy = true;
    error = '';
    try {
      await deleteCommuteConfig(settings.id);
      baseline = JSON.stringify(settings);
      await load();
      message = 'Commute deleted.';
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  async function testNotification() {
    busy = true;
    message = '';
    error = '';
    try {
      await testWebhook(settings);
      message = 'Test notification sent.';
    } catch (e) {
      error = (e as Error).message;
    } finally {
      busy = false;
    }
  }
  function moveStop(index: number, direction: number) {
    const stops = [...settings.waypoints];
    [stops[index], stops[index + direction]] = [stops[index + direction], stops[index]];
    settings.waypoints = stops;
  }
</script>

<svelte:head><title>Your commute · Commute Check</title></svelte:head>
<svelte:window
  onbeforeunload={(event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  }}
/>
<div class="page-heading">
  <p class="eyebrow">Set up once. Check before you leave.</p>
  <h1>Your commute</h1>
</div>
{#if !$jwt_token}
  <section class="card">
    <h2>Keep your commute handy</h2>
    <p>Create an account to save your places, times and weather preferences.</p>
    <a class="button" href="/register">Create an account</a> <a href="/login">Sign in</a>
  </section>
{:else if loading}<p role="status">Loading your commute…</p>
{:else if !loaded}<div class="notice error" role="alert">{error}</div>
  <button onclick={load}>Try again</button>
{:else}
  {#if commutes.length}<div class="commute-picker">
      <label for="saved-commute">Saved commute</label>
      <div class="actions">
        <select
          id="saved-commute"
          value={settings.id || ''}
          onchange={(e) => {
            const selected = commutes.find((c) => c.id === Number(e.currentTarget.value));
            if (selected) select(selected);
          }}
          ><option value="" disabled>New commute</option>{#each commutes as commute}<option
              value={commute.id}>{commute.name}</option
            >{/each}</select
        ><button class="secondary" onclick={() => select(newCommute())}>Add commute</button>
      </div>
    </div>{/if}
  <form onsubmit={save}>
    <fieldset disabled={busy}>
      <section class="card">
        <h2><span class="step">1</span> Where do you travel?</h2>
        <p class="muted">
          A nearby town is enough for a weather check. Use your location or choose on the map for
          more precision.
        </p>
        <PlacePicker
          id="origin"
          label="Leaving from"
          bind:name={settings.origin_name}
          bind:lat={settings.lat}
          bind:lon={settings.lon}
          onselect={(place) => (settings.timezone = place.timezone)}
        />
        <PlacePicker
          id="destination"
          label="Going to"
          bind:name={settings.dest_name}
          bind:lat={settings.dest_lat}
          bind:lon={settings.dest_lon}
        />
        <label>Commute name<input bind:value={settings.name} required maxlength="100" /></label>
      </section>
      <section class="card">
        <h2><span class="step">2</span> When do you go?</h2>
        <div class="two-columns">
          <label>Leave home<input type="time" bind:value={settings.schedule_time} required /></label
          ><label
            >Head back<input
              type="time"
              value={settings.return_schedule_time || ''}
              disabled={settings.return_schedule_time === null}
              onchange={(e) => (settings.return_schedule_time = e.currentTarget.value)}
              required={settings.return_schedule_time !== null}
            /></label
          >
        </div>
        <label class="checkbox"
          ><input
            type="checkbox"
            checked={settings.return_schedule_time !== null}
            onchange={(e) =>
              (settings.return_schedule_time = e.currentTarget.checked ? '17:00' : null)}
          /> Check my return trip too</label
        >
        <p class="field-label">Commute days</p>
        <DayOfWeekSelector bind:value={settings.days_of_week} />
        <details>
          <summary>Time zone: {settings.timezone.replaceAll('_', ' ')}</summary><label
            >Time zone<input
              bind:value={settings.timezone}
              required
              placeholder="America/New_York"
            /></label
          >
          <p class="muted">
            Both departure times use this time zone. A return time before your outbound time means
            the next day.
          </p>
        </details>
      </section>
      <section class="card">
        <h2><span class="step">3</span> Your riding preferences</h2>
        <label
          >Weather units<select
            value={settings.unit_system}
            onchange={(e) =>
              (settings = convertUnits(settings, e.currentTarget.value as 'imperial' | 'metric'))}
            ><option value="imperial">Fahrenheit & miles per hour</option><option value="metric"
              >Celsius & kilometres per hour</option
            ></select
          ></label
        >
        <p class="muted">
          We start with cautious weather limits. Adjust them to suit your comfort and gear.
        </p>
        <details>
          <summary>Adjust weather limits</summary>
          <p>Temperature uses “feels like.” Wind limits apply to gusts too.</p>
          <div class="two-columns">
            <label
              >Cold: take care below ({settings.unit_system === 'metric' ? '°C' : '°F'})<input
                type="number"
                step="any"
                bind:value={settings.min_temp_caution}
                required
              /></label
            ><label
              >Cold: avoid riding below<input
                type="number"
                step="any"
                bind:value={settings.min_temp_no_go}
                required
              /></label
            ><label
              >Wind: take care above ({settings.unit_system === 'metric' ? 'km/h' : 'mph'})<input
                type="number"
                min="0"
                step="any"
                bind:value={settings.max_wind_caution}
                required
              /></label
            ><label
              >Wind: avoid riding above<input
                type="number"
                min="0"
                step="any"
                bind:value={settings.max_wind_no_go}
                required
              /></label
            >
          </div>
          <label
            >Avoid riding when rain chance exceeds (%)<input
              type="number"
              min="0"
              max="100"
              bind:value={settings.rain_threshold}
              required
            /></label
          >
        </details>
        <details>
          <summary>Stops along the way ({settings.waypoints.length})</summary>
          <p class="muted">
            Optional. Add places where you want another weather check. Stops are checked in reverse
            on the way home.
          </p>
          {#each settings.waypoints as wp, index}
            <div class="stop">
              <PlacePicker
                id={`stop-${index}`}
                label={`Stop ${index + 1}`}
                bind:name={wp.name}
                bind:lat={wp.lat}
                bind:lon={wp.lon}
              />
              <div class="actions">
                <button
                  type="button"
                  class="secondary"
                  disabled={index === 0}
                  onclick={() => moveStop(index, -1)}>Move up</button
                ><button
                  type="button"
                  class="secondary"
                  disabled={index === settings.waypoints.length - 1}
                  onclick={() => moveStop(index, 1)}>Move down</button
                ><button
                  type="button"
                  class="text-button danger"
                  onclick={() =>
                    (settings.waypoints = settings.waypoints.filter((_, i) => i !== index))}
                  >Remove stop {index + 1}</button
                >
              </div>
            </div>
          {/each}
          <button
            type="button"
            class="secondary"
            disabled={settings.waypoints.length >= 8}
            onclick={() =>
              (settings.waypoints = [...settings.waypoints, { name: '', lat: null, lon: null }])}
            >Add a stop</button
          >
        </details>
        <details>
          <summary>Other notification services</summary>
          <p class="muted">
            Optional. Connect a service such as Discord or Telegram using an Apprise URL.
          </p>
          <label
            >Notification URL<input
              type="text"
              bind:value={settings.webhook_url}
              placeholder="discord://…"
            /></label
          ><button
            type="button"
            class="secondary"
            disabled={!settings.webhook_url}
            onclick={testNotification}>Send test notification</button
          >
        </details>
      </section>
      {#if error}<p class="notice error" role="alert">{error}</p>{/if}
      {#if message}<p class="notice" role="status">{message}</p>{/if}
      <div class="save-bar">
        <button type="submit">{busy ? 'Saving…' : 'Save and check weather'}</button><a href="/"
          >Cancel</a
        >
      </div>
    </fieldset>
  </form>
  <details class="card">
    <summary>Departure notifications on this device</summary>
    <p>Optional weather checks at your saved departure times.</p>
    <PushNotificationToggle />
  </details>
  {#if settings.id}<div class="delete-area">
      {#if confirmDelete}<p>Delete “{settings.name}”? Its scheduled notifications will stop.</p>
        <div class="actions">
          <button class="danger" disabled={busy} onclick={remove}>Yes, delete commute</button
          ><button class="secondary" onclick={() => (confirmDelete = false)}>Keep commute</button>
        </div>{:else}<button class="text-button danger" onclick={() => (confirmDelete = true)}
          >Delete this commute</button
        >{/if}
    </div>{/if}
{/if}

<style>
  .commute-picker {
    margin-bottom: 1.5rem;
  }
  .commute-picker select {
    flex: 1;
  }
  .step {
    display: inline-grid;
    place-items: center;
    width: 1.7rem;
    height: 1.7rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 50%;
    font-size: 0.95rem;
    margin-right: 0.4rem;
  }
  .save-bar {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0 0 1.5rem;
  }
  .stop {
    border-top: 1px solid var(--border);
    padding: 0.5rem 0 1rem;
  }
  .delete-area {
    margin-top: 2rem;
  }
  .field-label {
    font-weight: 650;
  }
</style>
