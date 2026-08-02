import { render, screen } from '@testing-library/svelte';
import CommuteHistoryChart from '$lib/charts/CommuteHistoryChart.svelte';
import { describe, it, expect, vi } from 'vitest';

vi.mock('svelte-chartjs', () => ({
  Line: vi.fn()
}));

describe('CommuteHistoryChart', () => {
  it('renders without crashing with minimal data', () => {
    const minimalChartData = {
      labels: [],
      datasets: []
    };
    render(CommuteHistoryChart, { props: { chartData: minimalChartData } });
    expect(screen.getByTestId('commute-history-chart')).toBeInTheDocument();
  });

  it('renders with provided chart data', () => {
    const testChartData = {
      labels: ['Mon', 'Tue'],
      datasets: [
        {
          label: 'Days Ridden',
          data: [1, 2],
          backgroundColor: 'blue'
        },
        {
          label: 'Days Driven',
          data: [2, 1],
          backgroundColor: 'red'
        }
      ]
    };
    render(CommuteHistoryChart, { props: { chartData: testChartData } });
    expect(screen.getByTestId('commute-history-chart')).toBeInTheDocument();
  });
});
