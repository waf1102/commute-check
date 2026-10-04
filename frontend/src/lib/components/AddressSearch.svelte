<script lang="ts">
  import { searchAddress, type GeocodeResult } from '$lib/geocoding';

  let {
    placeholder = 'Search address or place (e.g., 10 Downing St, London)...',
    label = '',
    disabled = false,
    testId = 'address-search',
    showUseCurrentLocation = false,
    onselect,
    onuseCurrentLocation
  }: {
    placeholder?: string;
    label?: string;
    disabled?: boolean;
    testId?: string;
    showUseCurrentLocation?: boolean;
    onselect: (result: { name: string; lat: number; lon: number; display_name: string }) => void;
    onuseCurrentLocation?: () => void;
  } = $props();

  let query = $state('');
  let results = $state<GeocodeResult[]>([]);
  let loading = $state(false);
  let errorMsg = $state('');
  let isOpen = $state(false);
  let hasSearched = $state(false);

  async function handleSearch(e?: Event) {
    if (e) e.preventDefault();
    if (!query.trim() || disabled || loading) return;

    loading = true;
    errorMsg = '';
    hasSearched = true;

    try {
      const data = await searchAddress(query);
      results = data;
      isOpen = true;
      if (data.length === 0) {
        errorMsg = 'No locations found for this query.';
      }
    } catch (err: any) {
      console.error('Nominatim search error:', err);
      errorMsg = 'Failed to fetch location suggestions. Please try again.';
      results = [];
    } finally {
      loading = false;
    }
  }

  function handleSelect(item: GeocodeResult) {
    onselect({
      name: item.name,
      lat: item.lat,
      lon: item.lon,
      display_name: item.display_name
    });
    query = item.name;
    isOpen = false;
    results = [];
    errorMsg = '';
  }

  function handleClear() {
    query = '';
    results = [];
    isOpen = false;
    errorMsg = '';
    hasSearched = false;
  }
</script>

<div class="address-search-wrapper" data-testid={testId}>
  {#if label}
    <label for="{testId}-input" class="search-label">{label}</label>
  {/if}

  <form onsubmit={handleSearch} class="search-input-group" role="search">
    <div class="input-with-clear">
      <input
        type="text"
        id="{testId}-input"
        class="search-input"
        bind:value={query}
        placeholder={placeholder}
        disabled={disabled}
        autocomplete="off"
        data-testid="{testId}-input"
      />
      {#if query}
        <button
          type="button"
          class="clear-btn"
          onclick={handleClear}
          title="Clear search"
          aria-label="Clear search"
          data-testid="{testId}-clear-btn"
        >
          ✕
        </button>
      {/if}
    </div>

    <button
      type="submit"
      class="search-btn"
      disabled={disabled || loading || !query.trim()}
      data-testid="{testId}-btn"
    >
      {#if loading}
        <span class="spinner" data-testid="{testId}-loading">⏳</span>
      {:else}
        🔍 Search
      {/if}
    </button>

    {#if showUseCurrentLocation && onuseCurrentLocation}
      <button
        type="button"
        class="current-loc-btn secondary"
        disabled={disabled}
        onclick={onuseCurrentLocation}
        data-testid="{testId}-current-loc-btn"
        title="Use device GPS location"
      >
        📍 Current Location
      </button>
    {/if}
  </form>

  {#if isOpen && results.length > 0}
    <ul class="suggestions-list" data-testid="{testId}-results" role="listbox">
      {#each results as item, idx}
        <li role="option" aria-selected="false">
          <button
            type="button"
            class="suggestion-item"
            onclick={() => handleSelect(item)}
            data-testid="{testId}-result-{idx}"
          >
            <div class="result-title">
              <span class="pin-icon">📍</span>
              <strong>{item.name}</strong>
            </div>
            <div class="result-details">{item.display_name}</div>
            <div class="result-coords">Lat: {item.lat}, Lon: {item.lon}</div>
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  {#if errorMsg}
    <div class="search-feedback" data-testid="{testId}-feedback">
      {errorMsg}
    </div>
  {/if}
</div>

<style>
  .address-search-wrapper {
    position: relative;
    width: 100%;
    margin-bottom: 8px;
  }

  .search-label {
    display: block;
    margin-bottom: 4px;
    font-weight: 600;
    font-size: 13px;
    color: var(--text);
  }

  .search-input-group {
    display: flex;
    gap: 8px;
    align-items: center;
    width: 100%;
  }

  .input-with-clear {
    position: relative;
    flex: 1;
    display: flex;
    align-items: center;
  }

  .search-input {
    width: 100%;
    padding: 8px 30px 8px 12px;
    border: 1px solid var(--border, #ccc);
    border-radius: 6px;
    font-size: 14px;
    background: var(--bg-surface, #fff);
    color: var(--text, #333);
    box-sizing: border-box;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--primary, #3b82f6);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
  }

  .clear-btn {
    position: absolute;
    right: 8px;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 12px;
    color: #94a3b8;
    padding: 2px 4px;
    border-radius: 4px;
  }

  .clear-btn:hover {
    color: #475569;
  }

  .search-btn, .current-loc-btn {
    white-space: nowrap;
    padding: 8px 14px;
    font-size: 13px;
    border-radius: 6px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .search-btn {
    background: var(--primary, #3b82f6);
    color: white;
    border: 1px solid var(--primary, #3b82f6);
  }

  .search-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .current-loc-btn {
    background: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
  }

  .current-loc-btn:hover:not(:disabled) {
    background: #e2e8f0;
  }

  .suggestions-list {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    background: var(--bg-surface, #ffffff);
    border: 1px solid var(--border, #e2e8f0);
    border-radius: 8px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    list-style: none;
    padding: 4px;
    margin: 0;
    z-index: 1050;
    max-height: 240px;
    overflow-y: auto;
  }

  .suggestion-item {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    padding: 8px 10px;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: var(--text, #1e293b);
  }

  .suggestion-item:hover, .suggestion-item:focus {
    background: #f8fafc;
    outline: none;
  }

  .result-title {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
  }

  .pin-icon {
    font-size: 12px;
  }

  .result-details {
    font-size: 12px;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .result-coords {
    font-size: 11px;
    color: #94a3b8;
    font-family: monospace;
  }

  .search-feedback {
    margin-top: 4px;
    font-size: 12px;
    color: #e11d48;
  }

  .spinner {
    animation: spin 1s linear infinite;
    display: inline-block;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
