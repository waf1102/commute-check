<script lang="ts">
  import { onMount } from 'svelte';

  let isOffline = $state<boolean>(false);

  onMount(() => {
    if (typeof window !== 'undefined') {
      isOffline = !navigator.onLine;

      const handleOnline = () => {
        isOffline = false;
      };
      const handleOffline = () => {
        isOffline = true;
      };

      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
  });
</script>

{#if isOffline}
  <div class="offline-banner" role="status" data-testid="offline-banner">
    <span>You are offline. Reconnect and refresh before relying on a forecast.</span>
  </div>
{/if}

<style>
  .offline-banner {
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeeba;
    padding: 10px 16px;
    border-radius: 6px;
    margin-bottom: 20px;
    text-align: center;
    font-weight: 500;
    font-size: 0.95rem;
  }
</style>
