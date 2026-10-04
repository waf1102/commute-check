<script lang="ts">
  import { onMount } from 'svelte';
  import { user } from '$lib/auth';
  import { getCommuteStats, recordDecision } from '$lib/api';
  import CommuteHistoryChart from '$lib/charts/CommuteHistoryChart.svelte';

  let startDate = $state(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);
  let endDate = $state(new Date().toISOString().split('T')[0]);
  let chartData = $state<any>(null);
  let error = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let isRecording = $state(false);

  async function fetchHistory() {
    error = null;
    let userId: string | undefined = undefined;
    const unsubscribe = user.subscribe((u: any) => {
      if (u && u.id) userId = String(u.id);
    });
    unsubscribe();

    try {
      const data = await getCommuteStats(userId, startDate, endDate);
      const dailyStats = Array.isArray(data)
        ? data
        : (data && Array.isArray(data.daily_stats) ? data.daily_stats : []);

      chartData = {
        labels: dailyStats.map((d: any) => d.date),
        datasets: [
          {
            label: 'Days Ridden',
            data: dailyStats.map((d: any) => d.days_ridden),
            backgroundColor: 'blue',
            borderColor: 'blue'
          },
          {
            label: 'Days Driven',
            data: dailyStats.map((d: any) => d.days_driven),
            backgroundColor: 'red',
            borderColor: 'red'
          }
        ]
      };
    } catch (e: any) {
      error = `Error fetching commute data: ${e.message || e}`;
    }
  }

  async function handleRecordDecision(decision: 'riding' | 'driving') {
    isRecording = true;
    error = null;
    successMessage = null;
    try {
      await recordDecision({ decision });
      successMessage = `Recorded today's commute as ${decision === 'riding' ? 'Riding 🏍️' : 'Driving 🚗'}!`;
      await fetchHistory();
    } catch (e: any) {
      error = `Error recording decision: ${e.message || e}`;
    } finally {
      isRecording = false;
    }
  }

  onMount(() => {
    fetchHistory();
  });
</script>

<h1>Commute History</h1>

{#if error}
  <p class="text-red-500 my-2">{error}</p>
{/if}

{#if successMessage}
  <p class="text-green-600 my-2">{successMessage}</p>
{/if}

<div class="flex gap-4 my-4 items-center flex-wrap">
  <label>
    Start Date
    <input type="date" bind:value={startDate} />
  </label>
  <label>
    End Date
    <input type="date" bind:value={endDate} />
  </label>
  <button onclick={fetchHistory}>Refresh</button>

  <div class="flex gap-2 items-center ml-auto">
    <span class="text-sm font-semibold">Log Today:</span>
    <button
      class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
      disabled={isRecording}
      onclick={() => handleRecordDecision('riding')}
    >
      🏍️ Rode
    </button>
    <button
      class="bg-gray-600 text-white px-3 py-1 rounded hover:bg-gray-700 disabled:opacity-50"
      disabled={isRecording}
      onclick={() => handleRecordDecision('driving')}
    >
      🚗 Drove
    </button>
  </div>
</div>

{#if chartData}
  <CommuteHistoryChart {chartData} />
{/if}

