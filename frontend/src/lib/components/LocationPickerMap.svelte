<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type * as LeafletType from 'leaflet';
  import AddressSearch from './AddressSearch.svelte';

  export interface MapPoint {
    lat: number;
    lon: number;
    name?: string;
  }

  export interface MapWaypoint {
    id?: string | number;
    name?: string;
    lat: number;
    lon: number;
    order?: number;
  }

  let {
    origin,
    destination = null,
    waypoints = [],
    height = '400px',
    onupdateOrigin,
    onupdateDestination,
    onupdateWaypoint,
    onaddWaypoint
  }: {
    origin: MapPoint;
    destination?: MapPoint | null;
    waypoints?: MapWaypoint[];
    height?: string;
    onupdateOrigin: (coords: { lat: number; lon: number }) => void;
    onupdateDestination: (coords: { lat: number; lon: number }) => void;
    onupdateWaypoint: (index: number, coords: { lat: number; lon: number }) => void;
    onaddWaypoint?: (coords: { lat: number; lon: number }) => void;
  } = $props();

  let mapContainer: HTMLDivElement | null = $state(null);
  let mapInstance: LeafletType.Map | null = null;
  let L: typeof LeafletType | null = null;
  let markersLayerGroup: LeafletType.LayerGroup | null = null;
  let routeLineLayerGroup: LeafletType.LayerGroup | null = null;
  let isDestroyed = false;
  let isMounted = $state(false);

  // Active target for map clicks: 'origin' | 'destination' | number (index into waypoints) | 'new_waypoint'
  let activeTarget = $state<'origin' | 'destination' | number | 'new_waypoint'>('origin');
  let statusNotice = $state('');

  let targetLabel = $derived.by(() => {
    if (activeTarget === 'origin') return 'Origin (Home)';
    if (activeTarget === 'destination') return 'Destination (Office)';
    if (activeTarget === 'new_waypoint') return 'New Waypoint';
    if (typeof activeTarget === 'number') {
      const wp = waypoints[activeTarget];
      return wp?.name ? `Waypoint ${activeTarget + 1}: ${wp.name}` : `Waypoint ${activeTarget + 1}`;
    }
    return 'Location';
  });

  onMount(async () => {
    if (!mapContainer) return;

    try {
      const leafletModule = await import('leaflet');
      if (isDestroyed || !mapContainer) return;
      L = leafletModule;

      if ((mapContainer as any)._leaflet_id) {
        (mapContainer as any)._leaflet_id = null;
      }

      // Default center to origin or London if origin coordinates are 0/0
      const initialLat = origin?.lat || 51.5074;
      const initialLon = origin?.lon || -0.1278;

      mapInstance = L.map(mapContainer, {
        scrollWheelZoom: true,
        dragging: true,
        zoomControl: true
      }).setView([initialLat, initialLon], 12);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }).addTo(mapInstance);

      markersLayerGroup = L.layerGroup().addTo(mapInstance);
      routeLineLayerGroup = L.layerGroup().addTo(mapInstance);

      // Handle map clicks to drop or move active target pin
      mapInstance.on('click', (e: LeafletType.LeafletMouseEvent) => {
        handleMapCoordinateSelect(e.latlng.lat, e.latlng.lng);
      });

      // Expose map click trigger for automated testing in Vitest / jsdom
      (mapContainer as any).__handleMapCoordinateSelect = handleMapCoordinateSelect;
      (mapContainer as any).__leafletMap = mapInstance;

      isMounted = true;
      renderMarkers();
      fitAllPoints();
    } catch (err) {
      console.error('Failed to initialize Leaflet location picker map:', err);
    }
  });

  onDestroy(() => {
    isDestroyed = true;
    if (mapInstance) {
      mapInstance.remove();
      mapInstance = null;
    }
  });

  // Re-render markers whenever points or activeTarget change
  $effect(() => {
    // Read reactive props to track them
    const _o = origin;
    const _d = destination;
    const _w = waypoints;
    const _t = activeTarget;
    if (isMounted) {
      renderMarkers();
    }
  });

  function handleMapCoordinateSelect(lat: number, lon: number) {
    const cleanLat = parseFloat(lat.toFixed(4));
    const cleanLon = parseFloat(lon.toFixed(4));

    if (activeTarget === 'origin') {
      onupdateOrigin({ lat: cleanLat, lon: cleanLon });
      statusNotice = `📍 Origin set to ${cleanLat}, ${cleanLon}`;
    } else if (activeTarget === 'destination') {
      onupdateDestination({ lat: cleanLat, lon: cleanLon });
      statusNotice = `📍 Destination set to ${cleanLat}, ${cleanLon}`;
    } else if (typeof activeTarget === 'number') {
      onupdateWaypoint(activeTarget, { lat: cleanLat, lon: cleanLon });
      statusNotice = `📍 Waypoint #${activeTarget + 1} set to ${cleanLat}, ${cleanLon}`;
    } else if (activeTarget === 'new_waypoint') {
      if (onaddWaypoint) {
        onaddWaypoint({ lat: cleanLat, lon: cleanLon });
        statusNotice = `📍 New Waypoint added at ${cleanLat}, ${cleanLon}`;
        activeTarget = waypoints.length; // Focus on the new waypoint
      }
    }

    setTimeout(() => {
      if (statusNotice.startsWith('📍')) statusNotice = '';
    }, 4000);
  }

  function renderMarkers() {
    if (!mapInstance || !L || !markersLayerGroup || !routeLineLayerGroup) return;

    const leaflet = L;
    const markersGroup = markersLayerGroup;
    const routeGroup = routeLineLayerGroup;

    markersGroup.clearLayers();
    routeGroup.clearLayers();

    const allPoints: [number, number][] = [];

    // 1. Origin Marker (Green)
    if (origin && typeof origin.lat === 'number' && typeof origin.lon === 'number') {
      allPoints.push([origin.lat, origin.lon]);
      const isActive = activeTarget === 'origin';
      const originIcon = leaflet.divIcon({
        className: 'location-picker-div-icon',
        html: `
          <div class="map-picker-pin pin-origin ${isActive ? 'active-target-pin' : ''}" data-testid="picker-marker-origin">
            <div class="pin-badge">A</div>
            <div class="pin-title">Origin</div>
          </div>
        `,
        iconSize: [36, 44],
        iconAnchor: [18, 42],
        popupAnchor: [0, -38]
      });

      const originMarker = leaflet.marker([origin.lat, origin.lon], {
        icon: originIcon,
        draggable: true
      }).addTo(markersGroup);

      originMarker.bindPopup(`
        <div style="font-family: inherit; font-size: 13px;">
          <strong style="color: #16a34a;">🟢 Origin Location</strong><br/>
          Lat: ${origin.lat}, Lon: ${origin.lon}<br/>
          <em>Drag marker or click map to move</em>
        </div>
      `);

      originMarker.on('dragend', (e: any) => {
        const pos = e.target.getLatLng();
        handleMapCoordinateSelect(pos.lat, pos.lng);
      });
    }

    // 2. Waypoint Markers (Purple)
    if (waypoints && Array.isArray(waypoints)) {
      for (let idx = 0; idx < waypoints.length; idx++) {
        const wp = waypoints[idx];
        if (typeof wp.lat === 'number' && typeof wp.lon === 'number') {
          allPoints.push([wp.lat, wp.lon]);
          const isActive = activeTarget === idx;
          const wpIcon = leaflet.divIcon({
            className: 'location-picker-div-icon',
            html: `
              <div class="map-picker-pin pin-waypoint ${isActive ? 'active-target-pin' : ''}" data-testid="picker-marker-waypoint-${idx}">
                <div class="pin-badge">${idx + 1}</div>
                <div class="pin-title">${wp.name || `W${idx + 1}`}</div>
              </div>
            `,
            iconSize: [36, 44],
            iconAnchor: [18, 42],
            popupAnchor: [0, -38]
          });

          const wpMarker = leaflet.marker([wp.lat, wp.lon], {
            icon: wpIcon,
            draggable: true
          }).addTo(markersGroup);

          wpMarker.bindPopup(`
            <div style="font-family: inherit; font-size: 13px;">
              <strong style="color: #9333ea;">🟣 Waypoint #${idx + 1}</strong><br/>
              <b>${wp.name || `Waypoint ${idx + 1}`}</b><br/>
              Lat: ${wp.lat}, Lon: ${wp.lon}<br/>
              <em>Drag marker or click map to move</em>
            </div>
          `);

          wpMarker.on('dragend', (e: any) => {
            const pos = e.target.getLatLng();
            const cleanLat = parseFloat(pos.lat.toFixed(4));
            const cleanLon = parseFloat(pos.lng.toFixed(4));
            onupdateWaypoint(idx, { lat: cleanLat, lon: cleanLon });
            statusNotice = `📍 Waypoint #${idx + 1} set to ${cleanLat}, ${cleanLon}`;
            setTimeout(() => { if (statusNotice.startsWith('📍')) statusNotice = ''; }, 4000);
          });
        }
      }
    }

    // 3. Destination Marker (Red / Teal)
    if (destination && destination.lat !== null && destination.lon !== null &&
        typeof destination.lat === 'number' && typeof destination.lon === 'number') {
      allPoints.push([destination.lat, destination.lon]);
      const isActive = activeTarget === 'destination';
      const destIcon = leaflet.divIcon({
        className: 'location-picker-div-icon',
        html: `
          <div class="map-picker-pin pin-destination ${isActive ? 'active-target-pin' : ''}" data-testid="picker-marker-destination">
            <div class="pin-badge">B</div>
            <div class="pin-title">${destination.name || 'Destination'}</div>
          </div>
        `,
        iconSize: [36, 44],
        iconAnchor: [18, 42],
        popupAnchor: [0, -38]
      });

      const destMarker = leaflet.marker([destination.lat, destination.lon], {
        icon: destIcon,
        draggable: true
      }).addTo(markersGroup);

      destMarker.bindPopup(`
        <div style="font-family: inherit; font-size: 13px;">
          <strong style="color: #dc2626;">🔴 Destination Location</strong><br/>
          <b>${destination.name || 'Destination'}</b><br/>
          Lat: ${destination.lat}, Lon: ${destination.lon}<br/>
          <em>Drag marker or click map to move</em>
        </div>
      `);

      destMarker.on('dragend', (e: any) => {
        const pos = e.target.getLatLng();
        const cleanLat = parseFloat(pos.lat.toFixed(4));
        const cleanLon = parseFloat(pos.lng.toFixed(4));
        onupdateDestination({ lat: cleanLat, lon: cleanLon });
        statusNotice = `📍 Destination set to ${cleanLat}, ${cleanLon}`;
        setTimeout(() => { if (statusNotice.startsWith('📍')) statusNotice = ''; }, 4000);
      });
    }

    // 4. Connect points with dashed route guidance polyline if 2 or more points
    if (allPoints.length >= 2) {
      leaflet.polyline(allPoints, {
        color: '#6366f1',
        weight: 3,
        dashArray: '6, 8',
        opacity: 0.7
      }).addTo(routeGroup);
    }
  }

  function fitAllPoints() {
    if (!mapInstance || !L) return;
    const pts: [number, number][] = [];
    if (origin && typeof origin.lat === 'number' && typeof origin.lon === 'number') {
      pts.push([origin.lat, origin.lon]);
    }
    if (waypoints && Array.isArray(waypoints)) {
      waypoints.forEach(wp => {
        if (typeof wp.lat === 'number' && typeof wp.lon === 'number') {
          pts.push([wp.lat, wp.lon]);
        }
      });
    }
    if (destination && typeof destination.lat === 'number' && typeof destination.lon === 'number') {
      pts.push([destination.lat, destination.lon]);
    }

    if (pts.length > 1) {
      mapInstance.fitBounds(pts, { padding: [40, 40], maxZoom: 15 });
    } else if (pts.length === 1) {
      mapInstance.setView(pts[0], 13);
    }
  }

  function handleAddressSelect(result: { name: string; lat: number; lon: number; display_name: string }) {
    handleMapCoordinateSelect(result.lat, result.lon);
    if (mapInstance) {
      mapInstance.setView([result.lat, result.lon], 14, { animate: true });
    }
  }

  async function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      statusNotice = '❌ Geolocation is not supported by your browser';
      return;
    }

    statusNotice = `Locating current GPS position for ${targetLabel}...`;

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = parseFloat(pos.coords.latitude.toFixed(4));
        const lon = parseFloat(pos.coords.longitude.toFixed(4));
        handleMapCoordinateSelect(lat, lon);
        if (mapInstance) {
          mapInstance.setView([lat, lon], 14, { animate: true });
        }
        statusNotice = `✅ Updated ${targetLabel} to current location!`;
        setTimeout(() => { if (statusNotice.startsWith('✅')) statusNotice = ''; }, 4000);
      },
      (err) => {
        console.error('Geolocation error:', err);
        statusNotice = '❌ Unable to retrieve GPS location. Check browser permissions.';
        setTimeout(() => { if (statusNotice.startsWith('❌')) statusNotice = ''; }, 6000);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }
