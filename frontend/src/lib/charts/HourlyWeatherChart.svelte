<script lang="ts">
  import { Line } from 'svelte-chartjs';
  import {
    Chart as ChartJS,
    Title,
    Tooltip,
    Legend,
    LineElement,
    LinearScale,
    CategoryScale,
    PointElement,
    type ChartData,
    type ChartOptions
  } from 'chart.js';
  import type { HourlyForecastItem, Thresholds } from '$lib/api';

  ChartJS.register(
    Title,
    Tooltip,
    Legend,
    LineElement,
    LinearScale,
    CategoryScale,
    PointElement
  );

  const props = $props<{
    hourlyData?: HourlyForecastItem[];
    destinationHourlyData?: HourlyForecastItem[];
    destination_hourly?: HourlyForecastItem[];
    thresholds?: Partial<Thresholds>;
  }>();

  let activeLocation = $state<'origin' | 'destination'>('origin');

  const destHourly = $derived(props.destinationHourlyData || props.destination_hourly);
  const hasDestination = $derived(!!(destHourly && destHourly.length > 0));

  const activeHourlyData = $derived(
    activeLocation === 'destination' && destHourly ? destHourly : (props.hourlyData || [])
  );

  const labels = $derived(
    (activeHourlyData || []).map((h: HourlyForecastItem) => {
      try {
        const date = new Date(h.time);
        if (isNaN(date.getTime())) return h.time;
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch {
        return h.time;
      }
    })
  );

  const chartData = $derived<ChartData<'line'>>({
    labels,
    datasets: [
      {
        label: 'Temperature',
        data: (activeHourlyData || []).map((h: HourlyForecastItem) => h.temperature),
        borderColor: '#3b82f6',
        backgroundColor: '#3b82f6',
        yAxisID: 'y',
        tension: 0.3
      },
      {
        label: 'Wind Speed',
        data: (activeHourlyData || []).map((h: HourlyForecastItem) => h.wind_speed),
        borderColor: '#f59e0b',
        backgroundColor: '#f59e0b',
        yAxisID: 'y',
        tension: 0.3
      },
      {
        label: 'Rain Probability (%)',
        data: (activeHourlyData || []).map((h: HourlyForecastItem) => h.precip_prob),
        borderColor: '#06b6d4',
        backgroundColor: '#06b6d4',
        yAxisID: 'y1',
        tension: 0.3
      }
    ]
  });

  const chartOptions = $derived<ChartOptions<'line'>>({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' as const },
      title: {
        display: true,
        text: activeLocation === 'destination' ? 'Hourly Weather Forecast (Destination)' : 'Hourly Weather Forecast (Origin)'
      }
    },
    scales: {
      x: {
        title: { display: true, text: 'Time' }
      },
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: { display: true, text: 'Temp / Wind' }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        grid: { drawOnChartArea: false },
        min: 0,
        max: 100,
        title: { display: true, text: 'Rain Prob (%)' }
      }
    }
  });
</script>

<div class="h-80 w-full p-4 bg-white rounded-xl shadow-sm border border-gray-200" data-testid="hourly-weather-chart" role="region" aria-label="Hourly Weather Forecast Chart">
  {#if hasDestination}
    <div class="flex gap-2 mb-3 location-toggle" data-testid="location-toggle">
      <button
        type="button"
        class="px-3 py-1 text-sm font-medium rounded-md transition-colors {activeLocation === 'origin' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}"
        aria-pressed={activeLocation === 'origin'}
        onclick={() => (activeLocation = 'origin')}
      >
        Origin
      </button>
      <button
        type="button"
        class="px-3 py-1 text-sm font-medium rounded-md transition-colors {activeLocation === 'destination' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}"
        aria-pressed={activeLocation === 'destination'}
        onclick={() => (activeLocation = 'destination')}
      >
        Destination
      </button>
    </div>
  {/if}
  <div class="h-64 w-full">
    <Line data={chartData} options={chartOptions} />
  </div>
</div>
