<script lang="ts">
    import type { PageData } from './$types';

    let { data }: { data: PageData } = $props();

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
    <h1>Commute Check Dashboard</h1>

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
</style>
