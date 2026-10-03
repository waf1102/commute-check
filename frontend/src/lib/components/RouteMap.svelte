<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type * as LeafletType from 'leaflet';
  import type { RouteAssessmentResult, HazardPinpoint } from '$lib/api';

  export interface WaypointItem {
    id?: string | number;
    name?: string;
    lat: number;
    lon: number;
    status?: string;
  }

  export interface RoutePoint {
    name?: string;
    lat: number;
    lon: number;
  }

  export interface RouteSegmentItem {
    coordinates: [number, number][];
    status?: 'Go' | 'Caution' | 'No-Go' | string;
    score?: number;
    name?: string;
  }

  let {
    origin = null,
    destination = null,
    waypoints = [],
    segments = [],
    hazardPinpoints = [],
    hazard_pinpoints = undefined,
    assessment = null,
    height = '420px',
    interactive = true
  }: {
    origin?: RoutePoint | null;
    destination?: RoutePoint | null;
    waypoints?: WaypointItem[];
    segments?: RouteSegmentItem[];
    hazardPinpoints?: HazardPinpoint[];
    hazard_pinpoints?: HazardPinpoint[];
    assessment?: RouteAssessmentResult | any;
    height?: string;
    interactive?: boolean;
  } = $props();

  let mapContainer: HTMLDivElement | null = $state(null);
  let mapInstance: LeafletType.Map | null = null;
  let L: typeof LeafletType | null = null;
  let isMounted = $state(false);

  // Layer groups for easy cleanup on update
  let markersLayerGroup: LeafletType.LayerGroup | null = null;
  let polylinesLayerGroup: LeafletType.LayerGroup | null = null;
  let hazardsLayerGroup: LeafletType.LayerGroup | null = null;

  const STATUS_COLORS: Record<string, string> = {
    'Go': '#22c55e',
    'Caution': '#f59e0b',
    'No-Go': '#ef4444'
  };

  // Derive consolidated list of hazard pinpoints
  let effectiveHazards = $derived.by<HazardPinpoint[]>(() => {
    const list: HazardPinpoint[] = [];
    if (hazard_pinpoints && Array.isArray(hazard_pinpoints) && hazard_pinpoints.length > 0) {
      list.push(...hazard_pinpoints);
    } else if (hazardPinpoints && Array.isArray(hazardPinpoints) && hazardPinpoints.length > 0) {
      list.push(...hazardPinpoints);
    } else if (assessment?.hazard_pinpoints && Array.isArray(assessment.hazard_pinpoints) && assessment.hazard_pinpoints.length > 0) {
      list.push(...assessment.hazard_pinpoints);
    }

    // Auto-generate hazard pinpoints if assessment has Caution/No-Go conditions and no explicit hazards provided
    if (list.length === 0 && assessment) {
      if (assessment.outbound_leg && assessment.outbound_leg.status && assessment.outbound_leg.status !== 'Go' && origin) {
        list.push({
          lat: origin.lat,
          lon: origin.lon,
          title: `${origin.name || 'Origin'} Outbound Risk`,
          location_name: origin.name || 'Origin',
          severity: assessment.outbound_leg.status,
          risk_factors: assessment.outbound_leg.reasons || ['Adverse conditions detected'],
          weather: assessment.outbound_leg.weather,
          weather_conditions: assessment.outbound_leg.weather
            ? `${assessment.outbound_leg.weather.temperature ?? 'N/A'}°, Wind: ${assessment.outbound_leg.weather.wind_speed ?? 'N/A'}, Rain: ${assessment.outbound_leg.weather.precip_prob ?? 0}%`
            : undefined
        });
      }
      if (assessment.return_leg && assessment.return_leg.status && assessment.return_leg.status !== 'Go' && destination) {
        list.push({
          lat: destination.lat,
          lon: destination.lon,
          title: `${destination.name || 'Destination'} Return Risk`,
          location_name: destination.name || 'Destination',
          severity: assessment.return_leg.status,
          risk_factors: assessment.return_leg.reasons || ['Adverse conditions detected'],
          weather: assessment.return_leg.weather,
          weather_conditions: assessment.return_leg.weather
            ? `${assessment.return_leg.weather.temperature ?? 'N/A'}°, Wind: ${assessment.return_leg.weather.wind_speed ?? 'N/A'}, Rain: ${assessment.return_leg.weather.precip_prob ?? 0}%`
            : undefined
        });
      }
    }

    return list;
  });

  // Calculate ordered stops (Origin, Waypoints, Destination)
  let orderedStops = $derived.by(() => {
    const stops: Array<{
      seq: number;
      type: 'origin' | 'waypoint' | 'destination';
      name: string;
      lat: number;
      lon: number;
      status?: string;
    }> = [];

    let seqCounter = 1;

    if (origin && typeof origin.lat === 'number' && typeof origin.lon === 'number') {
      stops.push({
        seq: seqCounter++,
        type: 'origin',
        name: origin.name || 'Origin',
        lat: origin.lat,
        lon: origin.lon,
        status: assessment?.outbound_leg?.status || 'Go'
      });
    }

    if (waypoints && Array.isArray(waypoints)) {
      waypoints.forEach((wp, idx) => {
        if (typeof wp.lat === 'number' && typeof wp.lon === 'number') {
          stops.push({
            seq: seqCounter++,
            type: 'waypoint',
            name: wp.name || `Waypoint ${idx + 1}`,
            lat: wp.lat,
            lon: wp.lon,
            status: wp.status || assessment?.overall_status || 'Go'
          });
        }
      });
    }

    if (destination && typeof destination.lat === 'number' && typeof destination.lon === 'number') {
      stops.push({
        seq: seqCounter++,
        type: 'destination',
        name: destination.name || 'Destination',
        lat: destination.lat,
        lon: destination.lon,
        status: assessment?.return_leg?.status || assessment?.overall_status || 'Go'
      });
    }

    return stops;
  });

  // Build segments if not provided
  let effectiveSegments = $derived.by<RouteSegmentItem[]>(() => {
    if (segments && segments.length > 0) {
      return segments;
    }

    const res: RouteSegmentItem[] = [];
    if (orderedStops.length >= 2) {
      for (let i = 0; i < orderedStops.length - 1; i++) {
        const p1 = orderedStops[i];
        const p2 = orderedStops[i + 1];
        // Determine segment status: p2's status, or assessment status, default 'Go'
        const segStatus = p2.status || p1.status || assessment?.overall_status || 'Go';
        res.push({
          name: `${p1.name} → ${p2.name}`,
          coordinates: [
            [p1.lat, p1.lon],
            [p2.lat, p2.lon]
          ],
          status: segStatus
        });
      }
    }
    return res;
  });

  let isDestroyed = false;

  onMount(async () => {
    if (!mapContainer) return;

    try {
      // Guard against SSR: strictly import within onMount()
      const leafletModule = await import('leaflet');
      if (isDestroyed || !mapContainer) return;
      L = leafletModule;

      if ((mapContainer as any)._leaflet_id) {
        (mapContainer as any)._leaflet_id = null;
      }

      mapInstance = L.map(mapContainer, {
        scrollWheelZoom: interactive,
        dragging: interactive,
        zoomControl: interactive
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
      }).addTo(mapInstance);

      markersLayerGroup = L.layerGroup().addTo(mapInstance);
      polylinesLayerGroup = L.layerGroup().addTo(mapInstance);
      hazardsLayerGroup = L.layerGroup().addTo(mapInstance);

      isMounted = true;
      renderMapFeatures();
    } catch (err) {
      console.error('Failed to initialize Leaflet route map:', err);
    }
  });

  onDestroy(() => {
    isDestroyed = true;
    if (mapInstance) {
      mapInstance.remove();
      mapInstance = null;
    }
  });

  function renderMapFeatures() {
    if (!mapInstance || !L || !markersLayerGroup || !polylinesLayerGroup || !hazardsLayerGroup) return;

    markersLayerGroup.clearLayers();
    polylinesLayerGroup.clearLayers();
    hazardsLayerGroup.clearLayers();

    const allCoords: [number, number][] = [];

    // 1. Draw multi-colored polyline segments
    for (const seg of effectiveSegments) {
      const color = STATUS_COLORS[seg.status || 'Go'] || '#22c55e';
      const poly = L.polyline(seg.coordinates, {
        color,
        weight: 6,
        opacity: 0.85,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(polylinesLayerGroup);

      poly.bindPopup(`
        <div style="font-family: inherit; font-size: 13px;">
          <strong>${seg.name || 'Route Segment'}</strong><br/>
          Status: <span style="font-weight: 600; color: ${color}">${seg.status || 'Go'}</span>
        </div>
      `);

      for (const pt of seg.coordinates) {
        allCoords.push(pt);
      }
    }

    // 2. Draw numbered markers for Origin, Waypoints, Destination
    for (const stop of orderedStops) {
      allCoords.push([stop.lat, stop.lon]);

      const pinColor = stop.type === 'origin' ? '#3b82f6' : (stop.type === 'destination' ? '#0d9488' : '#8b5cf6');
      const icon = L.divIcon({
        className: 'route-stop-div-icon',
        html: `
          <div class="route-stop-marker marker-${stop.type}" style="--pin-color: ${pinColor};" data-testid="marker-${stop.type}-${stop.seq}">
            <div class="pin-bubble">
              <span class="pin-number">${stop.seq}</span>
            </div>
            <div class="pin-label">${stop.name}</div>
          </div>
        `,
        iconSize: [36, 44],
        iconAnchor: [18, 42],
        popupAnchor: [0, -38]
      });

      const marker = L.marker([stop.lat, stop.lon], { icon }).addTo(markersLayerGroup);

      const typeLabel = stop.type === 'origin' ? 'Origin (Start)' : (stop.type === 'destination' ? 'Destination (End)' : `Waypoint #${stop.seq}`);

      marker.bindPopup(`
        <div class="route-stop-popup" style="font-family: inherit;">
          <h4 style="margin: 0 0 4px; font-size: 14px; color: ${pinColor};">${typeLabel}</h4>
          <p style="margin: 0 0 4px; font-weight: 600;">${stop.name}</p>
          <div style="font-size: 12px; color: #64748b;">
            Lat: ${stop.lat.toFixed(4)}, Lon: ${stop.lon.toFixed(4)}
          </div>
          ${stop.status ? `<div style="margin-top: 4px; font-size: 12px;">Condition: <b>${stop.status}</b></div>` : ''}
        </div>
      `);
    }

    // 3. Draw hazard alert markers with interactive popups
    for (const hazard of effectiveHazards) {
      if (typeof hazard.lat !== 'number' || typeof hazard.lon !== 'number') continue;
      allCoords.push([hazard.lat, hazard.lon]);

      const isNoGo = (hazard.severity || '').toLowerCase().includes('no-go');
      const hazardColor = isNoGo ? '#ef4444' : '#f59e0b';

      const hazardIcon = L.divIcon({
        className: 'hazard-pin-div-icon',
        html: `
          <div class="hazard-alert-pin ${isNoGo ? 'severity-nogo' : 'severity-caution'}" data-testid="hazard-pin">
            <span class="hazard-symbol">⚠️</span>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -14]
      });

      const hazardMarker = L.marker([hazard.lat, hazard.lon], { icon: hazardIcon }).addTo(hazardsLayerGroup);

      const weatherHtml = hazard.weather
        ? `
          <div class="hazard-weather-section" style="margin: 6px 0; padding: 6px; background: #f8fafc; border-radius: 4px; font-size: 12px;">
            <div style="font-weight: 600; margin-bottom: 2px;">Weather Conditions:</div>
            <div>Temp: ${hazard.weather.temperature ?? 'N/A'}°</div>
            <div>Wind: ${hazard.weather.wind_speed ?? 'N/A'} mph/kmh</div>
            <div>Rain Chance: ${hazard.weather.precip_prob ?? 0}%</div>
            ${hazard.weather.weather_code ? `<div>Condition Code: ${hazard.weather.weather_code}</div>` : ''}
          </div>
        `
        : (hazard.weather_conditions ? `<div style="font-size: 12px; margin: 4px 0;"><b>Weather:</b> ${hazard.weather_conditions}</div>` : '');

      const risks = hazard.risk_factors || hazard.reasons || ['Adverse weather risk'];
      const risksHtml = `
        <div class="hazard-risk-factors" style="margin-top: 6px;">
          <div style="font-size: 12px; font-weight: 600; color: ${hazardColor};">Localized Risk Factors:</div>
          <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 12px;">
            ${risks.map(r => `<li>${r}</li>`).join('')}
          </ul>
        </div>
      `;

      hazardMarker.bindPopup(`
        <div class="hazard-interactive-popup" style="font-family: inherit; max-width: 240px;" data-testid="hazard-popup-content">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span style="font-size: 16px;">⚠️</span>
            <strong style="color: ${hazardColor}; font-size: 13px;">${hazard.title || hazard.location_name || 'Hazard Alert'}</strong>
          </div>
          <div style="display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; color: white; background: ${hazardColor}; margin-bottom: 6px;">
            ${hazard.severity || 'Caution'}
          </div>
          ${weatherHtml}
          ${risksHtml}
        </div>
      `);
    }

    // 4. Center and bound to route coordinates
    if (allCoords.length > 1) {
      try {
        const bounds = L.latLngBounds(allCoords);
        mapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
      } catch (e) {
        console.warn('Could not fit bounds:', e);
      }
    } else if (allCoords.length === 1) {
      mapInstance.setView(allCoords[0], 12);
    } else {
      mapInstance.setView([51.5074, -0.1278], 11);
    }
  }

  // Reactive redraw whenever inputs change
  $effect(() => {
    // Register dependencies
    const _stops = orderedStops;
    const _segments = effectiveSegments;
    const _hazards = effectiveHazards;
    const _assessment = assessment;
    if (isMounted) {
      renderMapFeatures();
    }
  });
</script>

<div class="route-map-wrapper" data-testid="route-map-wrapper">
  <!-- Route Map Legend -->
  <div class="route-map-legend" data-testid="route-legend">
    <div class="legend-item"><span class="legend-color" style="background-color: var(--route-go, #22c55e);"></span> Go (Safe)</div>
    <div class="legend-item"><span class="legend-color" style="background-color: var(--route-caution, #f59e0b);"></span> Caution (Risk)</div>
    <div class="legend-item"><span class="legend-color" style="background-color: var(--route-nogo, #ef4444);"></span> No-Go (Severe)</div>
    <div class="legend-item"><span class="legend-icon">⚠️</span> Hazard Alert</div>
  </div>

  <!-- Leaflet Map Container -->
  <div
    bind:this={mapContainer}
    class="route-map-canvas"
    style="height: {height};"
    data-testid="route-map-canvas"
    role="region"
    aria-label="Interactive Route Map"
  ></div>

  <!-- Stops and Hazard Summary -->
  <div class="route-summary" data-testid="route-stops-summary">
    {#if orderedStops.length > 0}
      <div class="stops-flow">
        {#each orderedStops as stop}
          <div class="stop-chip {stop.type}" data-testid="stop-chip-{stop.seq}">
            <span class="stop-badge">{stop.seq}</span>
            <span class="stop-name">{stop.name}</span>
          </div>
          {#if stop.seq < orderedStops.length}
            <span class="stop-arrow">→</span>
          {/if}
        {/each}
      </div>
    {:else}
      <p class="empty-route-notice">No route coordinates specified. Add origin and destination to view the route.</p>
    {/if}

    {#if effectiveHazards.length > 0}
      <div class="hazards-alert-bar" data-testid="hazard-alerts-summary">
        <span class="hazard-bar-icon">⚠️</span>
        <span><strong>{effectiveHazards.length}</strong> active hazard pinpoint{effectiveHazards.length > 1 ? 's' : ''} on route</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .route-map-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    border-radius: 8px;
    overflow: hidden;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    border: 1px solid var(--border, #e5e7eb);
  }

  .route-map-legend {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 14px;
    background: #f8fafc;
    border-bottom: 1px solid var(--border, #e5e7eb);
    font-size: 0.85rem;
    font-weight: 500;
    color: #475569;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .legend-color {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    display: inline-block;
  }

  .legend-icon {
    font-size: 14px;
  }

  .route-map-canvas {
    width: 100%;
    min-height: 280px;
    z-index: 1;
    background-color: #f1f5f9;
  }

  .route-summary {
    padding: 10px 14px;
    background: #ffffff;
    border-top: 1px solid var(--border, #e5e7eb);
  }

  .stops-flow {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .stop-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 0.82rem;
    font-weight: 500;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    color: #1e293b;
  }

  .stop-chip.origin {
    border-color: #93c5fd;
    background: #eff6ff;
    color: #1e40af;
  }

  .stop-chip.destination {
    border-color: #99f6e4;
    background: #f0fdfa;
    color: #0f766e;
  }

  .stop-chip.waypoint {
    border-color: #ddd6fe;
    background: #f5f3ff;
    color: #6b21a8;
  }

  .stop-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: currentColor;
    color: white;
    font-size: 0.72rem;
    font-weight: 700;
  }

  .stop-name {
    white-space: nowrap;
  }

  .stop-arrow {
    color: #94a3b8;
    font-weight: bold;
    font-size: 0.85rem;
  }

  .empty-route-notice {
    margin: 0;
    color: #64748b;
    font-size: 0.85rem;
    font-style: italic;
  }

  .hazards-alert-bar {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;
    font-size: 0.82rem;
    color: #92400e;
  }

  /* Custom marker styling injected for Leaflet DivIcons */
  :global(.route-stop-div-icon) {
    background: transparent;
    border: none;
  }

  :global(.route-stop-marker) {
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
  }

  :global(.route-stop-marker .pin-bubble) {
    width: 28px;
    height: 28px;
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    background: var(--pin-color, #3b82f6);
    border: 2px solid #ffffff;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  :global(.route-stop-marker .pin-number) {
    transform: rotate(45deg);
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
  }

  :global(.route-stop-marker .pin-label) {
    font-size: 11px;
    font-weight: 600;
    background: rgba(15, 23, 42, 0.85);
    color: #ffffff;
    padding: 1px 5px;
    border-radius: 4px;
    margin-top: 2px;
    white-space: nowrap;
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  :global(.hazard-pin-div-icon) {
    background: transparent;
    border: none;
  }

  :global(.hazard-alert-pin) {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #ffffff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
    cursor: pointer;
    font-size: 14px;
    animation: hazardPulse 2s infinite ease-in-out;
  }

  :global(.hazard-alert-pin.severity-caution) {
    background: #f59e0b;
  }

  :global(.hazard-alert-pin.severity-nogo) {
    background: #ef4444;
  }

  @keyframes hazardPulse {
    0%, 100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.15);
    }
  }

  /* Responsive styles */
  @media (max-width: 640px) {
    .route-map-canvas {
      min-height: 240px;
      height: 300px !important;
    }

    .route-map-legend {
      gap: 10px;
      font-size: 0.78rem;
      padding: 6px 10px;
    }

    .route-summary {
      padding: 8px 10px;
    }

    .stop-chip {
      font-size: 0.75rem;
      padding: 3px 8px;
    }
  }
</style>
