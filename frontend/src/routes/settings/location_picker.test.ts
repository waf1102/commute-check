import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import SettingsPage from './+page.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '$lib/api';

vi.mock('$lib/api', () => ({
  getCommuteConfig: vi.fn(),
  saveCommuteConfig: vi.fn(),
  deleteCommuteConfig: vi.fn(),
  testWebhook: vi.fn(),
}));

vi.mock('$lib/auth', () => ({
  jwt_token: {
    subscribe: vi.fn((fn) => {
      fn('mock-token');
      return () => {};
    }),
  },
}));

describe('Settings Page (+page.svelte) - Interactive Location Picker Integration', () => {
  const mockCommute = {
    id: 1,
    name: 'Work Commute',
    unit_system: 'imperial',
    min_temp_caution: 40,
    min_temp_no_go: 35,
    max_wind_caution: 20,
    max_wind_no_go: 35,
    rain_threshold: 50,
    webhook_url: '',
    schedule_time: '08:00',
    return_schedule_time: '17:00',
    days_of_week: 'mon-fri',
    lat: 37.7749,
    lon: -122.4194,
    dest_name: 'Downtown Office',
    dest_lat: 37.7891,
    dest_lon: -122.4014,
    waypoints: [
      { id: 'wp-1', name: 'Coffee Stop', lat: 37.7800, lon: -122.4100 },
      { id: 'wp-2', name: 'Midway Station', lat: 37.7850, lon: -122.4050 }
    ]
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getCommuteConfig as any).mockResolvedValue([mockCommute]);
    (api.saveCommuteConfig as any).mockResolvedValue(mockCommute);
  });

  it('renders interactive map picker section and address search components', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Check map section and location picker component
    expect(screen.getByTestId('interactive-map-section')).toBeInTheDocument();
    expect(screen.getByTestId('location-picker-component')).toBeInTheDocument();

    // Check address search inputs for Origin, Destination, and Waypoints
    expect(screen.getByTestId('origin-address-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('dest-address-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('wp-address-search-0-input')).toBeInTheDocument();
    expect(screen.getByTestId('wp-address-search-1-input')).toBeInTheDocument();

    // Coordinates summary
    expect(screen.getByTestId('origin-coords-chip')).toHaveTextContent('37.7749, -122.4194');
    expect(screen.getByTestId('destination-coords-chip')).toHaveTextContent('37.7891, -122.4014');
  });

  it('updates Origin coordinates and form input when map pin coordinate changes', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    // Ensure origin is active target and simulate dropping pin
    const originPill = screen.getByTestId('target-select-origin');
    await fireEvent.click(originPill);

    canvas.__handleMapCoordinateSelect(37.7711, -122.4222);

    // Verify origin inputs reflect new coordinates
    await waitFor(() => {
      const latInput = screen.getByLabelText('Origin Latitude') as HTMLInputElement;
      const lonInput = screen.getByLabelText('Origin Longitude') as HTMLInputElement;
      expect(latInput.value).toBe('37.7711');
      expect(lonInput.value).toBe('-122.4222');
    });

    // Verify summary chip reflects updated coordinates
    const originChip = screen.getByTestId('origin-coords-chip');
    expect(originChip).toHaveTextContent('37.7711, -122.4222');
  });

  it('updates Destination coordinates and form input when destination target is selected and pin dropped', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    const destPill = screen.getByTestId('target-select-destination');
    await fireEvent.click(destPill);

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    canvas.__handleMapCoordinateSelect(37.7950, -122.3950);

    await waitFor(() => {
      const destLatInput = screen.getByLabelText('Destination Latitude') as HTMLInputElement;
      const destLonInput = screen.getByLabelText('Destination Longitude') as HTMLInputElement;
      expect(destLatInput.value).toBe('37.795');
      expect(destLonInput.value).toBe('-122.395');
    });
  });

  it('updates Waypoint coordinates when waypoint target is selected and pin dropped', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    const wp0Pill = screen.getByTestId('target-select-waypoint-0');
    await fireEvent.click(wp0Pill);

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    canvas.__handleMapCoordinateSelect(37.7812, -122.4115);

    await waitFor(() => {
      const wp0LatInput = screen.getByTestId('wp-lat-input-0') as HTMLInputElement;
      const wp0LonInput = screen.getByTestId('wp-lon-input-0') as HTMLInputElement;
      expect(wp0LatInput.value).toBe('37.7812');
      expect(wp0LonInput.value).toBe('-122.4115');
    });
  });

  it('updates location via AddressSearch with Nominatim and persists on Save', async () => {
    const mockNominatimResponse = [
      {
        place_id: 301,
        name: 'Ferry Building',
        display_name: 'Ferry Building, The Embarcadero, San Francisco, CA',
        lat: '37.7955',
        lon: '-122.3937'
      }
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockNominatimResponse
    } as Response);

    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Search destination address using Nominatim address search
    const destSearchInput = screen.getByTestId('dest-address-search-input');
    await fireEvent.input(destSearchInput, { target: { value: 'Ferry Building' } });

    const destSearchBtn = screen.getByTestId('dest-address-search-btn');
    await fireEvent.click(destSearchBtn);

    const result0 = await screen.findByTestId('dest-address-search-result-0');
    await fireEvent.click(result0);

    // Check that Destination lat/lon updated
    await waitFor(() => {
      const destLatInput = screen.getByLabelText('Destination Latitude') as HTMLInputElement;
      const destLonInput = screen.getByLabelText('Destination Longitude') as HTMLInputElement;
      expect(destLatInput.value).toBe('37.7955');
      expect(destLonInput.value).toBe('-122.3937');
    });

    // Save commute
    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.saveCommuteConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          dest_lat: 37.7955,
          dest_lon: -122.3937
        })
      );
    });
  });
});
