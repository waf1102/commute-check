<script lang="ts">
    import { onMount } from 'svelte';

    const BACKEND_URL = import.meta.env?.VITE_BACKEND_URL || 'http://localhost:8000';

    let settings = $state({
        name: "My Commute",
        min_temp_caution: 40,
        min_temp_no_go: 35,
        max_wind_caution: 20,
        max_wind_no_go: 35,
        rain_threshold: 50,
        webhook_url: '',
        schedule_time: '07:00',
        days_of_week: 'mon-fri',
        lat: 51.5074,
        lon: -0.1278
    });

    let saved = $state(false);
    let testing = $state(false);
    let testStatus = $state('');

    onMount(async () => {
        try {
            const res = await fetch(`${BACKEND_URL}/config`);
            if (res.ok) {
                const data = await res.json();
                Object.assign(settings, data);
            }
        } catch (e) {
            console.error("Failed to load config from backend", e);
        }
    });

    async function saveSettings(e: Event) {
        e.preventDefault();
        try {
            const res = await fetch(`${BACKEND_URL}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            if (res.ok) {
                saved = true;
                setTimeout(() => saved = false, 3000);
            }
        } catch (e) {
            console.error("Failed to save config to backend", e);
        }
        
        // Keep localStorage as a fallback for the main dashboard for now
        localStorage.setItem('commute-settings', JSON.stringify(settings));
    }

    async function testWebhook() {
        if (!settings.webhook_url) {
            testStatus = 'Please enter a webhook URL first.';
            setTimeout(() => testStatus = '', 3000);
            return;
        }

        testing = true;
        testStatus = 'Testing...';
        try {
            const res = await fetch(`${BACKEND_URL}/test-webhook`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            if (res.ok) {
                testStatus = '✅ Test notification sent!';
            } else {
                testStatus = '❌ Failed to send notification.';
            }
        } catch (e) {
            console.error("Failed to test webhook", e);
            testStatus = '❌ Error triggering test.';
        } finally {
            testing = false;
            setTimeout(() => testStatus = '', 4000);
        }
    }
</script>

<div class="container">
    <h1>Settings</h1>
    
    <div class="card">
        <form onsubmit={saveSettings}>
            <h3>Location</h3>
            <div class="field">
                <label for="lat">Latitude</label>
                <input type="number" step="0.0001" id="lat" bind:value={settings.lat} required>
            </div>
            <div class="field">
                <label for="lon">Longitude</label>
                <input type="number" step="0.0001" id="lon" bind:value={settings.lon} required>
            </div>

            <hr>

            <h3>Temperature Thresholds (°F)</h3>
            <div class="field">
                <label for="tc">Caution Below</label>
                <input type="number" id="tc" bind:value={settings.min_temp_caution}>
            </div>
            <div class="field">
                <label for="tn">No-Go Below</label>
                <input type="number" id="tn" bind:value={settings.min_temp_no_go}>
            </div>

            <hr>

            <h3>Wind Thresholds (mph)</h3>
            <div class="field">
                <label for="wc">Caution Above</label>
                <input type="number" id="wc" bind:value={settings.max_wind_caution}>
            </div>
            <div class="field">
                <label for="wn">No-Go Above</label>
                <input type="number" id="wn" bind:value={settings.max_wind_no_go}>
            </div>

            <hr>

            <h3>Precipitation Threshold</h3>
            <div class="field">
                <label for="rp">Rain Probability % (No-Go)</label>
                <input type="number" min="0" max="100" id="rp" bind:value={settings.rain_threshold}>
            </div>

            <hr>

            <h3>Notification & Scheduling</h3>
            <div class="field">
                <label for="webhook">Webhook URL (Discord/Generic)</label>
                <input type="url" id="webhook" placeholder="https://discord.com/api/webhooks/..." bind:value={settings.webhook_url}>
            </div>
            <div class="field">
                <label for="time">Notification Time</label>
                <input type="time" id="time" bind:value={settings.schedule_time} required>
            </div>
            <div class="field">
                <label for="days">Days of Week (cron format: mon-fri, mon,wed,fri, etc.)</label>
                <input type="text" id="days" bind:value={settings.days_of_week} placeholder="mon-fri" required>
            </div>

            <div class="actions">
                <button type="submit">Save Settings</button>
                <button type="button" class="secondary" onclick={testWebhook} disabled={testing}>Test Webhook</button>
                
                {#if saved}
                    <span class="saved-msg">✅ Saved!</span>
                {/if}
                {#if testStatus}
                    <span class="test-msg">{testStatus}</span>
                {/if}
            </div>
        </form>
    </div>
</div>

<style>
    .field {
        margin-bottom: 15px;
        display: flex;
        flex-direction: column;
    }

    label {
        font-weight: bold;
        margin-bottom: 5px;
        font-size: 0.9rem;
    }

    input {
        padding: 8px;
        border: 1px solid var(--border);
        border-radius: 4px;
        font-size: 1rem;
    }

    hr {
        border: 0;
        border-top: 1px solid var(--border);
        margin: 20px 0;
    }

    .actions {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-top: 20px;
        flex-wrap: wrap;
    }

    button {
        background-color: var(--primary);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 4px;
        font-weight: bold;
        cursor: pointer;
    }

    button:hover {
        opacity: 0.9;
    }
    
    button.secondary {
        background-color: #6c757d;
    }
    
    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .saved-msg, .test-msg {
        color: var(--status-go);
        font-weight: bold;
    }
    
    .test-msg {
        color: #0d6efd;
    }
</style>
