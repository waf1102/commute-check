<script lang="ts">
    import type { PageData } from './$types';

    let { data }: { data: PageData } = $props();

    const statusIcons = {
        'Go': '🟢',
        'Caution': '🟡',
        'No-Go': '🔴'
    };

    const statusClasses = {
        'Go': 'status-go',
        'Caution': 'status-caution',
        'No-Go': 'status-nogo'
    };
</script>

<div class="container">
    <h1>Commute Check</h1>

    {#if data.error}
        <div class="card" style="border-color: var(--status-nogo)">
            <p>{data.error}</p>
        </div>
    {:else if data.assessment}
        <div class="card assessment-card">
            <div class="status-icon">
                {statusIcons[data.assessment.status] || '❓'}
            </div>
            <h2 class={statusClasses[data.assessment.status]}>
                {data.assessment.status}
            </h2>
            <p class="recommendation">{data.assessment.recommendation}</p>
        </div>

        <div class="card">
            <h3>Weather Details</h3>
            <div class="metrics">
                <div class="metric">
                    <span>Temperature</span>
                    <span>{data.assessment.details.temperature.toFixed(1)}°C</span>
                </div>
                <div class="metric">
                    <span>Wind Speed</span>
                    <span>{data.assessment.details.wind_speed.toFixed(1)} km/h</span>
                </div>
                <div class="metric">
                    <span>Rain Probability</span>
                    <span>{data.assessment.details.precip_prob}%</span>
                </div>
                <div class="metric score">
                    <span>Safety Score</span>
                    <span>{data.assessment.score}/100</span>
                </div>
            </div>
        </div>
    {/if}
</div>

<style>
    .assessment-card {
        text-align: center;
        padding: 40px 20px;
    }

    .status-icon {
        font-size: 5rem;
        margin-bottom: 10px;
    }

    h2 {
        font-size: 2.5rem;
        margin: 10px 0;
    }

    .status-go { color: var(--status-go); }
    .status-caution { color: var(--status-caution); }
    .status-nogo { color: var(--status-nogo); }

    .recommendation {
        font-size: 1.2rem;
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
