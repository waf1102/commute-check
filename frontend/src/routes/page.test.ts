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
  it('renders destination inputs and return schedule picker', () => {
    (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
    render(Page, { data: mockPageData });

    expect(screen.getByLabelText(/Destination Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Destination Latitude/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Destination Longitude/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Return Schedule Time/i)).toBeInTheDocument();
  });

  it('renders LegRiskCard when outbound_leg and return_leg are present', () => {
    (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
    const mockMultiRouteData = {
      assessments: [
        {
          name: 'Multi Route Commute',
          schedule_time: '08:00',
          return_schedule_time: '17:00',
          unit_system: 'imperial',
          assessment: {
            overall_status: 'Caution',
            overall_score: 60,
            recommendation: 'Caution advised on return leg',
            outbound_leg: {
              leg_type: 'outbound',
              location_name: 'Home -> Office',
              schedule_time: '08:00',
              status: 'Go',
              score: 95,
              reasons: ['Mild conditions']
            },
            return_leg: {
              leg_type: 'return',
              location_name: 'Office -> Home',
              schedule_time: '17:00',
              status: 'Caution',
              score: 60,
              reasons: ['High wind speed']
            }
          }
        }
      ]
    };

    render(Page, { data: mockMultiRouteData });

    expect(screen.getByTestId('leg-risk-card')).toBeInTheDocument();
    expect(screen.getByText('Home -> Office')).toBeInTheDocument();
    expect(screen.getByText('Office -> Home')).toBeInTheDocument();
  });  it('renders LegRiskCard when only outbound_leg is present (single-leg assessment)', () => {
    (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
    const mockSingleLegData = {
      assessments: [
        {
          name: 'Single Leg Commute',
          schedule_time: '08:00',
          unit_system: 'imperial',
          assessment: {
            overall_status: 'Go',
            overall_score: 90,
            recommendation: 'Good conditions',
            outbound_leg: {
              leg_type: 'outbound',
              location_name: 'Home -> Office',
              schedule_time: '08:00',
              status: 'Go',
              score: 90,
              reasons: ['Clear skies']
            }
          }
        }
      ]
    };

    render(Page, { data: mockSingleLegData });

    expect(screen.getByTestId('leg-risk-card')).toBeInTheDocument();
    expect(screen.getByText('Home -> Office')).toBeInTheDocument();
  });
});
