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

describe('Settings Page (+page.svelte) - Schedule Selector Integration', () => {
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
    days_of_week: 'mon,wed,thu',
    lat: 37.7749,
    lon: -122.4194,
    dest_name: 'Office',
    dest_lat: 37.3861,
    dest_lon: -122.0839,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getCommuteConfig as any).mockResolvedValue([mockCommute]);
    (api.saveCommuteConfig as any).mockResolvedValue(mockCommute);
  });

  it('loads existing commute days_of_week and reflects active days in selector', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Check that Monday, Wednesday, Thursday are active
    const monBtn = await screen.findByRole('button', { name: 'Monday' });
    const tueBtn = await screen.findByRole('button', { name: 'Tuesday' });
    const wedBtn = await screen.findByRole('button', { name: 'Wednesday' });
    const thuBtn = await screen.findByRole('button', { name: 'Thursday' });
    const friBtn = await screen.findByRole('button', { name: 'Friday' });

    expect(monBtn).toHaveAttribute('aria-pressed', 'true');
    expect(tueBtn).toHaveAttribute('aria-pressed', 'false');
    expect(wedBtn).toHaveAttribute('aria-pressed', 'true');
    expect(thuBtn).toHaveAttribute('aria-pressed', 'true');
    expect(friBtn).toHaveAttribute('aria-pressed', 'false');
  });

  it('serializes toggled days back to backend cron format upon saving settings', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Toggle Friday on
    const friBtn = await screen.findByRole('button', { name: 'Friday' });
    await fireEvent.click(friBtn);
    expect(friBtn).toHaveAttribute('aria-pressed', 'true');

    // Click Save Commute button
    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.saveCommuteConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          days_of_week: 'mon,wed,thu,fri',
        })
      );
    });
  });

  it('updates days via preset and serializes on save', async () => {
    render(SettingsPage);

    await waitFor(() => {
      expect(api.getCommuteConfig).toHaveBeenCalledTimes(1);
    });

    // Click Weekdays preset
    const weekdaysPreset = await screen.findByRole('button', { name: 'Weekdays' });
    await fireEvent.click(weekdaysPreset);

    // Save
    const saveBtn = screen.getByRole('button', { name: 'Save Commute' });
    await fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.saveCommuteConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          days_of_week: 'mon,tue,wed,thu,fri',
        })
      );
    });
  });
});
