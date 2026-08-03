<script lang="ts">
    import { onMount } from 'svelte';
    import type { PageData } from './$types';
    import { getWeatherForecast, type ForecastResponse } from '$lib/api';
    import RiskGaugeCards from '$lib/charts/RiskGaugeCards.svelte';
    import HourlyWeatherChart from '$lib/charts/HourlyWeatherChart.svelte';
    import OfflineBanner from '$lib/components/OfflineBanner.svelte';
    import PwaInstallPrompt from '$lib/components/PwaInstallPrompt.svelte';
    import PushNotificationToggle from '$lib/components/PushNotificationToggle.svelte';

    let { data }: { data: PageData } = $props();

    let forecast = $state<ForecastResponse | null>(null);

    onMount(async () => {
        try {
            forecast = await getWeatherForecast();
        } catch (e) {
            console.error('Error fetching weather forecast:', e);
        }
    });

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

    {#if data.error}
        <div class="card" style="border-color: var(--status-nogo)">
            <p>{data.error}</p>
        </div>
    {:else if data.assessments && data.assessments.length > 0}
        <div class="dashboard-grid">
            {#each data.assessments as item}
                <div class="commute-panel">
                    <h2>{item.name} <span class="time-badge">{item.schedule_time}</span></h2>
                    
                    {#if item.error}
                        <div class="card" style="border-color: var(--status-nogo)">
                            <p>Error: {item.error}</p>
                        </div>
                    {:else if item.assessment}
                        <div class="card assessment-card">
                            <div class="status-icon">
                                {statusIcons[item.assessment.status] || '❓'}
                            </div>
                            <h2 class={statusClasses[item.assessment.status]}>
                                {item.assessment.status}
                            </h2>
                            <p class="recommendation">{item.assessment.recommendation}</p>
                        </div>

                        <div class="card weather-card">
                            <h3>Weather Details</h3>
                            <div class="metrics">
                                <div class="metric">
                                    <span>Temperature</span>
                                    <span>{item.assessment.details.temperature.toFixed(1)}{item.unit_system === 'metric' ? '°C' : '°F'}</span>
                                </div>
                                <div class="metric">
                                    <span>Wind Speed</span>
                                    <span>{item.assessment.details.wind_speed.toFixed(1)} {item.unit_system === 'metric' ? 'km/h' : 'mph'}</span>
                                </div>
                                <div class="metric">
                                    <span>Rain Probability</span>
                                    <span>{item.assessment.details.precip_prob}%</span>
                                </div>
                                <div class="metric score">
                                    <span>Safety Score</span>
                                    <span>{item.assessment.score}/100</span>
                                </div>
                            </div>
                        </div>
                    {/if}
                </div>
            {/each}
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
                thresholds={forecast.thresholds}
            />
        </section>
    {/if}
</div>

<style>
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
