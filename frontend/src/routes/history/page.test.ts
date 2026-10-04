import { render, screen, fireEvent } from '@testing-library/svelte';
import HistoryPage from './+page.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '$lib/api';
import { user } from '$lib/auth';

vi.mock('svelte-chartjs', () => ({
  Line: vi.fn()
}));

vi.mock('$lib/api', () => ({
  getCommuteStats: vi.fn(),
  recordDecision: vi.fn(),
}));

vi.mock('$lib/auth', () => ({
  user: {
    subscribe: vi.fn((fn) => {
      fn({ id: 'test-user-123' });
      return () => {};
    }),
  },
}));

describe('History Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getCommuteStats as any).mockResolvedValue({
      daily_stats: [
        { date: '2023-01-01', days_ridden: 5, days_driven: 2 },
        { date: '2023-01-02', days_ridden: 3, days_driven: 4 },
      ],
    });
    (api.recordDecision as any).mockResolvedValue({
      id: 1,
      commute_type: 'riding',
    });
  });

  it('renders without crashing', async () => {
    render(HistoryPage);
    expect(screen.getByText(/Commute History/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Start Date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/End Date/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refresh/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Rode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Drove/i })).toBeInTheDocument();
  });

  it('fetches data on mount with default dates and displays chart', async () => {
    render(HistoryPage);
    expect(api.getCommuteStats).toHaveBeenCalledTimes(1);
    expect(api.getCommuteStats).toHaveBeenCalledWith(
      'test-user-123',
      expect.any(String),
      expect.any(String)
    );

    expect(await screen.findByTestId('commute-history-chart')).toBeInTheDocument();
  });

  it('handles raw array responses from analytics API and renders chart', async () => {
    (api.getCommuteStats as any).mockResolvedValueOnce([
      { date: '2023-03-01', days_ridden: 4, days_driven: 1, avg_score: 85.0 },
      { date: '2023-03-02', days_ridden: 2, days_driven: 3, avg_score: 75.0 },
    ]);

    render(HistoryPage);
    expect(await screen.findByTestId('commute-history-chart')).toBeInTheDocument();
  });

  it('records ride decision and refreshes data', async () => {
    render(HistoryPage);
    const rideButton = screen.getByRole('button', { name: /Rode/i });
    await fireEvent.click(rideButton);

    expect(api.recordDecision).toHaveBeenCalledWith({ decision: 'riding' });
    expect(await screen.findByText(/Recorded today's commute as Riding/i)).toBeInTheDocument();
    expect(api.getCommuteStats).toHaveBeenCalledTimes(2);
  });

  it('records drive decision and refreshes data', async () => {
    render(HistoryPage);
    const driveButton = screen.getByRole('button', { name: /Drove/i });
    await fireEvent.click(driveButton);

    expect(api.recordDecision).toHaveBeenCalledWith({ decision: 'driving' });
    expect(await screen.findByText(/Recorded today's commute as Driving/i)).toBeInTheDocument();
  });

  it('refetches data when dates are changed and refresh is clicked', async () => {
    render(HistoryPage);

    expect(api.getCommuteStats).toHaveBeenCalledTimes(1);

    const startDateInput = screen.getByLabelText(/Start Date/i);
    const endDateInput = screen.getByLabelText(/End Date/i);
    const refreshButton = screen.getByRole('button', { name: /Refresh/i });

    await fireEvent.input(startDateInput, { target: { value: '2023-02-01' } });
    await fireEvent.input(endDateInput, { target: { value: '2023-02-28' } });
    await fireEvent.click(refreshButton);

    expect(api.getCommuteStats).toHaveBeenCalledTimes(2);
    expect(api.getCommuteStats).toHaveBeenLastCalledWith(
      'test-user-123',
      '2023-02-01',
      '2023-02-28'
    );
  });

  it('handles error during data fetch', async () => {
    (api.getCommuteStats as any).mockRejectedValueOnce(new Error('API Error'));
    render(HistoryPage);
    expect(await screen.findByText(/Error fetching commute data:/i)).toBeInTheDocument();
  });

  it('calls getCommuteStats with undefined userId when user store is unpopulated', async () => {
    (user.subscribe as any).mockImplementationOnce((fn: any) => {
      fn(null);
      return () => {};
    });
    render(HistoryPage);
    expect(api.getCommuteStats).toHaveBeenCalledWith(
      undefined,
      expect.any(String),
      expect.any(String)
    );
  });
});

