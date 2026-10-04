import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { writable } from 'svelte/store';
import { newCommute } from '$lib/commute';
import { jwt_token } from '$lib/auth';
import * as api from '$lib/api';
import Page from './+page.svelte';
vi.mock('$lib/auth', () => ({ jwt_token: writable<string | null>(null) }));
vi.mock('$lib/api', () => ({ getCommuteConfig: vi.fn(), checkRoute: vi.fn() }));
const result = {
  overall_status: 'Go',
  overall_score: 100,
  recommendation: 'Within your limits.',
  timezone: 'UTC',
  outbound_leg: {
    leg_type: 'outbound',
    location_name: 'Home',
    schedule_time: '08:00',
    status: 'Go',
    score: 100,
    reasons: ['Clear conditions']
  }
};
beforeEach(() => {
  vi.resetAllMocks();
  jwt_token.set('token');
});
afterEach(cleanup);
describe('commute weather journey', () => {
  it('gives visitors one clear starting action without fetching private data', () => {
    jwt_token.set(null);
    render(Page);
    expect(screen.getByRole('link', { name: 'Set up my commute' })).toHaveAttribute(
      'href',
      '/register'
    );
    expect(api.getCommuteConfig).not.toHaveBeenCalled();
  });
  it('guides a new account to setup instead of showing an error', async () => {
    vi.mocked(api.getCommuteConfig).mockResolvedValue([]);
    render(Page);
    expect(await screen.findByRole('link', { name: 'Set up my commute' })).toHaveAttribute(
      'href',
      '/settings'
    );
    expect(api.checkRoute).not.toHaveBeenCalled();
  });
  it('checks the saved ID and can recover from an unavailable forecast', async () => {
    vi.mocked(api.getCommuteConfig).mockResolvedValue([{ ...newCommute(), id: 7 }]);
    vi.mocked(api.checkRoute)
      .mockRejectedValueOnce(new Error('Weather unavailable'))
      .mockResolvedValueOnce(result);
    render(Page);
    expect(await screen.findByRole('alert')).toHaveTextContent('Weather unavailable');
    expect(api.checkRoute).toHaveBeenCalledWith({ commute_id: 7 });
    await fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Good to ride' })).toBeInTheDocument();
  });
  it('ignores a late response for a different commute', async () => {
    let resolveFirst!: (value: typeof result) => void;
    vi.mocked(api.getCommuteConfig).mockResolvedValue([
      { ...newCommute(), id: 1 },
      { ...newCommute(), id: 2, name: 'Second' }
    ]);
    vi.mocked(api.checkRoute)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockResolvedValueOnce({ ...result, overall_status: 'No-Go' });
    render(Page);
    await fireEvent.change(await screen.findByLabelText('Your commute'), {
      target: { value: '2' }
    });
    expect(
      await screen.findByRole('heading', { name: 'Consider another way' })
    ).toBeInTheDocument();
    resolveFirst(result);
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Good to ride' })).not.toBeInTheDocument()
    );
  });
});
