import { render, screen, fireEvent } from '@testing-library/svelte';
import HistoryPage from './+page.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '$lib/api';
import { user } from '$lib/auth'; // Assuming user store is available

// Mock the API function
vi.mock('$lib/api', () => ({
  getCommuteStats: vi.fn(),
}));

// Mock the user store
vi.mock('$lib/auth', () => ({
  user: {
    subscribe: vi.fn((fn) => {
      fn({ id: 'test-user-123' }); // Provide a mock user
      return () => {};
    }),
  },
}));

describe('History Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock implementation for getCommuteStats
    (api.getCommuteStats as vi.Mock).mockResolvedValue({
      daily_stats: [
        { date: '2023-01-01', days_ridden: 5, days_driven: 2 },
        { date: '2023-01-02', days_ridden: 3, days_driven: 4 },
      ],
    });
  });

  it('renders without crashing', async () => {
    render(HistoryPage);
    expect(screen.getByText(/Commute History/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Start Date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/End Date/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refresh/i })).toBeInTheDocument();
  });

  it('fetches data on mount with default dates and displays chart', async () => {
    render(HistoryPage);
    expect(api.getCommuteStats).toHaveBeenCalledTimes(1);
    expect(api.getCommuteStats).toHaveBeenCalledWith(
      'test-user-123',
      expect.any(String), // Default start date
      expect.any(String)  // Default end date
    );

    // Wait for the chart to be rendered (it's inside CommuteHistoryChart, which we don't fully mock here)
    // We expect the svelte component to pass data to the chart component which has a testid.
    expect(await screen.findByTestId('commute-history-chart')).toBeInTheDocument();
  });

  it('refetches data when dates are changed and refresh is clicked', async () => {
    render(HistoryPage);

    // Initial fetch on mount
    expect(api.getCommuteStats).toHaveBeenCalledTimes(1);

    const startDateInput = screen.getByLabelText(/Start Date/i);
    const endDateInput = screen.getByLabelText(/End Date/i);
    const refreshButton = screen.getByRole('button', { name: /Refresh/i });

    await fireEvent.change(startDateInput, { target: { value: '2023-02-01' } });
    await fireEvent.change(endDateInput, { target: { value: '2023-02-28' } });
    await fireEvent.click(refreshButton);

    expect(api.getCommuteStats).toHaveBeenCalledTimes(2);
    expect(api.getCommuteStats).toHaveBeenCalledWith(
      'test-user-123',
      '2023-02-01',
      '2023-02-28'
    );
  });

  it('handles error during data fetch', async () => {
    (api.getCommuteStats as vi.Mock).mockRejectedValueOnce(new Error('API Error'));
    render(HistoryPage);
    expect(await screen.findByText(/Error fetching commute data:/i)).toBeInTheDocument();
  });
});
