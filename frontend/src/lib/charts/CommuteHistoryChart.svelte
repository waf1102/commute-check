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

  ChartJS.register(
    Title,
    Tooltip,
    Legend,
    LineElement,
    LinearScale,
    CategoryScale,
    PointElement
  );

  // Use runes mode props
  const { chartData, chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Commute History',
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Days',
        },
      },
      x: {
        title: {
          display: true,
          text: 'Date',
        },
      },
    },
  } } = $props<{
    chartData: ChartData<'line'>;
    chartOptions?: ChartOptions<'line'>;
  }>();

</script>

<div style="height: 400px; width: 100%;" data-testid="commute-history-chart">
  <Line data={chartData} options={chartOptions} />
</div>
