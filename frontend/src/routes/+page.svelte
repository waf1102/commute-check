<script lang="ts">
    import { onMount } from 'svelte';
    import type { PageData } from './$types';
    import { getWeatherForecast, checkRoute, type ForecastResponse } from '$lib/api';
    import RiskGaugeCards from '$lib/charts/RiskGaugeCards.svelte';
    import HourlyWeatherChart from '$lib/charts/HourlyWeatherChart.svelte';
    import LegRiskCard from '$lib/components/LegRiskCard.svelte';
    import OfflineBanner from '$lib/components/OfflineBanner.svelte';
    import PwaInstallPrompt from '$lib/components/PwaInstallPrompt.svelte';
    import PushNotificationToggle from '$lib/components/PushNotificationToggle.svelte';

    let { data }: { data: PageData } = $props();

    let forecast = $state<ForecastResponse | null>(null);
    let assessmentsOverride = $state<any[] | null>(null);
    let activeAssessments = $derived(assessmentsOverride ?? (data.assessments || []));
    let selectedIndex = $state(0);

    let selectedCommute = $derived(
        activeAssessments.length > 0
            ? (activeAssessments[selectedIndex] ?? activeAssessments[0])
            : null
    );

    let dest_name = $state('');
    let dest_lat = $state<number | null>(null);
    let dest_lon = $state<number | null>(null);
    let return_schedule_time = $state('17:00');

    onMount(async () => {
        const initial = (activeAssessments.length > 0 ? activeAssessments[selectedIndex] : null) ||
                        (data.assessments && data.assessments.length > 0 ? data.assessments[0] : null);
        if (initial) {
            if (initial.dest_name) dest_name = initial.dest_name;
            if (initial.dest_lat !== undefined && initial.dest_lat !== null) dest_lat = initial.dest_lat;
            if (initial.dest_lon !== undefined && initial.dest_lon !== null) dest_lon = initial.dest_lon;
            if (initial.return_schedule_time) return_schedule_time = initial.return_schedule_time;
            try {
                forecast = await getWeatherForecast(initial.id, initial.unit_system || 'imperial', dest_lat, dest_lon);
            } catch (e) {
                console.error('Error fetching weather forecast:', e);
            }
        } else {
            try {
                forecast = await getWeatherForecast(undefined, 'imperial', dest_lat, dest_lon);
            } catch (e) {
                console.error('Error fetching weather forecast:', e);
            }
        }

        const focusVisualizer = () => {
            if (typeof window !== 'undefined' && window.location.hash === '#route-visualizer') {
                const el = document.getElementById('route-visualizer');
                if (el) {
                    if (typeof el.scrollIntoView === 'function') {
                        el.scrollIntoView({ behavior: 'smooth' });
                    }
                    el.focus();
                }
            }
        };
        focusVisualizer();
        if (typeof window !== 'undefined') {
            window.addEventListener('hashchange', focusVisualizer);
        }
    });

    async function selectCommute(index: number) {
        if (index < 0 || index >= activeAssessments.length) return;
        selectedIndex = index;
        const commute = activeAssessments[index];
        if (!commute) return;

        dest_name = commute.dest_name || '';
        dest_lat = commute.dest_lat ?? null;
        dest_lon = commute.dest_lon ?? null;
        return_schedule_time = commute.return_schedule_time || '17:00';

        try {
            forecast = await getWeatherForecast(
                commute.id,
                commute.unit_system || 'imperial',
                dest_lat,
                dest_lon
            );
        } catch (e) {
            console.error('Error fetching weather forecast:', e);
            forecast = null;
        }
    }

    async function checkDestinationWeather(e?: Event) {
        if (e) e.preventDefault();
        try {
            const current = selectedCommute;
            forecast = await getWeatherForecast(current?.id, current?.unit_system || 'imperial', dest_lat, dest_lon);
            if (current) {
                const newAssessment = await checkRoute({
                    commute_id: current.id,
                    lat: current.lat,
                    lon: current.lon,
                    dest_name,
                    dest_lat,
                    dest_lon,
                    schedule_time: current.schedule_time || '08:00',
                    return_schedule_time
                });
                assessmentsOverride = activeAssessments.map((item, idx) =>
                    idx === selectedIndex
                        ? { ...item, dest_name, dest_lat, dest_lon, return_schedule_time, assessment: newAssessment }
                        : item
                );
            }
        } catch (err) {
            console.error('Error updating forecast with destination:', err);
        }
    }

    const statusIcons: Record<string, string> = {
        'Go': '🟢',
        'Caution': '🟡',
        'No-Go': '🔴'
    };

    const statusClasses: Record<string, string> = {
        'Go': 'status-go',
        'Caution': 'status-caution',
        'No-Go': 'status-nogo'
    };
