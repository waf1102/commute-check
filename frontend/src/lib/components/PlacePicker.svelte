<script lang="ts">
  import { searchPlaces, type Place } from '$lib/api';
  let {
    id,
    label,
    name = $bindable(''),
    lat = $bindable<number | null>(null),
    lon = $bindable<number | null>(null),
    onselect
  }: {
    id: string;
    label: string;
    name?: string;
    lat?: number | null;
    lon?: number | null;
    onselect?: (place: Place) => void;
  } = $props();
  let query = $state('');
  let results = $state<Place[]>([]);
  let busy = $state(false);
  let message = $state('');
  let editing = $state(false);
  let requestId = 0;
  async function search() {
    const current = ++requestId;
    if (query.trim().length < 2) {
      message = 'Enter a town, city or postal code.';
      return;
    }
    busy = true;
    message = '';
    results = [];
    try {
      const found = await searchPlaces(query.trim());
      if (current !== requestId) return;
      results = found;
      if (!found.length) message = 'No places found. Try a nearby town or a postal code.';
    } catch (error) {
      if (current === requestId) message = (error as Error).message;
    } finally {
      if (current === requestId) busy = false;
    }
  }
  function choose(place: Place) {
    requestId++;
    busy = false;
    name = place.name;
    lat = place.lat;
    lon = place.lon;
    results = [];
    message = '';
    editing = false;
    onselect?.(place);
  }
  function locate() {
    if (!navigator.geolocation) {
      message = 'Location is unavailable on this device. Search for your town instead.';
      return;
    }
    const current = ++requestId;
    busy = true;
    message = 'Finding your location…';
    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (current !== requestId) return;
        choose({
          name: 'Current location',
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        });
      },
      () => {
        if (current !== requestId) return;
        busy = false;
        message =
          'Could not access your location. Search for a town or allow location access in your browser.';
      },
      { timeout: 10000, maximumAge: 60000 }
    );
  }
</script>

<div class="place-picker">
  <p class="field-label">{label}</p>
  {#if lat != null && lon != null && !editing}
    <div class="chosen">
      <div>
        <strong>{name || 'Selected location'}</strong><small
          >{lat.toFixed(4)}, {lon.toFixed(4)}</small
        >
      </div>
      <button
        type="button"
        class="secondary"
        onclick={() => {
          editing = true;
          query = '';
        }}>Change<span class="sr-only"> {label}</span></button
      >
    </div>
  {:else}
    <label class="sr-only" for={id}>{label} town or postal code</label>
    <div class="search-row">
      <input
        {id}
        bind:value={query}
        placeholder="Town, city or postal code"
        autocomplete="off"
        onkeydown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            search();
          }
        }}
      /><button type="button" class="secondary" onclick={search} disabled={busy}
        >{busy ? 'Finding…' : 'Find'}</button
      >
    </div>
    <button type="button" class="text-button" onclick={locate} disabled={busy}
      >Use my current location<span class="sr-only"> for {label}</span></button
    >
    {#if results.length}<ul class="place-results" aria-label={`${label} search results`}>
        {#each results as place}<li>
            <button type="button" class="secondary" onclick={() => choose(place)}
              >{place.name}</button
            >
          </li>{/each}
      </ul>{/if}
    <details class="coordinates">
      <summary>Enter exact coordinates</summary>
      <div class="two-columns">
        <label
          >Latitude<input
            aria-label={`${label} latitude`}
            type="number"
            min="-90"
            max="90"
            step="any"
            bind:value={lat}
            onfocus={() => (editing = true)}
          /></label
        ><label
          >Longitude<input
            aria-label={`${label} longitude`}
            type="number"
            min="-180"
            max="180"
            step="any"
            bind:value={lon}
            onfocus={() => (editing = true)}
          /></label
        >
      </div>
      <label>Place name<input bind:value={name} placeholder="e.g. Home" /></label>
    </details>
    {#if editing}<button
        type="button"
        class="text-button"
        onclick={() => {
          editing = false;
          requestId++;
          busy = false;
          message = '';
        }}>Done</button
      >{/if}
  {/if}
  {#if message}<p role="status" class="muted">{message}</p>{/if}
</div>

<style>
  .place-picker {
    margin: 1.25rem 0;
  }
  .field-label {
    font-weight: 650;
    margin-bottom: 0.5rem;
  }
  .search-row,
  .chosen {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .search-row input {
    min-width: 0;
    flex: 1;
  }
  .chosen {
    justify-content: space-between;
    border: 1px solid var(--border);
    padding: 0.8rem;
    border-radius: 5px;
  }
  small {
    display: block;
    color: var(--muted);
  }
  .place-results {
    padding: 0;
    list-style: none;
  }
  .place-results button {
    width: 100%;
    text-align: left;
    margin-bottom: 0.4rem;
  }
  .coordinates {
    font-size: 0.9rem;
    border: 0;
    padding: 0;
    margin-top: 0.5rem;
  }
</style>
