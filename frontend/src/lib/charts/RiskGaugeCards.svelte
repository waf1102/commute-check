<script lang="ts">
  import type { Thresholds } from '$lib/api';

  const {
    currentTemp = 0,
    currentWind = 0,
    currentPrecip = 0,
    thresholds,
    unitSystem = 'imperial'
  } = $props<{
    currentTemp?: number;
    currentWind?: number;
    currentPrecip?: number;
    thresholds?: Partial<Thresholds>;
    unitSystem?: string;
  }>();

  // Fallback default thresholds for null safety when thresholds object is loading/undefined
  const minTempCaution = $derived(thresholds?.min_temp_caution ?? 45);
  const minTempNoGo = $derived(thresholds?.min_temp_no_go ?? 38);
  const maxWindCaution = $derived(thresholds?.max_wind_caution ?? 15);
  const maxWindNoGo = $derived(thresholds?.max_wind_no_go ?? 25);
  const rainThreshold = $derived(thresholds?.rain_threshold ?? 30);

  const tempStatus = $derived.by(() => {
    if (currentTemp <= minTempNoGo) {
      return { label: 'No-Go', bg: 'bg-red-100 text-red-800 border-red-200' };
    }
    if (currentTemp <= minTempCaution) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  });

  const windStatus = $derived.by(() => {
    if (currentWind >= maxWindNoGo) {
      return { label: 'No-Go', bg: 'bg-red-100 text-red-800 border-red-200' };
    }
    if (currentWind >= maxWindCaution) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  });

  const rainStatus = $derived.by(() => {
    if (currentPrecip >= rainThreshold) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  });
</script>

<div class="grid grid-cols-1 md:grid-cols-3 gap-4 my-6" data-testid="risk-gauge-cards" role="region" aria-label="Weather Risk Status Gauges">
  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Temperature</p>
      <p class="text-2xl font-bold text-gray-900">{currentTemp}°{unitSystem === 'imperial' ? 'F' : 'C'}</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {tempStatus.bg}">
      {tempStatus.label}
    </span>
  </div>

  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Wind Speed</p>
      <p class="text-2xl font-bold text-gray-900">{currentWind} {unitSystem === 'imperial' ? 'mph' : 'km/h'}</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {windStatus.bg}">
      {windStatus.label}
    </span>
  </div>

  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Rain Prob.</p>
      <p class="text-2xl font-bold text-gray-900">{currentPrecip}%</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {rainStatus.bg}">
      {rainStatus.label}
    </span>
  </div>
</div>
