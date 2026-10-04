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

describe('Settings Page (+page.svelte) - Waypoint Editor Integration', () => {
  const mockCommuteWithWaypoints = {
    id: 1,
    name: 'Work Commute with Stops',
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
      { id: 'wp-1', name: 'Coffee Shop', lat: 37.7800, lon: -122.4100 },
      { id: 'wp-2', name: 'Bike Repair Shop', lat: 37.7850, lon: -122.4050 },
    ]
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getCommuteConfig as any).mockResolvedValue([mockCommuteWithWaypoints]);
    (api.saveCommuteConfig as any).mockResolvedValue(mockCommuteWithWaypoints);
  });

  it('loads and displays intermediate waypoints from existing commute', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Check intermediate waypoints rendered
    expect(await screen.findByDisplayValue('Coffee Shop')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Bike Repair Shop')).toBeInTheDocument();
    expect(screen.getByTestId('waypoint-item-0')).toBeInTheDocument();
    expect(screen.getByTestId('waypoint-item-1')).toBeInTheDocument();
  });

  it('allows adding a new intermediate waypoint', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    const addBtn = screen.getByTestId('add-waypoint-btn');
    await fireEvent.click(addBtn);

    // Should now have 3 waypoint items
    expect(await screen.findByTestId('waypoint-item-2')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Waypoint 3')).toBeInTheDocument();
  });

  it('allows reordering waypoints (move down / move up)', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Move first waypoint down
    const moveDownBtn0 = screen.getByTestId('move-down-btn-0');
    expect(moveDownBtn0).not.toBeDisabled();

    // The first item before move is 'Coffee Shop'
    const nameInput0Before = screen.getByTestId('wp-name-input-0') as HTMLInputElement;
    expect(nameInput0Before.value).toBe('Coffee Shop');

    await fireEvent.click(moveDownBtn0);

    // After move down, item 0 should be 'Bike Repair Shop' and item 1 should be 'Coffee Shop'
    await waitFor(() => {
      const nameInput0After = screen.getByTestId('wp-name-input-0') as HTMLInputElement;
      const nameInput1After = screen.getByTestId('wp-name-input-1') as HTMLInputElement;
      expect(nameInput0After.value).toBe('Bike Repair Shop');
      expect(nameInput1After.value).toBe('Coffee Shop');
    });

    // Now move item 1 up
    const moveUpBtn1 = screen.getByTestId('move-up-btn-1');
    expect(moveUpBtn1).not.toBeDisabled();
    await fireEvent.click(moveUpBtn1);

    await waitFor(() => {
      const nameInput0Restored = screen.getByTestId('wp-name-input-0') as HTMLInputElement;
      expect(nameInput0Restored.value).toBe('Coffee Shop');
    });
  });

  it('allows removing an intermediate waypoint', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByTestId('waypoint-item-1')).toBeInTheDocument();

    const removeBtn0 = screen.getByTestId('remove-btn-0');
    await fireEvent.click(removeBtn0);

    await waitFor(() => {
      // Should now only have 1 waypoint
      expect(screen.queryByTestId('waypoint-item-1')).not.toBeInTheDocument();
      const remainingName = screen.getByTestId('wp-name-input-0') as HTMLInputElement;
      expect(remainingName.value).toBe('Bike Repair Shop');
    });
  });

  it('validates waypoint coordinates and prevents saving when latitude is out of bounds', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Set invalid latitude (> 90)
    const latInput0 = screen.getByTestId('wp-lat-input-0');
    await fireEvent.input(latInput0, { target: { value: '95.5' } });

    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    // saveCommuteConfig should NOT be called due to validation error
    expect(api.saveCommuteConfig).not.toHaveBeenCalled();
    expect(screen.getAllByText(/latitude must be between -90 and 90/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('wp-lat-error-0')).toHaveTextContent('Latitude must be between -90 and 90');
  });

  it('validates waypoint coordinates and prevents saving when longitude is out of bounds', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Set invalid longitude (> 180)
    const lonInput0 = screen.getByTestId('wp-lon-input-0');
    await fireEvent.input(lonInput0, { target: { value: '200' } });

    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    // saveCommuteConfig should NOT be called due to validation error
    expect(api.saveCommuteConfig).not.toHaveBeenCalled();
    expect(screen.getAllByText(/longitude must be between -180 and 180/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('wp-lon-error-0')).toHaveTextContent('Longitude must be between -180 and 180');
  });

  it('saves commute settings including valid waypoints to the backend', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.saveCommuteConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Work Commute with Stops',
          waypoints: expect.arrayContaining([
            expect.objectContaining({ name: 'Coffee Shop', lat: 37.7800, lon: -122.4100 }),
            expect.objectContaining({ name: 'Bike Repair Shop', lat: 37.7850, lon: -122.4050 }),
          ])
        })
      );
    });
  });
});