</script>

<div class="location-picker-card" data-testid="location-picker-component">
  <div class="picker-header">
    <div class="target-selector-group">
      <span class="selector-heading">Target to drop/edit:</span>
      <div class="target-pills" role="radiogroup" aria-label="Location target to set">
        <button
          type="button"
          class="pill-btn origin-pill {activeTarget === 'origin' ? 'selected' : ''}"
          role="radio"
          aria-checked={activeTarget === 'origin'}
          onclick={() => activeTarget = 'origin'}
          data-testid="target-select-origin"
        >
          🟢 Origin
        </button>

        <button
          type="button"
          class="pill-btn destination-pill {activeTarget === 'destination' ? 'selected' : ''}"
          role="radio"
          aria-checked={activeTarget === 'destination'}
          onclick={() => activeTarget = 'destination'}
          data-testid="target-select-destination"
        >
          🔴 Destination
        </button>

        {#each waypoints as wp, idx}
          <button
            type="button"
            class="pill-btn waypoint-pill {activeTarget === idx ? 'selected' : ''}"
            role="radio"
            aria-checked={activeTarget === idx}
            onclick={() => activeTarget = idx}
            data-testid="target-select-waypoint-{idx}"
          >
            🟣 W{idx + 1}{wp.name ? `: ${wp.name}` : ''}
          </button>
        {/each}

        {#if onaddWaypoint}
          <button
            type="button"
            class="pill-btn add-wp-pill {activeTarget === 'new_waypoint' ? 'selected' : ''}"
            role="radio"
            aria-checked={activeTarget === 'new_waypoint'}
            onclick={() => activeTarget = 'new_waypoint'}
            data-testid="target-select-new-waypoint"
          >
            ➕ Add Waypoint Pin
          </button>
        {/if}
      </div>
    </div>
  </div>

  <div class="search-and-action-bar">
    <div class="address-search-box">
      <AddressSearch
        placeholder="Type address or place to set {targetLabel}..."
        onselect={handleAddressSelect}
        testId="map-address-search"
      />
    </div>

    <div class="map-quick-actions">
      <button
        type="button"
        class="secondary quick-btn"
        onclick={handleUseCurrentLocation}
        data-testid="use-current-location-btn"
        title="Set active target to current GPS location"
      >
        📍 Use Current Location
      </button>

      <button
        type="button"
        class="secondary quick-btn"
        onclick={fitAllPoints}
        data-testid="fit-bounds-btn"
        title="Fit all route pins in view"
      >
        🔍 Fit Route
      </button>
    </div>
  </div>

  <div class="interactive-hint" data-testid="map-picker-hint">
    👉 <strong>Active: {targetLabel}</strong> — Click anywhere on the map to drop pin, or drag existing pins.
  </div>

  {#if statusNotice}
    <div class="status-notice-banner" data-testid="map-status-notice">
      {statusNotice}
    </div>
  {/if}

  <div
    class="map-container"
    style="height: {height};"
    bind:this={mapContainer}
    data-testid="location-picker-canvas"
    role="region"
    aria-label="Interactive Location Picker Map"
  ></div>

  <div class="coordinates-summary" data-testid="coordinates-summary-bar">
    <div class="coord-chip origin-chip" data-testid="origin-coords-chip">
      <span class="chip-badge">Origin</span>
      <span class="chip-coords">{origin?.lat ?? 'N/A'}, {origin?.lon ?? 'N/A'}</span>
    </div>

    <div class="coord-chip dest-chip" data-testid="destination-coords-chip">
      <span class="chip-badge">Destination</span>
      <span class="chip-coords">
        {#if destination && destination.lat !== null && destination.lon !== null}
          {destination.lat}, {destination.lon}
        {:else}
          <em>Not Set</em>
        {/if}
      </span>
    </div>

    {#each waypoints as wp, idx}
      <div class="coord-chip wp-chip" data-testid="waypoint-coords-chip-{idx}">
        <span class="chip-badge">#{idx + 1} {wp.name || 'Waypoint'}</span>
        <span class="chip-coords">{wp.lat}, {wp.lon}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .location-picker-card {
    background: var(--bg-surface, #ffffff);
    border: 1px solid var(--border, #e2e8f0);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  .picker-header {
    margin-bottom: 12px;
  }

  .target-selector-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .selector-heading {
    font-size: 13px;
    font-weight: 600;
    color: var(--text, #334155);
  }

  .target-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .pill-btn {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    color: #475569;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease-in-out;
  }

  .pill-btn:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
  }

  .pill-btn.selected {
    font-weight: 700;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
  }

  .origin-pill.selected {
    background: #dcfce7;
    border-color: #22c55e;
    color: #15803d;
  }

  .destination-pill.selected {
    background: #fee2e2;
    border-color: #ef4444;
    color: #b91c1c;
  }

  .waypoint-pill.selected {
    background: #f3e8ff;
    border-color: #a855f7;
    color: #7e22ce;
  }

  .add-wp-pill {
    background: #eef2ff;
    border-color: #c7d2fe;
    color: #4338ca;
  }

  .add-wp-pill.selected {
    background: #e0e7ff;
    border-color: #6366f1;
    color: #3730a3;
  }

  .search-and-action-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: flex-start;
    margin-bottom: 8px;
  }

  .address-search-box {
    flex: 1;
    min-width: 260px;
  }

  .map-quick-actions {
    display: flex;
    gap: 6px;
  }

  .quick-btn {
    padding: 8px 12px;
    font-size: 12px;
    border-radius: 6px;
    white-space: nowrap;
  }

  .interactive-hint {
    font-size: 12px;
    color: #64748b;
    margin-bottom: 8px;
    background: #f8fafc;
    padding: 6px 10px;
    border-radius: 6px;
    border-left: 3px solid #6366f1;
  }

  .status-notice-banner {
    font-size: 12px;
    padding: 6px 10px;
    margin-bottom: 8px;
    background: #eff6ff;
    color: #1e40af;
    border-radius: 6px;
    border: 1px solid #bfdbfe;
  }

  .map-container {
    width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border, #cbd5e1);
    box-sizing: border-box;
    z-index: 1;
  }

  .coordinates-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }

  .coord-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
  }

  .chip-badge {
    font-weight: 700;
    text-transform: uppercase;
    font-size: 10px;
  }

  .origin-chip .chip-badge {
    color: #16a34a;
  }

  .dest-chip .chip-badge {
    color: #dc2626;
  }

  .wp-chip .chip-badge {
    color: #7e22ce;
  }

  .chip-coords {
    font-family: monospace;
    color: #475569;
  }

  /* Marker styling inside Leaflet DivIcon */
  :global(.map-picker-pin) {
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: grab;
    user-select: none;
  }

  :global(.map-picker-pin:active) {
    cursor: grabbing;
  }

  :global(.pin-badge) {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    color: white;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    border: 2px solid white;
    transition: transform 0.15s ease;
  }

  :global(.pin-origin .pin-badge) {
    background-color: #22c55e;
  }

  :global(.pin-destination .pin-badge) {
    background-color: #ef4444;
  }

  :global(.pin-waypoint .pin-badge) {
    background-color: #9333ea;
  }

  :global(.active-target-pin .pin-badge) {
    transform: scale(1.2);
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.4);
  }

  :global(.pin-title) {
    font-size: 10px;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.95);
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
    color: #1e293b;
    margin-top: 2px;
    white-space: nowrap;
    max-width: 90px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
