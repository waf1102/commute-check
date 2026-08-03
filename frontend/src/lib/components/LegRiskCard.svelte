<script lang="ts">
  import type { LegAssessment } from '$lib/api';

  const props = $props<{
    outboundLeg?: LegAssessment;
    returnLeg?: LegAssessment;
    outbound_leg?: LegAssessment;
    return_leg?: LegAssessment;
  }>();

  const outbound = $derived(props.outboundLeg || props.outbound_leg);
  const returnL = $derived(props.returnLeg || props.return_leg);

  function getStatusBadgeClass(status?: string): string {
    if (status === 'Go') return 'badge-go';
    if (status === 'Caution') return 'badge-caution';
    if (status === 'No-Go') return 'badge-nogo';
    return 'badge-default';
  }
</script>

<div class="leg-risk-container" data-testid="leg-risk-card">
  {#if outbound}
    <div class="leg-card outbound-card">
      <div class="leg-header">
        <span class="leg-title">Outbound (Morning)</span>
        <span class="status-pill {getStatusBadgeClass(outbound.status)}">{outbound.status}</span>
      </div>
      <div class="leg-details">
        <div class="location-name">{outbound.location_name}</div>
        <div class="departure-time">Departure: {outbound.schedule_time}</div>
        <div class="score-display">
          <span class="score-label">Safety Score:</span>
          <span class="score-value">{outbound.score}</span>
        </div>
      </div>
      {#if outbound.reasons && outbound.reasons.length > 0}
        <div class="reasons-list">
          <h4>Weather Considerations</h4>
          <ul>
            {#each outbound.reasons as reason}
              <li class="reason-badge">{reason}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {/if}

  {#if returnL}
    <div class="leg-card return-card">
      <div class="leg-header">
        <span class="leg-title">Return (Evening)</span>
        <span class="status-pill {getStatusBadgeClass(returnL.status)}">{returnL.status}</span>
      </div>
      <div class="leg-details">
        <div class="location-name">{returnL.location_name}</div>
        <div class="departure-time">Departure: {returnL.schedule_time}</div>
        <div class="score-display">
          <span class="score-label">Safety Score:</span>
          <span class="score-value">{returnL.score}</span>
        </div>
      </div>
      {#if returnL.reasons && returnL.reasons.length > 0}
        <div class="reasons-list">
          <h4>Weather Considerations</h4>
          <ul>
            {#each returnL.reasons as reason}
              <li class="reason-badge">{reason}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .leg-risk-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin: 16px 0;
  }

  .leg-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }

  .leg-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #f3f4f6;
  }

  .leg-title {
    font-weight: 600;
    font-size: 1.1rem;
    color: #111827;
  }

  .status-pill {
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .badge-go {
    background-color: #d1fae5;
    color: #065f46;
    border: 1px solid #a7f3d0;
  }

  .badge-caution {
    background-color: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
  }

  .badge-nogo {
    background-color: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
  }

  .badge-default {
    background-color: #f3f4f6;
    color: #374151;
  }

  .leg-details {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }

  .location-name {
    font-weight: 500;
    color: #374151;
    font-size: 1rem;
  }

  .departure-time {
    font-size: 0.9rem;
    color: #6b7280;
  }

  .score-display {
    display: flex;
    gap: 8px;
    align-items: center;
    font-weight: 600;
  }

  .score-label {
    color: #4b5563;
  }

  .score-value {
    color: #2563eb;
    font-size: 1.1rem;
  }

  .reasons-list {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px dashed #e5e7eb;
  }

  .reasons-list h4 {
    font-size: 0.85rem;
    color: #6b7280;
    margin: 0 0 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .reasons-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .reason-badge {
    background-color: #f3f4f6;
    color: #374151;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.825rem;
  }
</style>