</script>

<div class="container">
    <OfflineBanner />
    <PwaInstallPrompt />

    <h1>Commute Check Dashboard</h1>

    <PushNotificationToggle />

    {#if activeAssessments && activeAssessments.length > 1}
        <section class="card commute-switcher-card" data-testid="commute-switcher">
            <div class="switcher-header">
                <label for="commute-select" class="switcher-label">Select Commute:</label>
                <select
                    id="commute-select"
                    data-testid="commute-select"
                    class="commute-select"
                    value={selectedIndex}
                    onchange={(e) => selectCommute(Number((e.target as HTMLSelectElement).value))}
                    aria-label="Select Commute"
                >
                    {#each activeAssessments as item, idx}
                        <option value={idx}>{item.name} ({item.schedule_time})</option>
                    {/each}
                </select>
            </div>
            <div class="commute-tabs" role="tablist" aria-label="Commute selector tabs">
                {#each activeAssessments as item, idx}
                    <button
                        type="button"
                        role="tab"
                        class="commute-tab-btn {idx === selectedIndex ? 'active' : ''}"
                        aria-selected={idx === selectedIndex}
                        onclick={() => selectCommute(idx)}
                    >
                        {item.name}
                    </button>
                {/each}
            </div>
        </section>
    {/if}

    <section class="card destination-config-card">
        <h3>Route & Destination Configuration</h3>
        <form onsubmit={checkDestinationWeather} class="destination-form">
            <div class="field">
                <label for="dest_name">Destination Name</label>
                <input type="text" id="dest_name" bind:value={dest_name} placeholder="e.g. Office" />
            </div>
            <div class="field-row">
                <div class="field flex-1">
                    <label for="dest_lat">Destination Latitude</label>
                    <input type="number" step="0.0001" id="dest_lat" bind:value={dest_lat} placeholder="e.g. 37.7749" />
                </div>
                <div class="field flex-1">
                    <label for="dest_lon">Destination Longitude</label>
                    <input type="number" step="0.0001" id="dest_lon" bind:value={dest_lon} placeholder="e.g. -122.4194" />
                </div>
            </div>
            <div class="field">
                <label for="return_schedule_time">Return Schedule Time</label>
                <input type="time" id="return_schedule_time" bind:value={return_schedule_time} />
            </div>
            <button type="submit" class="update-btn">Update Route Forecast</button>
        </form>
    </section>

    {#if data.error}
        <div class="card" style="border-color: var(--status-nogo)">
            <p>{data.error}</p>
        </div>
    {:else if selectedCommute}
        <div class="dashboard-grid">
            <div class="commute-panel" id="route-visualizer" tabindex="-1" data-testid="route-assessment-card">
                <h2>{selectedCommute.name} <span class="time-badge">{selectedCommute.schedule_time}</span></h2>
                
                {#if selectedCommute.error}
                    <div class="card" style="border-color: var(--status-nogo)">
                        <p>Error: {selectedCommute.error}</p>
                    </div>
                {:else if selectedCommute.assessment?.outbound_leg || selectedCommute?.outbound_leg}
                    <LegRiskCard
                        outboundLeg={selectedCommute.assessment?.outbound_leg || selectedCommute?.outbound_leg}
                        returnLeg={selectedCommute.assessment?.return_leg || selectedCommute?.return_leg}
                    />
                {:else if selectedCommute.assessment}
                    <div class="card assessment-card">
                        <div class="status-icon">
                            {statusIcons[selectedCommute.assessment.status] || '❓'}
                        </div>
                        <h2 class={statusClasses[selectedCommute.assessment.status]}>
                            {selectedCommute.assessment.status}
                        </h2>
                        <p class="recommendation">{selectedCommute.assessment.recommendation}</p>
                    </div>

                    <div class="card weather-card">
                        <h3>Weather Details</h3>
                        <div class="metrics">
                            <div class="metric">
                                <span>Temperature</span>
                                <span>{selectedCommute.assessment.details?.temperature?.toFixed(1) ?? 'N/A'}{selectedCommute.unit_system === 'metric' ? '°C' : '°F'}</span>
                            </div>
                            <div class="metric">
                                <span>Wind Speed</span>
                                <span>{selectedCommute.assessment.details?.wind_speed?.toFixed(1) ?? 'N/A'} {selectedCommute.unit_system === 'metric' ? 'km/h' : 'mph'}</span>
                            </div>
                            <div class="metric">
                                <span>Rain Probability</span>
                                <span>{selectedCommute.assessment.details?.precip_prob ?? 'N/A'}%</span>
                            </div>
                            <div class="metric score">
                                <span>Safety Score</span>
                                <span>{selectedCommute.assessment.score}/100</span>
                            </div>
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    {#if forecast && forecast.hourly && forecast.hourly.length > 0}
        <section class="weather-visualizations">
            <h2>Weather Visualizations</h2>
            <RiskGaugeCards
                currentTemp={forecast.hourly[0].temperature}
                currentWind={forecast.hourly[0].wind_speed}
                currentPrecip={forecast.hourly[0].precip_prob}
                thresholds={forecast.thresholds}
                unitSystem={forecast.unit_system}
            />
            <HourlyWeatherChart
                hourlyData={forecast.hourly}
                destination_hourly={forecast.destination_hourly}
                thresholds={forecast.thresholds}
            />
        </section>
    {/if}
</div>

<style>
    .commute-switcher-card {
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .switcher-header {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }

    .switcher-label {
        font-weight: 600;
        font-size: 0.95rem;
        color: #374151;
    }

    .commute-select {
        padding: 8px 12px;
        border: 1px solid var(--border, #d1d5db);
        border-radius: 6px;
        font-size: 0.95rem;
        background: white;
        min-width: 220px;
        color: #1f2937;
    }

    .commute-tabs {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        border-top: 1px solid var(--border, #e5e7eb);
        padding-top: 10px;
    }

    .commute-tab-btn {
        padding: 8px 16px;
        border-radius: 6px;
        border: 1px solid var(--border, #d1d5db);
        background: #f9fafb;
        color: #374151;
        font-size: 0.9rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .commute-tab-btn:hover {
        background: #f3f4f6;
        border-color: #9ca3af;
    }

    .commute-tab-btn.active {
        background: var(--primary, #3b82f6);
        color: white;
        border-color: var(--primary, #3b82f6);
        font-weight: 600;
    }

    .destination-config-card {
        margin-bottom: 20px;
    }

    .destination-form {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 10px;
    }

    .field-row {
        display: flex;
        gap: 15px;
    }

    .flex-1 {
        flex: 1;
    }

    .field {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .field label {
        font-weight: 600;
        font-size: 0.9rem;
        color: #374151;
    }

    .field input {
        padding: 8px 12px;
        border: 1px solid var(--border, #d1d5db);
        border-radius: 6px;
        font-size: 0.95rem;
    }

    .update-btn {
        background-color: var(--primary, #3b82f6);
        color: white;
        border: none;
        padding: 10px 16px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        align-self: flex-start;
        margin-top: 6px;
    }

    .update-btn:hover {
        opacity: 0.9;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
    }

    .commute-panel {
        display: flex;
        flex-direction: column;
        gap: 15px;
        background: rgba(0,0,0,0.02);
        padding: 15px;
        border-radius: 8px;
    }

    .commute-panel h2 {
        margin: 0;
        font-size: 1.4rem;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .time-badge {
        font-size: 0.9rem;
        background: var(--primary);
        color: white;
        padding: 3px 8px;
        border-radius: 12px;
    }

    .assessment-card {
        text-align: center;
        padding: 30px 20px;
        margin: 0;
    }

    .weather-card {
        margin: 0;
    }

    .status-icon {
        font-size: 4rem;
        margin-bottom: 10px;
    }

    .assessment-card h2 {
        font-size: 2rem;
        margin: 10px 0;
        justify-content: center;
    }

    .status-go { color: var(--status-go); }
    .status-caution { color: var(--status-caution); }
    .status-nogo { color: var(--status-nogo); }

    .recommendation {
        font-size: 1.1rem;
        font-style: italic;
        color: #666;
    }

    .metrics {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .metric {
        display: flex;
        justify-content: space-between;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }

    .metric:last-child {
        border-bottom: none;
    }

    .score {
        font-weight: bold;
        margin-top: 10px;
        color: var(--primary);
    }

    .weather-visualizations {
        margin-top: 30px;
    }

    .weather-visualizations h2 {
        font-size: 1.5rem;
        margin-bottom: 15px;
    }
</style>
