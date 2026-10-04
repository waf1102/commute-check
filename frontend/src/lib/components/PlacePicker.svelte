<script lang="ts">
  import { browser } from '$app/environment';
  import { searchPlaces, type Place } from '$lib/api';
  import type * as LeafletType from 'leaflet';

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
  let requestId = 0;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  let L: typeof LeafletType | null = null;
  let map: LeafletType.Map | null = null;
  let marker: LeafletType.Marker | null = null;

  $effect(() => {
    if (name && !query) {
      query = name;
    }
  });

  function getPinIcon(leaflet: typeof LeafletType) {
    return leaflet.divIcon({
      className: 'leaflet-pin-icon',
      html: `<svg width="24" height="36" viewBox="0 0 24 36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M12 0C5.37 0 0 5.37 0 12C0 21 12 36 12 36C12 36 24 21 24 12C24 5.37 18.63 0 12 0ZM12 16.5C9.51 16.5 7.5 14.49 7.5 12C7.5 9.51 9.51 7.5 12 7.5C14.49 7.5 16.5 9.51 16.5 12C16.5 14.49 14.49 16.5 12 16.5Z" fill="#e53e3e"/></svg><span class="sr-only">${label} marker</span>`,
      iconSize: [24, 36],
      iconAnchor: [12, 36],
      popupAnchor: [0, -36]
    });
  }

  function updateMarker(targetLat: number, targetLon: number, popupText?: string) {
    if (!map || !L) return;
    if (!marker) {
      marker = L.marker([targetLat, targetLon], {
        icon: getPinIcon(L),
        title: `${label} marker`,
        alt: `${label} marker`
      }).addTo(map);
    } else {
      marker.setLatLng([targetLat, targetLon]);
    }
    const el = marker.getElement();
    if (el) {
      el.setAttribute('aria-label', `${label} marker`);
      el.setAttribute('title', `${label} marker`);
    }
    if (popupText) {
      marker.bindPopup(popupText);
    }
  }

  function updateMap(targetLat: number, targetLon: number, popupText?: string) {
    if (!map || !L) return;
    map.setView([targetLat, targetLon], 13, { animate: false });
    updateMarker(targetLat, targetLon, popupText);
  }

  $effect(() => {
    if (lat != null && lon != null && map && L) {
      const cur = marker?.getLatLng();
      if (!cur || Math.abs(cur.lat - lat) > 0.0001 || Math.abs(cur.lng - lon) > 0.0001) {
        updateMap(lat, lon, name);
      }
    } else if (lat == null && lon == null && marker && map) {
      marker.remove();
      marker = null;
    }
  });

  async function reverseGeocode(targetLat: number, targetLon: number): Promise<string> {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${targetLat}&lon=${targetLon}`,
        { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(3000) }
      );
      if (res.ok) {
        const data = await res.json();
        if (data.display_name) {
          return data.name || data.display_name.split(',').slice(0, 3).join(', ').trim();
        }
      }
    } catch {
      // Ignore network errors in test or offline environments
    }
    return `Location (${targetLat.toFixed(4)}, ${targetLon.toFixed(4)})`;
  }

  function initMap(node: HTMLElement) {
    let isDestroyed = false;
    (async () => {
      if (!browser && typeof window === 'undefined') return;
      const leafletModule = await import('leaflet');
      if (isDestroyed) return;
      L = (leafletModule.default || leafletModule) as typeof LeafletType;

      const initialLat = lat ?? 42.36;
      const initialLon = lon ?? -71.06;
      const initialZoom = lat != null && lon != null ? 13 : 10;

      map = L.map(node, {
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false
      }).setView([initialLat, initialLon], initialZoom);
      (node as any)._leaflet_map = map;

      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);

      if (lat != null && lon != null) {
        updateMarker(lat, lon, name);
      }

      map.on('click', async (e: LeafletType.LeafletMouseEvent) => {
        const clickedLat = Number(e.latlng.lat.toFixed(5));
        const clickedLon = Number(e.latlng.lng.toFixed(5));
        lat = clickedLat;
        lon = clickedLon;
        updateMarker(clickedLat, clickedLon);
        const defaultName = `Location (${clickedLat.toFixed(4)}, ${clickedLon.toFixed(4)})`;
        name = defaultName;
        query = defaultName;
        onselect?.({
          name: defaultName,
          lat: clickedLat,
          lon: clickedLon,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
        });
        const placeName = await reverseGeocode(clickedLat, clickedLon);
        if (placeName && placeName !== defaultName) {
          name = placeName;
          query = placeName;
          onselect?.({
            name: placeName,
            lat: clickedLat,
            lon: clickedLon,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
          });
        }
      });
    })();

    return {
      destroy() {
        isDestroyed = true;
        if (map) {
          try {
            map.stop();
            map.off();
            map.remove();
          } catch {
            // ignore
          }
          map = null;
          marker = null;
        }
      }
    };
  }

  async function search() {
    const current = ++requestId;
    const q = query.trim();
    if (q.length < 2) {
      message = 'Enter a town, city or postal code.';
      return;
    }
    busy = true;
    message = '';
    results = [];
    try {
      let found = await searchPlaces(q);
      if (!found || found.length === 0) {
        try {
          const nomRes = await fetch(
            `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=jsonv2&limit=5`,
            { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(3000) }
          );
          if (nomRes.ok) {
            const nomData = await nomRes.json();
            found = nomData.map((item: any) => ({
              name: item.display_name,
              lat: parseFloat(item.lat),
              lon: parseFloat(item.lon),
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
            }));
          }
        } catch {
          // Ignore Nominatim fallback error
        }
      }
      if (current !== requestId) return;
      results = found || [];
      if (!results.length) message = 'No places found. Try a nearby town or a postal code.';
    } catch (error) {
      if (current === requestId) message = (error as Error).message;
    } finally {
      if (current === requestId) busy = false;
    }
  }

  function onInput() {
    if (debounceTimer) clearTimeout(debounceTimer);
    if (query.trim().length >= 2) {
      debounceTimer = setTimeout(() => {
        search();
      }, 300);
    } else {
      results = [];
      message = '';
    }
  }

  function choose(place: Place) {
    requestId++;
    if (debounceTimer) clearTimeout(debounceTimer);
    busy = false;
    name = place.name;
    query = place.name;
    lat = place.lat;
    lon = place.lon;
    results = [];
    message = '';
    updateMap(place.lat, place.lon, place.name);
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
  <label class="sr-only" for={id}>{label} town or postal code</label>
  <div class="search-row">
    <input
      {id}
      bind:value={query}
      placeholder="Town, city or postal code"
      autocomplete="off"
      oninput={onInput}
      onkeydown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          if (debounceTimer) clearTimeout(debounceTimer);
          search();
        }
      }}
    /><button
      type="button"
      class="secondary"
      onclick={() => {
        if (debounceTimer) clearTimeout(debounceTimer);
        search();
      }}
      disabled={busy}>{busy ? 'Finding…' : 'Find'}</button
    >
  </div>
  <button type="button" class="text-button" onclick={locate} disabled={busy}
    >Use my current location<span class="sr-only"> for {label}</span></button
  >
  {#if results.length}<ul class="place-results" aria-label={`${label} search results`}>
      {#each results as place}<li>
          <button type="button" class="secondary" onclick={() => choose(place)}>{place.name}</button
          >
        </li>{/each}
    </ul>{/if}
  {#if lat != null && lon != null}
    <div class="chosen-location">
      <div>
        <strong>{name || 'Selected location'}</strong>
        <small>{lat.toFixed(4)}, {lon.toFixed(4)}</small>
      </div>
    </div>
  {/if}
  <div class="map-wrap">
    <div class="map" use:initMap role="region" aria-label={`${label} map`}></div>
    <p class="map-hint">Click the map to select or adjust location.</p>
  </div>
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
  .search-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .search-row input {
    min-width: 0;
    flex: 1;
  }
  .chosen-location {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid var(--border);
    padding: 0.6rem 0.8rem;
    border-radius: 5px;
    margin-top: 0.5rem;
    background: var(--card-bg, #fff);
  }
  .chosen-location small {
    display: block;
    color: var(--muted);
  }
  .place-results {
    padding: 0;
    list-style: none;
    margin: 0.4rem 0;
  }
  .place-results button {
    width: 100%;
    text-align: left;
    margin-bottom: 0.4rem;
  }
  .map-wrap {
    margin-top: 0.6rem;
  }
  .map {
    position: relative;
    width: 100%;
    height: 220px;
    border-radius: 6px;
    border: 1px solid var(--border);
    box-sizing: border-box;
    z-index: 0;
  }
  .map-hint {
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.3rem;
    margin-bottom: 0;
  }
</style>
