<script lang="ts">
  import type { Thresholds } from '$lib/api';

  const {
    currentTemp,
    currentWind,
    currentPrecip,
    thresholds,
    unitSystem = 'imperial'
  } = $props<{
    currentTemp: number;
    currentWind: number;
    currentPrecip: number;
    thresholds: Thresholds;
    unitSystem?: string;
  }>();

  function getTempStatus() {
    if (currentTemp <= thresholds.min_temp_no_go) {
      return { label: 'No-Go', bg: 'bg-red-100 text-red-800 border-red-200' };
    }
    if (currentTemp <= thresholds.min_temp_caution) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  }

  function getWindStatus() {
    if (currentWind >= thresholds.max_wind_no_go) {
      return { label: 'No-Go', bg: 'bg-red-100 text-red-800 border-red-200' };
    }
    if (currentWind >= thresholds.max_wind_caution) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  }

  function getRainStatus() {
    if (currentPrecip >= thresholds.rain_threshold) {
      return { label: 'Caution', bg: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    }
    return { label: 'Go', bg: 'bg-green-100 text-green-800 border-green-200' };
  }
</script>

<div class="grid grid-cols-1 md:grid-cols-3 gap-4 my-6" data-testid="risk-gauge-cards">
  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Temperature</p>
      <p class="text-2xl font-bold text-gray-900">{currentTemp}°{unitSystem === 'imperial' ? 'F' : 'C'}</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {getTempStatus().bg}">
      {getTempStatus().label}
    </span>
  </div>

  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Wind Speed</p>
      <p class="text-2xl font-bold text-gray-900">{currentWind} {unitSystem === 'imperial' ? 'mph' : 'km/h'}</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {getWindStatus().bg}">
      {getWindStatus().label}
    </span>
  </div>

  <div class="p-4 rounded-xl border border-gray-200 bg-white shadow-sm flex justify-between items-center">
    <div>
      <p class="text-sm font-medium text-gray-500">Rain Prob.</p>
      <p class="text-2xl font-bold text-gray-900">{currentPrecip}%</p>
    </div>
    <span class="px-3 py-1 rounded-full text-xs font-semibold border {getRainStatus().bg}">
      {getRainStatus().label}
    </span>
  </div>
</div>
