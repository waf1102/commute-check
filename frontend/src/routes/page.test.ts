import { render, screen, fireEvent, within, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '$lib/api';

vi.mock('svelte-chartjs', () => ({
  Line: vi.fn()
}));

vi.mock('$lib/api', () => ({
  getWeatherForecast: vi.fn(),
  checkRoute: vi.fn(),
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

  describe('Multi-Commute Switcher', () => {
    const mockMultiCommuteData = {
      assessments: [
        {
          id: 101,
          name: 'Work Commute',
          schedule_time: '08:00',
          unit_system: 'imperial',
          dest_name: 'Downtown Office',
          dest_lat: 37.7749,
          dest_lon: -122.4194,
          return_schedule_time: '17:00',
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
        },
        {
          id: 102,
          name: 'Evening Gym Commute',
          schedule_time: '18:30',
          unit_system: 'imperial',
          dest_name: 'Fitness Center',
          dest_lat: 37.7833,
          dest_lon: -122.4167,
          return_schedule_time: '20:30',
          assessment: {
            status: 'Caution',
            score: 65,
            recommendation: 'Gusty winds expected later',
            details: {
              temperature: 55.0,
              apparent_temp: 53.0,
              wind_speed: 22.0,
              wind_gusts: 30.0,
              precip_prob: 20,
              weather_code: 3
            }
          }
        }
      ]
    };

    const mockGymForecast = {
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
          time: '2026-08-02T18:00',
          temperature: 55.0,
          apparent_temp: 53.0,
          wind_speed: 22.0,
          precip_prob: 20,
          weather_code: 3
        }
      ]
    };

    it('does not render commute switcher when only one commute exists', () => {
      (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
      render(Page, { data: mockPageData });

      expect(screen.queryByTestId('commute-switcher')).not.toBeInTheDocument();
    });

    it('renders commute switcher dropdown and tabs when multiple commutes exist in account', () => {
      (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
      render(Page, { data: mockMultiCommuteData });

      expect(screen.getByTestId('commute-switcher')).toBeInTheDocument();
      expect(screen.getByTestId('commute-select')).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Work Commute' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: 'Evening Gym Commute' })).toBeInTheDocument();
    });

    it('selecting a different commute via tab selector updates route assessment card, weather chart, and risk gauges', async () => {
      (api.getWeatherForecast as any).mockResolvedValueOnce(mockForecast);
      (api.getWeatherForecast as any).mockResolvedValueOnce(mockGymForecast);

      render(Page, { data: mockMultiCommuteData });

      // Initially displays first commute
      const initialCard = within(screen.getByTestId('route-assessment-card'));
      expect(initialCard.getByText('Work Commute')).toBeInTheDocument();
      expect(initialCard.getByText('Go')).toBeInTheDocument();
      expect(initialCard.getByText('Great conditions for riding!')).toBeInTheDocument();

      // Click the tab for the second commute
      const gymTab = screen.getByRole('tab', { name: 'Evening Gym Commute' });
      await fireEvent.click(gymTab);

      // Route assessment card updates dynamically
      const updatedCard = within(screen.getByTestId('route-assessment-card'));
      expect(updatedCard.getByText('Evening Gym Commute')).toBeInTheDocument();
      expect(updatedCard.getByText('Caution')).toBeInTheDocument();
      expect(updatedCard.getByText('Gusty winds expected later')).toBeInTheDocument();
      expect(updatedCard.queryByText('Great conditions for riding!')).not.toBeInTheDocument();

      // Weather forecast fetched for second commute with destination coordinates
      expect(api.getWeatherForecast).toHaveBeenCalledWith(102, 'imperial', 37.7833, -122.4167);

      // Weather visualizations reflect second commute
      expect(await screen.findByRole('heading', { name: /Weather Visualizations/i })).toBeInTheDocument();
      expect(await screen.findByTestId('risk-gauge-cards')).toBeInTheDocument();
      expect(await screen.findByTestId('hourly-weather-chart')).toBeInTheDocument();
    });

    it('selecting a different commute via dropdown updates destination fields and assessment card', async () => {
      (api.getWeatherForecast as any).mockResolvedValueOnce(mockForecast);
      (api.getWeatherForecast as any).mockResolvedValueOnce(mockGymForecast);

      render(Page, { data: mockMultiCommuteData });

      const select = screen.getByTestId('commute-select') as HTMLSelectElement;
      await fireEvent.change(select, { target: { value: '1' } });

      const updatedCard = within(screen.getByTestId('route-assessment-card'));
      expect(updatedCard.getByText('Evening Gym Commute')).toBeInTheDocument();
      expect(updatedCard.getByText('Caution')).toBeInTheDocument();

      // Destination form fields update to the selected commute
      expect(screen.getByLabelText(/Destination Name/i)).toHaveValue('Fitness Center');
      expect(screen.getByLabelText(/Destination Latitude/i)).toHaveValue(37.7833);
      expect(screen.getByLabelText(/Destination Longitude/i)).toHaveValue(-122.4167);
      expect(screen.getByLabelText(/Return Schedule Time/i)).toHaveValue('20:30');
    });

    it('submitting destination form updates forecast and route assessment for selected commute', async () => {
      (api.getWeatherForecast as any).mockResolvedValue(mockGymForecast);
      const updatedAssessment = {
        status: 'Go',
        score: 90,
        recommendation: 'Conditions improved for gym ride',
        details: {
          temperature: 60.0,
          apparent_temp: 60.0,
          wind_speed: 10.0,
          wind_gusts: 12.0,
          precip_prob: 0,
          weather_code: 0
        }
      };
      (api.checkRoute as any).mockResolvedValue(updatedAssessment);

      render(Page, { data: mockMultiCommuteData });

      // Switch to gym commute
      const select = screen.getByTestId('commute-select') as HTMLSelectElement;
      await fireEvent.change(select, { target: { value: '1' } });

      // Update destination name and submit
      const destNameInput = screen.getByLabelText(/Destination Name/i);
      await fireEvent.input(destNameInput, { target: { value: 'New Fitness Center' } });

      const form = destNameInput.closest('form')!;
      await fireEvent.submit(form);

      expect(api.checkRoute).toHaveBeenCalledWith(expect.objectContaining({
        commute_id: 102,
        dest_name: 'New Fitness Center'
      }));

      expect(await screen.findByText('Conditions improved for gym ride')).toBeInTheDocument();
    });
  });

  describe('Loading & Error States', () => {
    it('displays loading spinner and skeleton loader while weather forecast is fetching on mount', async () => {
      let resolveForecast!: (val: any) => void;
      const forecastPromise = new Promise((resolve) => {
        resolveForecast = resolve;
      });
      (api.getWeatherForecast as any).mockReturnValue(forecastPromise);

      render(Page, { data: mockPageData });

      expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
      expect(screen.getByText(/Loading weather forecast/i)).toBeInTheDocument();
      expect(screen.getByTestId('skeleton-loader')).toBeInTheDocument();

      resolveForecast(mockForecast);

      await waitFor(() => {
        expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
      });
      expect(screen.queryByTestId('skeleton-loader')).not.toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /Weather Visualizations/i })).toBeInTheDocument();
    });

    it('displays loading indicator and updates button state while assessing route on form submit', async () => {
      (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
      let resolveCheck!: (val: any) => void;
      const checkPromise = new Promise((resolve) => {
        resolveCheck = resolve;
      });
      (api.checkRoute as any).mockReturnValue(checkPromise);

      render(Page, { data: mockPageData });

      await screen.findByRole('heading', { name: /Weather Visualizations/i });

      const submitBtn = screen.getByTestId('update-route-btn');
      expect(submitBtn).not.toBeDisabled();

      await fireEvent.click(submitBtn);

      expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
      expect(screen.getByText(/Assessing route and updating forecast/i)).toBeInTheDocument();
      expect(submitBtn).toBeDisabled();
      expect(submitBtn).toHaveTextContent(/Updating Route/i);

      resolveCheck({
        status: 'Go',
        score: 95,
        recommendation: 'Conditions clear',
        details: { temperature: 68, wind_speed: 5, precip_prob: 0 }
      });

      await waitFor(() => {
        expect(screen.queryByTestId('loading-indicator')).not.toBeInTheDocument();
      });
      expect(submitBtn).not.toBeDisabled();
      expect(submitBtn).toHaveTextContent(/Update Route Forecast/i);
    });

    it('renders error banner with retry button when getWeatherForecast fails and retries successfully', async () => {
      (api.getWeatherForecast as any).mockRejectedValueOnce(new Error('Network connection failed'));

      render(Page, { data: mockPageData });

      const errorBanner = await screen.findByTestId('error-banner');
      expect(errorBanner).toBeInTheDocument();
      expect(within(errorBanner).getByText(/Network connection failed/i)).toBeInTheDocument();

      const retryBtn = screen.getByTestId('retry-btn');
      expect(retryBtn).toBeInTheDocument();

      (api.getWeatherForecast as any).mockResolvedValueOnce(mockForecast);

      await fireEvent.click(retryBtn);

      expect(api.getWeatherForecast).toHaveBeenCalledTimes(2);

      await waitFor(() => {
        expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
      });
      expect(await screen.findByRole('heading', { name: /Weather Visualizations/i })).toBeInTheDocument();
    });

    it('renders error banner when checkRoute fails during route update and retries successfully', async () => {
      (api.getWeatherForecast as any).mockResolvedValue(mockForecast);
      (api.checkRoute as any).mockRejectedValueOnce(new Error('Route service timeout'));

      render(Page, { data: mockPageData });

      await screen.findByRole('heading', { name: /Weather Visualizations/i });

      await fireEvent.click(screen.getByTestId('update-route-btn'));

      const errorBanner = await screen.findByTestId('error-banner');
      expect(errorBanner).toBeInTheDocument();
      expect(within(errorBanner).getByText(/Route service timeout/i)).toBeInTheDocument();

      const retryBtn = screen.getByTestId('retry-btn');
      expect(retryBtn).toBeInTheDocument();

      (api.checkRoute as any).mockResolvedValueOnce({
        status: 'Go',
        score: 90,
        recommendation: 'Retry successful',
        details: { temperature: 65, wind_speed: 10, precip_prob: 0 }
      });

      await fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
      });
      expect(await screen.findByText('Retry successful')).toBeInTheDocument();
    });

    it('allows dismissing the error banner via dismiss button', async () => {
      (api.getWeatherForecast as any).mockRejectedValueOnce(new Error('Temporary glitch'));

      render(Page, { data: mockPageData });

      const errorBanner = await screen.findByTestId('error-banner');
      expect(errorBanner).toBeInTheDocument();

      const dismissBtn = screen.getByTestId('dismiss-btn');
      await fireEvent.click(dismissBtn);

      expect(screen.queryByTestId('error-banner')).not.toBeInTheDocument();
    });
  });
});
