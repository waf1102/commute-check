<script lang="ts">
  import type { LegAssessment } from '$lib/api';
  import { verdict, statusClass, departureLabel } from '$lib/commute';
  let {
    outboundLeg,
    returnLeg,
    unitSystem = 'imperial',
    timezone = 'UTC'
  }: {
    outboundLeg?: LegAssessment;
    returnLeg?: LegAssessment;
    unitSystem?: string;
    timezone?: string;
  } = $props();
</script>

<div class="legs" data-testid="leg-risk-card">
  {#each [outboundLeg, returnLeg].filter(Boolean) as leg}
    {#if leg}<section class="card leg">
        <p class="eyebrow">{leg.leg_type === 'return' ? 'Heading back' : 'Heading out'}</p>
        <h3>{departureLabel(leg.schedule_time, timezone)}</h3>
        <p class="status {statusClass(leg.status)}">{verdict(leg.status)}</p>
        <ul>
          {#each leg.reasons as reason}<li>
              {reason === 'Clear conditions' ? 'Within your weather limits' : reason}
            </li>{/each}
        </ul>
        {#if leg.weather}<dl>
            <div>
              <dt>Feels like</dt>
              <dd>{Math.round(leg.weather.apparent_temp)}°{unitSystem === 'metric' ? 'C' : 'F'}</dd>
            </div>
            <div>
              <dt>Wind{leg.weather.wind_gusts != null ? ' / gusts' : ''}</dt>
              <dd>
                {Math.round(leg.weather.wind_speed)}{leg.weather.wind_gusts != null
                  ? ` / ${Math.round(leg.weather.wind_gusts)}`
                  : ''}
                {unitSystem === 'metric' ? 'km/h' : 'mph'}
              </dd>
            </div>
            <div>
              <dt>Rain chance</dt>
              <dd>{Math.round(leg.weather.precip_prob)}%</dd>
            </div>
          </dl>
          <p class="muted sample-note">Weather at the most concerning checked location.</p>{/if}
        {#if leg.waypoint_evaluations && leg.waypoint_evaluations.length > 2}<details>
            <summary>Weather at your stops</summary>
            <ul>
              {#each leg.waypoint_evaluations as point}<li>
                  <strong>{point.name}</strong> · {departureLabel(
                    point.estimated_arrival_time,
                    timezone
                  )}<br />{verdict(point.status)}{point.status !== 'Go'
                    ? `: ${point.reasons.join('; ')}`
                    : ''}
                </li>{/each}
            </ul>
          </details>{/if}
      </section>{/if}
  {/each}
</div>

<style>
  .legs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr));
    gap: 1.25rem;
  }
  .leg {
    margin-bottom: 1rem;
  }
  h3 {
    font-size: 1.2rem;
    margin-bottom: 0.8rem;
  }
  .status {
    font-weight: 700;
  }
  .go {
    color: var(--status-go);
  }
  .caution {
    color: var(--status-caution);
  }
  .nogo {
    color: var(--status-nogo);
  }
  ul {
    padding-left: 1.2rem;
    min-height: 3rem;
  }
  li {
    margin-bottom: 0.35rem;
  }
  dl {
    border-top: 1px solid var(--border);
    padding-top: 1rem;
    margin-bottom: 0.8rem;
  }
  dl div {
    display: flex;
    justify-content: space-between;
    gap: 0.8rem;
    margin-bottom: 0.5rem;
  }
  dt {
    color: var(--muted);
  }
  dd {
    margin: 0;
    font-weight: 650;
    text-align: right;
  }
  .sample-note {
    font-size: 0.75rem;
    margin: 0;
  }
</style>
