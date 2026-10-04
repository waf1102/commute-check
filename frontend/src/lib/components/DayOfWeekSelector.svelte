<script lang="ts">
  import {
    DAYS_OF_WEEK,
    WEEKDAYS,
    ALL_DAYS,
    parseDaysOfWeek,
    serializeDaysOfWeek,
    formatDaysSummary
  } from '$lib/schedule';

  let {
    value = $bindable('mon-fri'),
    disabled = false,
    id = 'day-of-week-selector',
    onChange
  }: {
    value?: string;
    disabled?: boolean;
    id?: string;
    onChange?: (serialized: string, days: string[]) => void;
  } = $props();

  let activeDays = $state<string[]>(parseDaysOfWeek(value));
  let lastExternalValue = $state<string | undefined>(undefined);

  // Synchronize when the external value prop updates (e.g. selecting different commutes)
  $effect(() => {
    const current = value;
    if (current !== lastExternalValue) {
      lastExternalValue = current;
      activeDays = parseDaysOfWeek(current);
    }
  });

  function updateDays(newDays: string[]) {
    if (disabled) return;
    activeDays = newDays;
    const serialized = serializeDaysOfWeek(newDays);
    lastExternalValue = serialized;
    value = serialized;
    onChange?.(serialized, newDays);
  }

  function toggleDay(dayKey: string) {
    if (disabled) return;
    let nextDays: string[];
    if (activeDays.includes(dayKey)) {
      nextDays = activeDays.filter((d) => d !== dayKey);
    } else {
      nextDays = [...activeDays, dayKey];
    }
    updateDays(nextDays);
  }

  function applyPreset(preset: 'weekdays' | 'all' | 'clear') {
    if (disabled) return;
    if (preset === 'weekdays') {
      updateDays([...WEEKDAYS]);
    } else if (preset === 'all') {
      updateDays([...ALL_DAYS]);
    } else if (preset === 'clear') {
      updateDays([]);
    }
  }
</script>

<div class="day-selector-container" role="group" aria-label="Day of week schedule selector" {id}>
  <div class="day-buttons-grid" role="group" aria-label="Days of the week">
    {#each DAYS_OF_WEEK as day (day.key)}
      {@const isActive = activeDays.includes(day.key)}
      <button
        type="button"
        class="day-toggle"
        class:active={isActive}
        aria-pressed={isActive}
        aria-label={day.fullName}
        data-day={day.key}
        {disabled}
        onclick={() => toggleDay(day.key)}
      >
        <span class="day-label">{day.label}</span>
      </button>
    {/each}
  </div>

  <div class="presets-row" role="group" aria-label="Schedule presets">
    <span class="presets-title">Presets:</span>
    <button type="button" class="preset-btn" {disabled} onclick={() => applyPreset('weekdays')}>
      Weekdays
    </button>
    <button type="button" class="preset-btn" {disabled} onclick={() => applyPreset('all')}>
      All Days
    </button>
    <button
      type="button"
      class="preset-btn preset-clear"
      {disabled}
      onclick={() => applyPreset('clear')}
    >
      Clear
    </button>
  </div>

  <div class="summary-row">
    <span class="summary-label">Schedule:</span>
    <span class="summary-text" aria-live="polite">{formatDaysSummary(activeDays)}</span>
  </div>
</div>

<style>
  .day-selector-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 4px;
    margin-bottom: 8px;
  }

  .day-buttons-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
  }

  @media (max-width: 480px) {
    .day-buttons-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  .day-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px 4px;
    background-color: var(--card-bg, #ffffff);
    color: var(--text, #212529);
    border: 1px solid var(--border, #dee2e6);
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.15s ease-in-out;
    user-select: none;
    outline: none;
  }

  .day-toggle:hover:not(:disabled) {
    border-color: var(--primary, #007bff);
    background-color: #f1f5f9;
  }

  .day-toggle:focus-visible {
    outline: 2px solid var(--primary, #007bff);
    outline-offset: 2px;
  }

  .day-toggle.active {
    background-color: var(--primary, #007bff);
    color: #ffffff;
    border-color: var(--primary, #007bff);
    font-weight: 600;
    box-shadow: 0 2px 4px rgba(0, 123, 255, 0.25);
  }

  .day-toggle.active:hover:not(:disabled) {
    background-color: #0069d9;
    border-color: #0062cc;
  }

  .day-toggle:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .presets-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .presets-title {
    font-size: 0.85rem;
    color: #6c757d;
    font-weight: 500;
  }

  .preset-btn {
    padding: 4px 10px;
    font-size: 0.8rem;
    background-color: var(--card-bg, #ffffff);
    color: var(--text, #212529);
    border: 1px solid var(--border, #dee2e6);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease-in-out;
  }

  .preset-btn:hover:not(:disabled) {
    background-color: #e9ecef;
    border-color: #adb5bd;
  }

  .preset-btn:focus-visible {
    outline: 2px solid var(--primary, #007bff);
    outline-offset: 1px;
  }

  .preset-clear {
    color: #dc3545;
  }

  .preset-clear:hover:not(:disabled) {
    background-color: #f8d7da;
    border-color: #f5c6cb;
  }

  .preset-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .summary-row {
    font-size: 0.85rem;
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .summary-label {
    color: #6c757d;
    font-weight: 500;
  }

  .summary-text {
    font-weight: 600;
    color: var(--text, #212529);
  }
</style>
