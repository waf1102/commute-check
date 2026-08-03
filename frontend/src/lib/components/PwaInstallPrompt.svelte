<script lang="ts">
  import { onMount } from 'svelte';

  let deferredPrompt = $state<any>(null);
  let showPrompt = $state<boolean>(false);

  onMount(() => {
    if (typeof window !== 'undefined') {
      const handleBeforeInstallPrompt = (e: Event) => {
        e.preventDefault();
        deferredPrompt = e;
        showPrompt = true;
      };

      window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

      return () => {
        window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      };
    }
  });

  async function installPwa() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    if (deferredPrompt.userChoice) {
      const choice = await deferredPrompt.userChoice;
      if (choice && choice.outcome === 'accepted') {
        showPrompt = false;
      }
    } else {
      showPrompt = false;
    }
    deferredPrompt = null;
  }
</script>

{#if showPrompt}
  <div class="card pwa-install-banner" data-testid="pwa-install-prompt">
    <div class="pwa-content">
      <span>📱 Install Commute Check app on your home screen for quick access.</span>
      <button onclick={installPwa} class="btn-install">
        Install App
      </button>
    </div>
  </div>
{/if}

<style>
  .pwa-install-banner {
    background-color: #e7f5ff;
    border: 1px solid #74c0fc;
    color: #1864ab;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 20px;
  }

  .pwa-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    font-size: 0.95rem;
    font-weight: 500;
  }

  .btn-install {
    background-color: var(--primary);
    color: white;
    border: none;
    padding: 6px 14px;
    border-radius: 4px;
    font-weight: bold;
    font-size: 0.85rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .btn-install:hover {
    opacity: 0.9;
  }
</style>
