<script lang="ts">
    import { onMount } from 'svelte';

    let settings = $state({
        min_temp_caution: 40,
        min_temp_no_go: 35,
        max_wind_caution: 20,
        max_wind_no_go: 35,
        rain_threshold: 50,
        webhook_url: '',
        lat: 51.5074,
        lon: -0.1278
    });

    let saved = $state(false);

    onMount(() => {
        const stored = localStorage.getItem('commute-settings');
        if (stored) {
            const parsed = JSON.parse(stored);
            Object.assign(settings, parsed);
        }
    });

    function saveSettings(e: Event) {
        e.preventDefault();
        localStorage.setItem('commute-settings', JSON.stringify(settings));
        saved = true;
        setTimeout(() => saved = false, 3000);
    }
</script>

<div class="container">
    <h1>Settings</h1>
    
    <div class="card">
        <form onsubmit={saveSettings}>
            <h3>Location</h3>
            <div class="field">
                <label for="lat">Latitude</label>
                <input type="number" step="0.0001" id="lat" bind:value={settings.lat}>
            </div>
            <div class="field">
                <label for="lon">Longitude</label>
                <input type="number" step="0.0001" id="lon" bind:value={settings.lon}>
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

            <h3>Wind Thresholds (km/h)</h3>
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

            <h3>Notification</h3>
            <div class="field">
                <label for="webhook">Webhook URL (Discord/Generic)</label>
                <input type="url" id="webhook" placeholder="https://discord.com/api/webhooks/..." bind:value={settings.webhook_url}>
            </div>

            <div class="actions">
                <button type="submit">Save Settings</button>
                {#if saved}
                    <span class="saved-msg">✅ Saved!</span>
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

    .saved-msg {
        color: var(--status-go);
        font-weight: bold;
    }
</style>
