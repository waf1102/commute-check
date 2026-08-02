<script lang="ts">
    import { onMount } from 'svelte';

    const BACKEND_URL = import.meta.env?.VITE_BACKEND_URL || 'http://localhost:8000';

    interface CommuteSettings {
        id?: number;
        name: string;
        unit_system: string;
        min_temp_caution: number;
        min_temp_no_go: number;
        max_wind_caution: number;
        max_wind_no_go: number;
        rain_threshold: number;
        webhook_url: string;
        schedule_time: string;
        days_of_week: string;
        lat: number;
        lon: number;
    }

    let commutes = $state<CommuteSettings[]>([]);
    let selectedIndex = $state(-1);
    
    let defaultSettings: CommuteSettings = {
        name: "New Commute",
        unit_system: "imperial",
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
    };

    let settings = $state<CommuteSettings>({ ...defaultSettings });

    let saved = $state(false);
    let testing = $state(false);
    let testStatus = $state('');
    let locStatus = $state('');

    onMount(async () => {
        await loadCommutes();
    });

    async function loadCommutes() {
        try {
            const res = await fetch(`${BACKEND_URL}/config`);
            if (res.ok) {
                const data = await res.json();
                commutes = data;
                if (commutes.length > 0 && selectedIndex === -1) {
                    selectCommute(0);
                } else if (commutes.length === 0) {
                    addNewCommute();
                }
            }
        } catch (e) {
            console.error("Failed to load configs from backend", e);
        }
    }

    function selectCommute(index: number) {
        selectedIndex = index;
        settings = JSON.parse(JSON.stringify(commutes[index]));
    }

    function addNewCommute() {
        selectedIndex = -1;
        settings = { ...defaultSettings };
    }

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
                await loadCommutes();
                if (selectedIndex === -1) {
                    selectCommute(commutes.length - 1);
                }
            }
        } catch (e) {
            console.error("Failed to save config to backend", e);
        }
    }

    async function deleteCommute() {
        if (!settings.id) return;
        if (!confirm("Are you sure you want to delete this commute?")) return;

        try {
            const res = await fetch(`${BACKEND_URL}/config/${settings.id}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                selectedIndex = -1;
                await loadCommutes();
            }
        } catch (e) {
            console.error("Failed to delete config", e);
        }
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

    async function useCurrentLocation() {
        if (!navigator.geolocation) {
            locStatus = "Geolocation is not supported by your browser";
            return;
        }
        
        locStatus = "Locating...";

        const getPosition = (options: PositionOptions): Promise<GeolocationPosition> => 
            new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, options));

        try {
            // Attempt 1: High Accuracy
            const position = await getPosition({ enableHighAccuracy: true, timeout: 8000, maximumAge: 0 });
            settings.lat = parseFloat(position.coords.latitude.toFixed(4));
            settings.lon = parseFloat(position.coords.longitude.toFixed(4));
            locStatus = "✅ Location updated";
            setTimeout(() => { if (locStatus === "✅ Location updated") locStatus = ''; }, 3000);
        } catch (error: any) {
            // If permission denied, don't retry
            if (error.code === error.PERMISSION_DENIED) {
                locStatus = "❌ Permission denied. Check browser settings.";
                setTimeout(() => locStatus = '', 5000);
                return;
            }

            console.warn("High accuracy failed, retrying with standard accuracy...", error);
            locStatus = "Retrying...";

            try {
                // Attempt 2: Standard Accuracy
                const position = await getPosition({ enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });
                settings.lat = parseFloat(position.coords.latitude.toFixed(4));
                settings.lon = parseFloat(position.coords.longitude.toFixed(4));
                locStatus = "✅ Location updated (approximate)";
                setTimeout(() => { if (locStatus === "✅ Location updated (approximate)") locStatus = ''; }, 3000);
            } catch (error2: any) {
                console.error("Geolocation fallback failed:", error2);
                if (error2.code === error2.POSITION_UNAVAILABLE) {
                    locStatus = "❌ Position unavailable. Try manual entry or check OS settings.";
                } else if (error2.code === error2.TIMEOUT) {
                    locStatus = "❌ Request timed out. Try again or enter manually.";
                } else {
                    locStatus = "❌ Unable to retrieve location. Please enter manually.";
                }
                setTimeout(() => { if (locStatus.startsWith('❌')) locStatus = ''; }, 8000);
            }
        }
    }
</script>

<div class="container layout">
    <div class="sidebar card">
        <h3>Your Commutes</h3>
        <ul class="commute-list">
            {#each commutes as commute, i}
                <li>
                    <button type="button" class="list-btn {i === selectedIndex ? 'active' : ''}" onclick={() => selectCommute(i)}>
                        {commute.name} ({commute.schedule_time})
                    </button>
                </li>
            {/each}
        </ul>
        <button type="button" class="add-btn" onclick={addNewCommute}>+ Add New Commute</button>
    </div>

    <div class="main-content card">
        <h1>{settings.id ? 'Edit Commute' : 'New Commute'}</h1>
        <form onsubmit={saveSettings}>
            <div class="field">
                <label for="name">Commute Name</label>
                <input type="text" id="name" bind:value={settings.name} required>
            </div>

            <hr>

            <h3>Preferences</h3>
            <div class="field">
                <label for="unit_system">Unit System</label>
                <select id="unit_system" bind:value={settings.unit_system}>
                    <option value="imperial">Imperial (°F / mph)</option>
                    <option value="metric">Metric (°C / km/h)</option>
                </select>
            </div>

            <hr>

            <h3>Location</h3>
            <div class="field-row">
                <div class="field flex-1">
                    <label for="lat">Latitude</label>
                    <input type="number" step="0.0001" id="lat" bind:value={settings.lat} required>
                </div>
                <div class="field flex-1">
                    <label for="lon">Longitude</label>
                    <input type="number" step="0.0001" id="lon" bind:value={settings.lon} required>
                </div>
            </div>
            <button type="button" class="secondary small-btn" onclick={useCurrentLocation}>📍 Use Current Location</button>
            {#if locStatus}
                <span class="status-msg">{locStatus}</span>
            {/if}

            <hr>

            <h3>Temperature Thresholds ({settings.unit_system === 'metric' ? '°C' : '°F'})</h3>
            <div class="field">
                <label for="tc">Caution Below</label>
                <input type="number" id="tc" bind:value={settings.min_temp_caution}>
            </div>
            <div class="field">
                <label for="tn">No-Go Below</label>
                <input type="number" id="tn" bind:value={settings.min_temp_no_go}>
            </div>

            <hr>

            <h3>Wind Thresholds ({settings.unit_system === 'metric' ? 'km/h' : 'mph'})</h3>
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
                <label for="webhook">Notification URL (Apprise Compatible)</label>
                <input type="url" id="webhook" placeholder="discord://... or tgram://..." bind:value={settings.webhook_url}>
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
                <button type="submit">Save Commute</button>
                <button type="button" class="secondary" onclick={testWebhook} disabled={testing}>Test Notification</button>
                {#if settings.id}
                    <button type="button" class="danger" onclick={deleteCommute}>Delete</button>
                {/if}
                
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
    .layout {
        display: flex;
        gap: 20px;
        align-items: flex-start;
    }

    @media (max-width: 768px) {
        .layout {
            flex-direction: column;
        }
        .sidebar, .main-content {
            width: 100%;
            box-sizing: border-box;
        }
    }

    .sidebar {
        flex: 1;
        min-width: 250px;
    }

    .main-content {
        flex: 3;
    }

    .commute-list {
        list-style: none;
        padding: 0;
        margin: 0 0 20px 0;
    }

    .commute-list li {
        margin-bottom: 5px;
    }

    .list-btn {
        width: 100%;
        text-align: left;
        background: transparent;
        color: var(--text);
        border: 1px solid var(--border);
    }

    .list-btn.active {
        background: var(--primary);
        color: white;
        border-color: var(--primary);
    }

    .add-btn {
        width: 100%;
        background-color: var(--status-go);
    }

    .field {
        margin-bottom: 15px;
        display: flex;
        flex-direction: column;
    }

    .field-row {
        display: flex;
        gap: 15px;
    }

    .flex-1 {
        flex: 1;
    }

    label {
        font-weight: bold;
        margin-bottom: 5px;
        font-size: 0.9rem;
    }

    input, select {
        padding: 8px;
        border: 1px solid var(--border);
        border-radius: 4px;
        font-size: 1rem;
        background-color: var(--card-bg, #fff);
        color: var(--text, #333);
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

    button.danger {
        background-color: var(--status-nogo);
    }

    button.small-btn {
        padding: 6px 12px;
        font-size: 0.9rem;
        margin-bottom: 15px;
    }
    
    button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .saved-msg, .test-msg, .status-msg {
        font-weight: bold;
    }

    .saved-msg {
        color: var(--status-go);
    }
    
    .test-msg {
        color: #0d6efd;
    }

    .status-msg {
        font-size: 0.9rem;
        margin-left: 10px;
    }
</style>
