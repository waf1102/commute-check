import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AddressSearch from '../AddressSearch.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('AddressSearch Component (AddressSearch.svelte)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockNominatimResponse = [
    {
      place_id: 101,
      name: '10 Downing Street',
      display_name: '10 Downing Street, City of Westminster, London, SW1A 2AA, UK',
      lat: '51.503396',
      lon: '-0.127625'
    },
    {
      place_id: 102,
      name: 'Downing College',
      display_name: 'Downing College, Regent Street, Cambridge, CB2 1DQ, UK',
      lat: '52.2008',
      lon: '0.1242'
    }
  ];

  it('renders input field, placeholder, and search button', () => {
    render(AddressSearch, {
      props: {
        placeholder: 'Search for address...',
        testId: 'test-search',
        onselect: vi.fn()
      }
    });

    const input = screen.getByTestId('test-search-input');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('placeholder', 'Search for address...');

    const btn = screen.getByTestId('test-search-btn');
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled(); // Disabled when input is empty
  });

  it('queries Nominatim and displays geocoded suggestions on search', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockNominatimResponse
    } as Response);

    const onselect = vi.fn();

    render(AddressSearch, {
      props: {
        testId: 'test-search',
        onselect
      }
    });

    const input = screen.getByTestId('test-search-input');
    await fireEvent.input(input, { target: { value: 'Downing' } });

    const btn = screen.getByTestId('test-search-btn');
    expect(btn).not.toBeDisabled();
    await fireEvent.click(btn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('nominatim.openstreetmap.org/search?format=json&q=Downing'),
        expect.any(Object)
      );
    });

    // Check dropdown suggestions rendered
    const list = await screen.findByTestId('test-search-results');
    expect(list).toBeInTheDocument();

    const result0 = screen.getByTestId('test-search-result-0');
    expect(result0).toHaveTextContent('10 Downing Street');
    expect(result0).toHaveTextContent('Lat: 51.5034, Lon: -0.1276');

    // Click first suggestion
    await fireEvent.click(result0);

    expect(onselect).toHaveBeenCalledWith({
      name: '10 Downing Street',
      lat: 51.5034,
      lon: -0.1276,
      display_name: '10 Downing Street, City of Westminster, London, SW1A 2AA, UK'
    });

    // Dropdown should close after selection
    expect(screen.queryByTestId('test-search-results')).not.toBeInTheDocument();
  });

  it('shows error feedback when no results found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => []
    } as Response);

    render(AddressSearch, {
      props: {
        testId: 'test-search',
        onselect: vi.fn()
      }
    });

    const input = screen.getByTestId('test-search-input');
    await fireEvent.input(input, { target: { value: 'NonexistentAddress123XYZ' } });

    const btn = screen.getByTestId('test-search-btn');
    await fireEvent.click(btn);

    const feedback = await screen.findByTestId('test-search-feedback');
    expect(feedback).toHaveTextContent('No locations found for this query.');
  });

  it('handles network failure gracefully', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'));

    render(AddressSearch, {
      props: {
        testId: 'test-search',
        onselect: vi.fn()
      }
    });

    const input = screen.getByTestId('test-search-input');
    await fireEvent.input(input, { target: { value: 'London' } });

    const btn = screen.getByTestId('test-search-btn');
    await fireEvent.click(btn);

    const feedback = await screen.findByTestId('test-search-feedback');
    expect(feedback).toHaveTextContent('Failed to fetch location suggestions');
  });

  it('clears query and results when clear button is clicked', async () => {
    render(AddressSearch, {
      props: {
        testId: 'test-search',
        onselect: vi.fn()
      }
    });

    const input = screen.getByTestId('test-search-input') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'Test' } });
    expect(input.value).toBe('Test');

    const clearBtn = screen.getByTestId('test-search-clear-btn');
    await fireEvent.click(clearBtn);

    expect(input.value).toBe('');
  });
});
