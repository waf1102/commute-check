<script lang="ts">
  import { onMount } from 'svelte';
  import {
    getVapidPublicKey,
    subscribePush,
    unsubscribePush,
    sendTestPush,
    urlBase64ToUint8Array
  } from '$lib/api';

  let permissionState = $state<string>('default');
  let isSubscribed = $state<boolean>(false);
  let loading = $state<boolean>(false);
  let message = $state<string>('');
  let isSupported = $state<boolean>(true);

  onMount(async () => {
    if (typeof window === 'undefined' || !('Notification' in window) || !('serviceWorker' in navigator)) {
      isSupported = false;
      return;
    }

    permissionState = Notification.permission;

    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      isSubscribed = !!sub;
    } catch (e) {
      console.error('Error checking push subscription:', e);
    }
  });

  async function togglePush() {
    if (!isSupported) {
      message = 'Push notifications are not supported in this browser.';
      return;
    }

    loading = true;
    message = '';

    try {
      if (!isSubscribed) {
        const perm = await Notification.requestPermission();
        permissionState = perm;

        if (perm !== 'granted') {
          message = 'Notification permission denied by user.';
          loading = false;
          return;
        }

        const { public_key } = await getVapidPublicKey();
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource
        });

        const subObj = sub.toJSON();
        await subscribePush({
          endpoint: subObj.endpoint || sub.endpoint,
          keys: {
            p256dh: subObj.keys?.p256dh || '',
            auth: subObj.keys?.auth || ''
          }
        });

        isSubscribed = true;
        message = 'Web Push notifications enabled successfully!';
      } else {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();

        if (sub) {
          try {
            await unsubscribePush(sub.endpoint);
          } catch (err) {
            console.error('Error unsubscribing on backend:', err);
          }
          await sub.unsubscribe();
        }

        isSubscribed = false;
        message = 'Web Push notifications disabled.';
      }
    } catch (err: any) {
      message = err.message || 'An error occurred while updating push notification status.';
    } finally {
      loading = false;
    }
  }

  async function handleTestPush() {
    loading = true;
    message = '';

    try {
      const res = await sendTestPush();
      message = `Test notification dispatched! (${res.delivered || 1} delivered)`;
    } catch (err: any) {
      message = err.message || 'Failed to dispatch test notification.';
    } finally {
      loading = false;
    }
  }
</script>

<div class="card push-toggle-card" data-testid="push-notification-toggle">
  <div class="push-header">
    <div>
      <h3>🔔 Push Notifications</h3>
      <p class="description">
        Get instant Go/No-Go commute safety alerts on your device.
      </p>
    </div>
    {#if isSupported}
      <button
        onclick={togglePush}
        disabled={loading}
        class="toggle-btn {isSubscribed ? 'btn-active' : 'btn-primary'}"
      >
        {isSubscribed ? 'Disable Push' : 'Enable Push'}
      </button>
    {/if}
  </div>

  {#if !isSupported}
    <p class="warning-text">Push notifications are not supported in this browser environment.</p>
  {:else if isSubscribed}
    <div class="push-actions">
      <span class="status-active">● Subscribed on this device</span>
      <button
        onclick={handleTestPush}
        disabled={loading}
        class="btn-secondary"
      >
        Send Test Notification
      </button>
    </div>
  {/if}

  {#if message}
    <p class="status-message">{message}</p>
  {/if}
</div>

<style>
  .push-toggle-card {
    border: 1px solid var(--border);
    border-radius: 8px;
    background-color: var(--card-bg);
    padding: 20px;
    margin-bottom: 20px;
  }

  .push-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
  }

  .push-header h3 {
    margin: 0;
    font-size: 1.25rem;
  }

  .description {
    margin: 4px 0 0 0;
    color: #666;
    font-size: 0.9rem;
  }

  .toggle-btn {
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: bold;
    cursor: pointer;
    border: none;
    transition: background-color 0.2s;
  }

  .btn-primary {
    background-color: var(--primary);
    color: white;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-active {
    background-color: var(--status-nogo);
    color: white;
  }

  .btn-active:hover {
    opacity: 0.9;
  }

  .push-actions {
    margin-top: 15px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .status-active {
    color: var(--status-go);
    font-weight: bold;
    font-size: 0.85rem;
  }

  .btn-secondary {
    padding: 6px 12px;
    background-color: #6c757d;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .btn-secondary:hover {
    opacity: 0.9;
  }

  .warning-text {
    margin-top: 10px;
    color: var(--status-caution);
    font-size: 0.9rem;
  }

  .status-message {
    margin-top: 12px;
    padding: 8px 12px;
    background-color: #f1f3f5;
    border-radius: 4px;
    font-size: 0.85rem;
    color: var(--text);
  }
</style>
