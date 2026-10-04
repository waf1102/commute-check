import { render, screen, cleanup } from '@testing-library/svelte';
import { afterEach, expect, it } from 'vitest';
import LegRiskCard from '../LegRiskCard.svelte';
afterEach(cleanup);
it('shows plain language, correct units and no invented return', () => {
  render(LegRiskCard, {
    outboundLeg: {
      leg_type: 'outbound',
      location_name: 'Home',
      schedule_time: '08:00',
      status: 'No-Go',
      score: 0,
      reasons: ['Extreme wind speeds'],
      weather: {
        temperature: 12,
        apparent_temp: 10,
        wind_speed: 15,
        wind_gusts: 45,
        precip_prob: 20,
        weather_code: 0
      }
    },
    unitSystem: 'metric'
  });
  expect(screen.getByText('Consider another way')).toBeInTheDocument();
  expect(screen.getByText('10°C')).toBeInTheDocument();
  expect(screen.getByText('15 / 45 km/h')).toBeInTheDocument();
  expect(screen.queryByText('Heading back')).not.toBeInTheDocument();
});
