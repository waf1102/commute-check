import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import HourlyWeatherChart from './HourlyWeatherChart.svelte';
import RiskGaugeCards from './RiskGaugeCards.svelte';
import type { HourlyForecastItem, Thresholds } from '$lib/api';

// Mock svelte-chartjs so chart rendering in JSDOM doesn't throw canvas errors
vi.mock('svelte-chartjs', () => ({
  Line: vi.fn()
}));

describe('RiskGaugeCards Component', () => {
  const defaultThresholds: Thresholds = {
    min_temp_caution: 45.0,
    min_temp_no_go: 38.0,
    max_wind_caution: 15.0,
    max_wind_no_go: 25.0,
    rain_threshold: 30.0
  };

  it('renders Go status when weather is within safe limits', () => {
    render(RiskGaugeCards, {
      props: {
        currentTemp: 65,
        currentWind: 8,
        currentPrecip: 10,
        thresholds: defaultThresholds,
        unitSystem: 'imperial'
      }
    });

    expect(screen.getByTestId('risk-gauge-cards')).toBeInTheDocument();
    expect(screen.getByText('65°F')).toBeInTheDocument();
    expect(screen.getByText('8 mph')).toBeInTheDocument();
    expect(screen.getByText('10%')).toBeInTheDocument();

    const goBadges = screen.getAllByText('Go');
    expect(goBadges.length).toBe(3);
  });

  it('renders Caution status when weather reaches caution thresholds', () => {
    render(RiskGaugeCards, {
      props: {
        currentTemp: 42,
        currentWind: 18,
        currentPrecip: 40,
        thresholds: defaultThresholds,
        unitSystem: 'imperial'
      }
    });

    const cautionBadges = screen.getAllByText('Caution');
    expect(cautionBadges.length).toBe(3);
  });

  it('renders No-Go status when weather exceeds risk thresholds', () => {
    render(RiskGaugeCards, {
      props: {
        currentTemp: 35,
        currentWind: 30,
        currentPrecip: 50,
        thresholds: defaultThresholds,
        unitSystem: 'imperial'
      }
    });

    expect(screen.getByText('35°F')).toBeInTheDocument();
    expect(screen.getByText('30 mph')).toBeInTheDocument();

    const noGoBadges = screen.getAllByText('No-Go');
    expect(noGoBadges.length).toBe(2);
  });
});

describe('HourlyWeatherChart Component', () => {
  const sampleHourlyData: HourlyForecastItem[] = [
    {
      time: '2026-08-02T08:00:00Z',
      temperature: 68.5,
      apparent_temp: 70.0,
      wind_speed: 8.2,
      precip_prob: 10.0,
      weather_code: 0
    },
    {
      time: '2026-08-02T09:00:00Z',
      temperature: 70.0,
      apparent_temp: 72.0,
      wind_speed: 9.5,
      precip_prob: 15.0,
      weather_code: 0
    }
  ];

  const sampleThresholds: Thresholds = {
    min_temp_caution: 45.0,
    min_temp_no_go: 38.0,
    max_wind_caution: 15.0,
    max_wind_no_go: 25.0,
    rain_threshold: 30.0
  };

  it('instantiates and renders component container with hourly data', () => {
    render(HourlyWeatherChart, {
      props: {
        hourlyData: sampleHourlyData,
        thresholds: sampleThresholds
      }
    });

    expect(screen.getByTestId('hourly-weather-chart')).toBeInTheDocument();
  });

  it('handles empty hourly data gracefully', () => {
    render(HourlyWeatherChart, {
      props: {
        hourlyData: [],
        thresholds: sampleThresholds
      }
    });

    expect(screen.getByTestId('hourly-weather-chart')).toBeInTheDocument();
  });
});
