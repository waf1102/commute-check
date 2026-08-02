<script lang="ts">
  import { onMount } from 'svelte';
  import { user } from '$lib/auth';
  import { getCommuteStats } from '$lib/api';
  import CommuteHistoryChart from '$lib/charts/CommuteHistoryChart.svelte';

  let startDate = $state(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);
  let endDate = $state(new Date().toISOString().split('T')[0]);
  let chartData = $state<any>(null);
  let error = $state<string | null>(null);

  async function fetchHistory() {
    error = null;
    let userId = '';
    const unsubscribe = user.subscribe((u: any) => {
      if (u) userId = u.id;
    });
    unsubscribe();

    try {
      const data = await getCommuteStats(userId, startDate, endDate);
      if (data && data.daily_stats) {
        chartData = {
          labels: data.daily_stats.map((d: any) => d.date),
          datasets: [
            {
              label: 'Days Ridden',
              data: data.daily_stats.map((d: any) => d.days_ridden),
              backgroundColor: 'blue'
            },
            {
              label: 'Days Driven',
              data: data.daily_stats.map((d: any) => d.days_driven),
              backgroundColor: 'red'
            }
          ]
        };
      }
    } catch (e: any) {
      error = `Error fetching commute data: ${e.message || e}`;
    }
  }

  onMount(() => {
    fetchHistory();
  });
</script>

<h1>Commute History</h1>

{#if error}
  <p>{error}</p>
{/if}

<div class="flex gap-4 my-4">
  <label>
    Start Date
    <input type="date" bind:value={startDate} />
  </label>
  <label>
    End Date
    <input type="date" bind:value={endDate} />
  </label>
  <button onclick={fetchHistory}>Refresh</button>
</div>

{#if chartData}
  <CommuteHistoryChart {chartData} />
{/if}
