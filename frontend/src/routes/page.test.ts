import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '$lib/api';

vi.mock('svelte-chartjs', () => ({
  Line: vi.fn()
}));

vi.mock('$lib/api', () => ({
  getWeatherForecast: vi.fn(),
}));

describe('Dashboard Page (+page.svelte)', () => {
  const mockPageData = {
    assessments: [
      {
        name: 'Work Commute',
        schedule_time: '08:00',
        unit_system: 'imperial',
        assessment: {
          status: 'Go',
          score: 95,
          recommendation: 'Great conditions for riding!',
          details: {
            temperature: 68.0,
            apparent_temp: 68.0,
            wind_speed: 8.0,
            wind_gusts: 10.0,
            precip_prob: 5,
            weather_code: 0
          }
        }
      }
    ]
  };

  const mockForecast = {
    unit_system: 'imperial',
    thresholds: {
      min_temp_caution: 45,
      min_temp_no_go: 38,
      max_wind_caution: 15,
      max_wind_no_go: 25,
      rain_threshold: 30
    },
    hourly: [
      {
        time: '2026-08-02T08:00',
        temperature: 68.0,
        apparent_temp: 68.0,
        wind_speed: 8.0,
        precip_prob: 5,
        weather_code: 0
      },
      {
        time: '2026-08-02T09:00',
        temperature: 70.0,
        apparent_temp: 70.0,
        wind_speed: 10.0,
        precip_prob: 10,
        weather_code: 0
      }
    ]
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders primary commute assessment card', () => {
    (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
    render(Page, { data: mockPageData });

    expect(screen.getByText('Work Commute')).toBeInTheDocument();
    expect(screen.getByText('Go')).toBeInTheDocument();
    expect(screen.getByText('Great conditions for riding!')).toBeInTheDocument();
  });

  it('fetches forecast on mount and displays Weather Visualizations section, risk gauges, and chart', async () => {
    (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
    render(Page, { data: mockPageData });

    expect(api.getWeatherForecast).toHaveBeenCalledTimes(1);

    expect(await screen.findByRole('heading', { name: /Weather Visualizations/i })).toBeInTheDocument();
    expect(await screen.findByTestId('risk-gauge-cards')).toBeInTheDocument();
    expect(await screen.findByTestId('hourly-weather-chart')).toBeInTheDocument();
  });

  it('does not render Weather Visualizations section when forecast fails or is null', async () => {
    (api.getWeatherForecast as any).mockRejectedValue(new Error('API error'));
    render(Page, { data: mockPageData });

    expect(api.getWeatherForecast).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('heading', { name: /Weather Visualizations/i })).not.toBeInTheDocument();
  });
});
